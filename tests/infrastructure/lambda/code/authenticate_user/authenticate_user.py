import json
import boto3
from os import environ


CLIENT_ID = environ['COGNITO_APPCLIENT_ID']

client = boto3.client('cognito-idp')

def lambda_handler(event, context):
    # TODO Better error handling
    try:
        event_body = json.loads(event['body'])
        username = event_body['username']
        password = event_body['password']
    except:
        return respond(400, 'BadRequesError: Please provide a username and password.', cors=True)
    
    # TODO: what do i do for unverified users?  users w/ expired passwords?
    response = {}
    try:
        response = client.initiate_auth(
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password
            },
            ClientId=CLIENT_ID,
        )
    except client.exceptions.NotAuthorizedException as e:
        return respond(401, 'NotAuthorizedError: Incorrect username or password.', cors=True)
    except client.exceptions.UserNotFoundException as e:
        return respond(401, 'NotAuthorizedError: Incorrect username or password.', cors=True)
    except client.exceptions.UserNotConfirmedException as e:
        return respond(401, 'NotConfirmedError: User has not been verified.', cors=True)
    except Exception as e:
        print(e)
        print(type(e))
        return respond(500, 'InternalServerError: Internal Server Error', cors=True)
    
    print(response)
    print(response['AuthenticationResult'].keys())
    
    user_data = {
        'auth_data': response['AuthenticationResult'],
        'profile_data': { # TODO
            'username': username,
            'email': '',
            'email_verified': '',
            'sub': '', 
        }
    }
    
    auth_data = {
        'username': username,
        **response['AuthenticationResult']
    }
    
    print(client.get_user(
        AccessToken=auth_data['AccessToken']
    ))

    # TODO:  do we want to return user_data or auth_data?  probably auth and move user_data into another api call?
    return respond(200, auth_data, cors=True) 
    
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
