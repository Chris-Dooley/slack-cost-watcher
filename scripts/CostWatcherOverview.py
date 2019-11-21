import boto3
import json
import datetime
import os
import time


def lambda_handler(event, context):
    # Get environment variables
    SNSTopicArn = os.environ['SNSTopicArn']

    # Variable declarations
    startDate = datetime.datetime.today() - datetime.timedelta(days = 1)
    startDateSOM = startDate.replace(day=1)
    endDate = datetime.datetime.today()
    return_message = ''
    return_stat_code = 0
    return_output = {}
    payload = {}
    dailyTotalCost = 0
    monthlyTotalCost = 0
    accountsList = []

    # Calculate the UTC offset
    utc_offset_sec = time.altzone if time.localtime().tm_isdst else time.timezone
    utc_offset = datetime.timedelta(seconds=-utc_offset_sec)

    # Organisation ID
    orgClient = boto3.client('organizations')
    orgResponse = orgClient.describe_organization()

    # Daily cost usage
    dailyClient = boto3.client('ce')
    dailyResponse = dailyClient.get_cost_and_usage(
        TimePeriod={
            'Start': startDate.strftime('%Y-%m-%d'),
            'End': endDate.strftime('%Y-%m-%d')
        },
        Granularity='DAILY',
        Metrics=[
            'UnblendedCost',
        ],
        GroupBy=[
            {
                'Type': 'DIMENSION',
                'Key': 'LINKED_ACCOUNT'
            },
        ]
    )

    # Month to date
    monthlyClient = boto3.client('ce')
    monthlyResponse = monthlyClient.get_cost_and_usage(
        TimePeriod={
            'Start': startDateSOM.strftime('%Y-%m-%d'),
            'End': endDate.strftime('%Y-%m-%d')
        },
        Granularity='MONTHLY',
        Metrics=[
            'UnblendedCost',
        ],
        GroupBy=[
            {
                'Type': 'DIMENSION',
                'Key': 'LINKED_ACCOUNT'
            },
        ]
    )

    dailyMetrics = dailyResponse['ResultsByTime'][0]['Groups']
    monthlyMetrics = monthlyResponse['ResultsByTime'][0]['Groups']

    # Loop through the monthly metrics, and map to the daily for each account
    for monthlyMetric in monthlyMetrics:
        account = monthlyMetric['Keys'][0]
        monthlyAmount = float(monthlyMetric['Metrics']['UnblendedCost']['Amount'])
        name =   boto3.client('organizations').describe_account(AccountId=account).get('Account').get('Name')

        # Check daily cost
        try:
            dailyAmount = float([x for x in dailyMetrics if x['Keys'][0] == account][0]['Metrics']['UnblendedCost']['Amount'])
        except IndexError:
            dailyAmount = 0

        # Prepare our output data
        if monthlyAmount > 0:
            accountsList.append({'accountNumber': account, 'accountName': name, 'dailyAmount': dailyAmount, 'monthlyAmount': monthlyAmount})

        dailyTotalCost += dailyAmount
        monthlyTotalCost += monthlyAmount

    # Sort the accounts list
    payload['accounts'] = sorted(accountsList, key=lambda x: x['dailyAmount'], reverse=True)
    # Add the overall entries
    # If this timestamp needs the microseconds changed to 3 digits, this should do it
    # re.sub(r'\.(\d{3})\d*\+', r'.\1+', startDate.replace(tzinfo=datetime.timezone(offset=utc_offset)).isoformat())
    payload['datestamp'] = startDate.replace(tzinfo=datetime.timezone(offset=utc_offset)).isoformat()
    payload['dailyTotal'] = round(dailyTotalCost, 2)
    payload['monthlyTotal'] = round(monthlyTotalCost, 2)
    payload['organisation'] = orgResponse['Organization']['Id']

    try:
        sns_client = boto3.client('sns')

        _ = sns_client.publish(
            TopicArn=SNSTopicArn,
            Message=json.dumps({'default': json.dumps(payload)}),
            MessageStructure='json'
        )
    except Exception as e:
        return_stat_code = 500
        return_message = '[ERROR] {}'.format(str(e))

    return_output['statusCode'] = return_stat_code or 200
    return_output['body'] = return_message or 'Ok, details for organisation *{}* published'.format(payload['organisation'])
    return return_output
