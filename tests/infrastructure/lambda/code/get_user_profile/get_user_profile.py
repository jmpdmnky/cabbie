import json
import boto3
from os import environ

DDB_TABLE = environ['DDB_TABLE']

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DDB_TABLE)

def lambda_handler(event, context):
    try:
        user_id = event['pathParameters']['user-id']
    except Exception as e:
        print(e)
        return respond(400, 'BadRequestError: Please provide a user ID.', cors=True)
        
    profile_string = '#PROFILE#{}'.format(user_id)
    
    try:
        response = table.get_item(
            Key={
                'task_id': profile_string,
                'team_id': profile_string
            }
        )
    except:
        return respond(500, 'Internal Server Error.', cors=True)
    
    if 'Item' in response.keys():
        return respond(200, response['Item'], cors=True)
    return respond(200, {}, cors=True)
    


def respond(code, data, cors=False):
    response = {
        'statusCode': code,
        'body': json.dumps(data)
    }
    
    if cors:
        response['headers'] = {
            'Content-Type': 'application/json', 
            'Access-Control-Allow-Origin': '*' 
        }
        
    return response
