import boto3
import json
import datetime
import os
from botocore.vendored import requests

startDate = datetime.datetime.today() - datetime.timedelta(days = 1)
startDateSOM = startDate.replace(day=1)
endDate = datetime.datetime.today()

AccountWarningLevel = int(os.environ['AccountWarningLevel'])
AccountDangerLevel = int(os.environ['AccountDangerLevel'])
SlackWebHookUrl = os.environ['SlackWebHookUrl']


def lambda_handler(event, context):
    #Daily cost usage
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

    #Month to date
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
    
    dailyTotalCost = 0
    monthlyTotalCost = 0
    maxAccount = 0
    maxDaily = 0
    maxMonthly = 0
    
    OutputList = []
    for monthlyMetric in monthlyMetrics:
        account = monthlyMetric['Keys'][0]
        monthlyAmount = float(monthlyMetric['Metrics']['UnblendedCost']['Amount'])
        name =   boto3.client('organizations').describe_account(AccountId=account).get('Account').get('Name')
        accountFriendly = '({}) {}'.format(account,name)
        
        try:
            #Check daily cost
            dailyAmount = 0
            dailyAmount = float([x for x in dailyMetrics if x['Keys'][0] == account][0]['Metrics']['UnblendedCost']['Amount'])
        except IndexError:
            dailyAmount = 0
        
        #Get sizes for output alignment
        lenAccount = len(accountFriendly)
        if lenAccount > maxAccount:
            maxAccount = lenAccount
        
        lenDaily = len('{:.2f}'.format(round(dailyAmount,2)))
        if lenDaily > maxDaily:
            maxDaily = lenDaily
            
        lenMonthly = len('{:.2f}'.format(round(monthlyAmount,2)))
        if lenMonthly > maxMonthly:
            maxMonthly = lenMonthly
            
        #Prepare our output data
        if monthlyAmount > 0:
            OutputList.append((accountFriendly,dailyAmount,monthlyAmount))
        
        dailyTotalCost += dailyAmount
        monthlyTotalCost += monthlyAmount
        
    OutputList = sorted(OutputList, key=lambda x: x[2], reverse=True)
    
    payload = '{"username":"Cost-Watcher","icon_emoji":":fire:","text": "'
    payload += '{} - Cost yesterday is ${:.2f}. MTD is ${:.2f}\n'.format(startDate.strftime('%d %b %Y (%a)'), round(dailyTotalCost, 2), round(monthlyTotalCost, 2))
    
    for key, val1, val2 in OutputList:
            
        if val2 > AccountDangerLevel:
            emoji = 'red_bar'
        elif val2 > AccountWarningLevel:
            emoji = 'yellow_bar'
        else:
            emoji = 'green_bar'
        payload += ':{}:`'.format(emoji) + '{0:{1}}'.format(key,maxAccount) + ': Y${0:{1}.2f}'.format(round(val1, 2),maxDaily) + '  M${0:{1}.2f}'.format(round(val2, 2),maxMonthly) + '`\n'
    payload += '"}'
    
    
    requests.post(SlackWebHookUrl, data=payload)