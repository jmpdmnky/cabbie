import json
import boto3
from boto3.dynamodb.conditions import Key, Attr
from os import environ

DDB_TABLE = environ['DDB_TABLE_NAME']
    

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DDB_TABLE)

def lambda_handler(event, context):
    # get existing profile data
    try:
        event_body = json.loads(event['body'])
        user_string = '#PROFILE#{}'.format(event_body['userId'])
        user_id = user_string  # TODO: rework once we rework schema
    except Exception as e:
        print(e)
        return respond(400, 'BadRequestError: Missing required arguments.', cors=True)

    try:
        profile = table.get_item(
            Key={
                'task_id': user_string,
                'team_id': user_id
            }
        )['Item']
    except Exception as e:
        print(e)
        return respond(500, 'Internal Server Error', cors=True)

    # update item, put in ddb
    ddb_item = ddb_args(event, profile)
    try:
        response = table.put_item(
            Item={
                **ddb_item
            }
        )
    except Exception as e:
        print(e)
        return respond(500, 'Internal Server Error.', cors=True)
    
    return respond(200, {'profile': ddb_item}, cors=True)


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



def overwrite_item(old, new):
    return new


def append_item(old, new):
    for item in new:
        if item not in new:
            old.append(item)
        
    return old


def task_id(old, new):
    return '#PROFILE#{}'.format(new)


def team_id(old, new):
    return '#PROFILE#{}'.format(new)


def read_only(old, new):
    return old


VALID_ATTRIBUTES = [
    {
        'name': 'cognito_id',
        'event': 'cognitoId',
        'default': '',
        'update_action': read_only
    },
    # {
    #     'name': 'task_id',
    #     'event': 'userId',
    #     'default': '',
    #     'update_action': read_only
    # },
    # {
    #     'name': 'team_id',
    #     'event': 'userId',
    #     'default': '',
    #     'update_action': read_only
    # },
    {
        'name': 'username', # optional display name
        'event': 'username',
        'default': '',
        'update_action': overwrite_item
    }, 
    {
        'name': 'user_id', # randomized value, probably need to put this in task_id?
        'event': 'userId', 
        'default': '',
        'update_action': read_only 
    }, 
    {
        'name': 'email',
        'event': 'email',
        'default': '',
        'update_action': overwrite_item
    },
    {
        'name': 'api_key_id', # TODO: implement
        'event': 'apiKeyId',
        'default': '',
        'update_action': read_only 
    }, 
    {
        'name': 'api_key_value', # TODO: implement
        'event': 'apiKeyValue',
        'default': '',
        'update_action': read_only
    },
    {
        'name': 'created',
        'event': 'created',
        'default': '',
        'update_action': read_only
    },
    {
        'name': 'first_name',
        'event': 'firstName',
        'default': '',
        'update_action': overwrite_item
    },
    {
        'name': 'middle_name',
        'event': 'middleName',
        'default': '',
        'update_action': overwrite_item
    },
    {
        'name': 'last_name',
        'event': 'lastName',
        'default': '',
        'update_action': overwrite_item
    },
    {
        'name': 'nickname',
        'event': 'nickname',
        'default': '',
        'update_action': overwrite_item
    },
    {
        'name': 'birthday',
        'event': 'birthday',
        'default': '',
        'update_action': overwrite_item
    },
    {
        'name': 'phone',
        'event': 'phone',
        'default': '',
        'update_action': overwrite_item
    },
    {
        'name': 'marketing_opt_out',
        'event': 'marketingOptOut',
        'default': True,
        'update_action': overwrite_item
    },
    {
        'name': 'mfa_enabled',
        'event': 'mfaEnabled',
        'default': False,
        'update_action': overwrite_item
    },
    {
        'name': 'orgs',
        'event': 'orgs',
        'default': [],
        'update_action': append_item
    },
    {
        'name': 'teams',
        'event': 'teams',
        'default': [],
        'update_action': append_item
    },
    {
        'name': 'new_user',
        'event': 'newUser',
        'default': True,
        'update_action': overwrite_item
    }
]


def ddb_args(event, item):
    event_body = json.loads(event['body'])

    ddb_item = item

    for attr in VALID_ATTRIBUTES:
        # if the attr does not exist, give it the default value
        if attr['name'] not in item.keys():
            item[attr['name']] = attr['default']

        # update with new value
        new_val = safe_dict_val(event_body, attr['event'])
        old_val = item[attr['name']]
        if new_val:
            ddb_item[attr['name']] = attr['update_action'](old_val, new_val)

    return ddb_item


def camel_case(string):
    camel_string = ''
    next_cap =  False
    for char in string:
        if char != '_':
            camel_string += char.upper() if next_cap else char
            next_cap = False
        else:
            next_cap = True
    
    return camel_string


def grownup_case(string):
    grownup_string = ''
    for char in string:
        if char.isupper():
            grownup_string += '_'
        grownup_string += char.lower()
        
    return grownup_string


def safe_dict_val(d, k, default=False, error=False):
    try:
        return d[k]
    except Exception as e:
        if error:
            raise e
        else:
            return default