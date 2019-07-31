import json
import boto3
import re
import urllib.parse
import os

SNSTopicArn = os.environ['SNSTopicArn']

def lambda_handler(event, context):
    try:
        output = {}
        query = dict([x.split('=') for x in re.split('&', event['body'])])
        command = urllib.parse.unquote(query['command']).replace('/','')
        account = urllib.parse.unquote(query['text']).replace('/','')
        responseurl = urllib.parse.unquote(query['response_url'])

        sns_client = boto3.client('sns')

        # publish SNS message to delegate the actual work to worker lambda function
        message = {
            'command': command,
            'account': account,
            'responseurl': responseurl
        }

        sns_response = sns_client.publish(
            TopicArn=SNSTopicArn, 
            Message=json.dumps({'default': json.dumps(message)}),
            MessageStructure='json'
        )
        
    except Exception as e:
        response = '[ERROR] {}'.format(str(e))

    output['statusCode'] = 200
    output['body'] = 'Ok, fetching details for account *{}*'.format(account)
    return output
