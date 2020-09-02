#!/bin/bash 

aws cloudformation package --template template.yaml --s3-bucket "<Staging Bucket Name>" --output-template-file packaged.yaml

aws cloudformation deploy --template-file packaged.yaml --stack-name cost-watcher --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides SlackWebHookUrl="<Slack webhook>"