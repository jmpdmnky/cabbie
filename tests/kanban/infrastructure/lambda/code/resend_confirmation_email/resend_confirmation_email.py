import json
import boto3
from os import environ


CLIENT_ID = environ['COGNITO_APPCLIENT_ID']

client = boto3.client('cognito-idp')

def lambda_handler(event, context):
    # TODO Better error handling
    print(event)
    try:
        #event_body = json.loads(event['body'])
        username = event['pathParameters']['username']
    except:
        return respond(400, 'BadRequesError: Please provide a username.', cors=True)
        
    response = {}
    try:
        response = client.resend_confirmation_code(
            ClientId=CLIENT_ID,
            Username=username,

        )
    #except client.exceptions.NotAuthorizedException as e: # establish what exceptions to expect?
    #    return respond(401, 'Incorrect username or password.')
    except Exception as e:
        print(e)
        print(type(e))
        return respond(500, 'Internal Server Error')
    
    print(response)

    return respond(200, "Success", cors=True) 
    
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
