import boto3
import json
import datetime
import os
import urllib3

startDate = datetime.datetime.today() - datetime.timedelta(days = 1)
startDateSOM = startDate.replace(day=1)
endDate = datetime.datetime.today()

DetailWarningLevel = int(os.environ['DetailWarningLevel'])
DetailDangerLevel = int(os.environ['DetailDangerLevel'])

http = urllib3.PoolManager()


def lambda_handler(event, context):
    
    try:
        message = json.loads(event['Records'][0]['Sns']['Message'])
        account = message['account']
        responseurl = message['responseurl']
    
        # #Validate the account number
        
        #Daily cost usage
        dailyClient = boto3.client('ce')
        dailyResponse = dailyClient.get_cost_and_usage(
            TimePeriod={
                'Start': startDate.strftime('%Y-%m-%d'),
                'End': endDate.strftime('%Y-%m-%d')
            },
            Granularity='DAILY',
            Filter={
                'Dimensions': {
                    'Key': 'LINKED_ACCOUNT',
                    'Values': [
                        account 
                    ]
                }
            },
            Metrics=[
                'UnblendedCost',
            ],
            GroupBy=[
                {
                    'Type': 'DIMENSION',
                    'Key': 'SERVICE'
                },
            ]
        )
    
        #Month to date
        monthlyClient = boto3.client('ce')
        monthlyResponse = monthlyClient.get_cost_and_usage(
            TimePeriod={
                'Start': startDateSOM.strftime('%Y-%m-%d'),
                'End': endDate.strftime('%Y-%m-%d')
            },
            Granularity='MONTHLY',
            Filter={
                'Dimensions': {
                    'Key': 'LINKED_ACCOUNT',
                    'Values': [
                        account
                    ]
                }
            },
            Metrics=[
                'UnblendedCost',
            ],
            GroupBy=[
                {
                    'Type': 'DIMENSION',
                    'Key': 'SERVICE'
                },
            ]
        )
    
        
        dailyMetrics = dailyResponse['ResultsByTime'][0]['Groups']
        monthlyMetrics = monthlyResponse['ResultsByTime'][0]['Groups']
        
        dailyTotalCost = 0
        monthlyTotalCost = 0
        maxService = 0
        maxDaily = 0
        maxMonthly = 0
        
        OutputList = []
        for monthlyMetric in monthlyMetrics:
            service = monthlyMetric['Keys'][0]
            monthlyAmount = float(monthlyMetric['Metrics']['UnblendedCost']['Amount'])
            
            try:
                #Check daily cost
                dailyAmount = 0
                dailyAmount = float([x for x in dailyMetrics if x['Keys'][0] == service][0]['Metrics']['UnblendedCost']['Amount'])
            except IndexError:
                dailyAmount = 0
            
            #Get sizes for output alignment
            lenService = len(service)
            if lenService > maxService:
                maxService = lenService
        
            lenDaily = len('{:.2f}'.format(round(dailyAmount,2)))
            if lenDaily > maxDaily:
                maxDaily = lenDaily
                
            lenMonthly = len('{:.2f}'.format(round(monthlyAmount,2)))
            if lenMonthly > maxMonthly:
                maxMonthly = lenMonthly
                
            #Prepare our output data
            if monthlyAmount > 0:
                OutputList.append((service,dailyAmount,monthlyAmount))
            
            dailyTotalCost += dailyAmount
            monthlyTotalCost += monthlyAmount
            
        OutputList = sorted(OutputList, key=lambda x: x[2], reverse=True)
        
        payload = '{"username":"Cost-Watcher","icon_emoji":":fire:","text": "'
        payload += '*{}* - Cost yesterday is ${:.2f}. MTD is ${:.2f}\n'.format(account, round(dailyTotalCost, 2), round(monthlyTotalCost, 2))
        
        for key, val1, val2 in OutputList:
            if val2 > DetailDangerLevel:
                emoji = 'red_bar'
            elif val2 > DetailWarningLevel:
                emoji = 'yellow_bar'
            else:
                emoji = 'green_bar'
            payload += ':{}:`'.format(emoji) + '{0:{1}}'.format(key,maxService) + ': Y${0:{1}.2f}'.format(round(val1, 2),maxDaily) + '  M${0:{1}.2f}'.format(round(val2, 2),maxMonthly) + '`\n'        
        payload += '"}'
    
    except Exception as e:
        payload = '{"text" : "' + '[ERROR] {}'.format(str(e)) + '"}'
    
    encoded_msg = payload.encode('utf-8')
    req = http.request('POST',responseurl, body=encoded_msg)
    return req.data