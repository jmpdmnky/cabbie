import json
import boto3
from os import environ

# TODO handle InvalidParameterException (invalid e-mail etc)

CLIENT_ID = environ['COGNITO_APPCLIENT_ID']

client = boto3.client('cognito-idp')

def lambda_handler(event, context):
    # TODO Better error handling
    response = {}
    try:
        event_body = json.loads(event['body'])
        response = client.sign_up(
            ClientId=CLIENT_ID,
            Username=event_body['username'],
            Password=event_body['password'],
            UserAttributes=[
                {
                    'Name': 'email',
                    'Value': event_body['email']
                },
            ]
        )
    except client.exceptions.UsernameExistsException as e: # establish what exceptions to expect?
        return respond(401, 'User already exists.', cors=True)
    except Exception as e:
        print(e)
        print(type(e))
        return respond(500, 'Internal Server Error', cors=True)
    
    print(response)

    print(response['UserConfirmed']) # do something with this?
    sub = response['UserSub']

    # TODO: is this where I need to send verification 

    # TODO: change response based on 'userconfirmed'?
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
