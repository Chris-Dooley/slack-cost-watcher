import boto3
import json
import datetime
import os
from botocore.vendored import requests

def lambda_handler(event, context):
    # Get environment variables
    AccountWarningLevel = int(os.environ['AccountWarningLevel'])
    AccountDangerLevel = int(os.environ['AccountDangerLevel'])
    SlackWebHookUrl = os.environ['SlackWebHookUrl']

    try:
        message = json.loads(event['Records'][0]['Sns']['Message'])
    except Exception as e:
        payload = '{"text" : "' + '[ERROR] {}'.format(str(e)) + '"}'
    else:
        accounts_list = message['accounts']
        datestamp = datetime.datetime.fromisoformat(message['datestamp']).strftime('%d %b %Y (%a)')
        dailyTotal = message['dailyTotal']
        monthlyTotal = message['monthlyTotal']

        # Calculate the max string lengths for pretty formatting
        account_lengths = [(len('({}) {}'.format(x['accountNumber'], x['accountName'])),
                            len('{:.2f}'.format(round(x['dailyAmount'],2))),
                            len('{:.2f}'.format(round(x['monthlyAmount'],2)))
                           ) for x in accounts_list]

        maxAccount = max(account_lengths, key=lambda x: x[0])[0]
        maxDaily = max(account_lengths, key=lambda x: x[1])[1]
        maxMonthly = max(account_lengths, key=lambda x: x[2])[2]

        payload = '{"username":"Cost-Watcher","icon_emoji":":fire:","text": "'
        payload += '{} - Cost yesterday is ${:.2f}. MTD is ${:.2f}\n'.format(datestamp, round(dailyTotal, 2), round(monthlyTotal, 2))

        for val in accounts_list:
            accountFriendly = '({}) {}'.format(val['accountNumber'], val['accountName'])

            if val['monthlyAmount'] > AccountDangerLevel:
                emoji = 'red_bar'
            elif val['monthlyAmount'] > AccountWarningLevel:
                emoji = 'yellow_bar'
            else:
                emoji = 'green_bar'

            payload += ':{}:`'.format(emoji)
            payload += '{0:{1}}'.format(accountFriendly, maxAccount)
            payload += ': Y${0:{1}.2f}'.format(round(val['dailyAmount'], 2),maxDaily)
            payload += '  M${0:{1}.2f}'.format(round(val['monthlyAmount'], 2),maxMonthly)
            payload += '`\n'

        payload += '"}'

    requests.post(SlackWebHookUrl, data=payload)