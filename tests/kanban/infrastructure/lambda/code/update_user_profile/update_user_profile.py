import json
import boto3
from os import environ

DDB_TABLE = environ['DDB_TABLE']

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DDB_TABLE)

def lambda_handler(event, context):
    #TODO: Implememt
    print(event)
    print(event.keys())
    return respond(200, event, cors=True)


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
