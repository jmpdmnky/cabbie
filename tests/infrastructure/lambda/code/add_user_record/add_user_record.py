import json
import boto3
from os import environ
from datetime import datetime

#TODO swap primary and sort key in tasks DB

DDB_TABLE = environ['DDB_TABLE']

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DDB_TABLE)

#apigateway = boto3.client('apigateway')

def lambda_handler(event, context):
    # TODO error handling
    #print(event)
    #print(event['request']['userAttributes'])

    # apigateway_response = apigateway.create_api_key(
    #     name=event['userName'],
    #     enabled=True,
    #     stageKeys=[
    #         {
    #             'restApiId': os.environ['APIGATEWAY_ID'],
    #             'stageName': os.environ['APIGATEWAY_STAGE_NAME']
    #         },
    #     ],
    # )
    
    # response = apigateway.create_usage_plan_key(
    #     usagePlanId=os.environ['APIGATEWAY_USAGEPLAN_ID'],
    #     keyId=apigateway_response['id'],
    #     keyType='API_KEY'
    # )
    
    ddb_args = {            
      'Item': {                
        'cognito_id': event['request']['userAttributes']['sub'],
        'task_id': '#PROFILE#{}'.format(event['userName']),
        'team_id': '#PROFILE#{}'.format(event['userName']),  # TODO we are inconsistent about how we store profiles... need to rethink this
        #'username': event['userName'], # eventually have username be a changeable display name, userID randomized
        'user_id': event['userName'],
        'email': event['request']['userAttributes']['email'],
        #'api_key_id': apigateway_response['id'],
        #'api_key_value': apigateway_response['value'],
        'created': datetime.now().strftime("%m%d%Y%H%M%S"),
        'new_user': True
      },
      'TableName': DDB_TABLE       
    }
    
    response = table.put_item(
        **ddb_args,
        ConditionExpression='attribute_not_exists(user_id)'
    )
    
    print(ddb_args)

    return event
