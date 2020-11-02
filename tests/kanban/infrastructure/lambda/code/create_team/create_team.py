import json
import boto3
from boto3.dynamodb.conditions import Key, Attr
from os import environ

DDB_TABLE = environ['DDB_TABLE']

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DDB_TABLE)

def lambda_handler(event, context):
    try:
        # TODO: Do something with invitees
        # TODO: Generate a unique team ID so we can have non-unique names
        event_body = json.loads(event['body'])
        team_string = '#TEAM#{}'.format(event_body['name'])
        team_id = team_string
        ddb_item = {
            'task_id': team_string,
            'team_id': team_id,
            'parent_org_id': event_body['parentOrg'],
            'description': event_body['description'],
            'name': event_body['name']
        }
    except Exception as e:
        print(e)
        return respond(400, 'BadRequestError: Missing required arguments.', cors=True)

    try:
        response = table.put_item(
            Item={
                **ddb_item
            },
            ConditionExpression=Attr('team_id').not_exists()
        )
    except Exception as e:
        print(e)
        return respond(500, 'Internal Server Error.', cors=True)
    
    return respond(200, {'team_id': team_id} , cors=True)


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
