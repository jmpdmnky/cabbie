import json
import boto3
from os import environ


TABLE_NAME = environ['DDB_TABLE_NAME']

REQUIRED_FIELDS = [
#    {
#        "name": "task_id",
#        "type": "S",
#        "request_parameter": "taskId"
#    },
    {
        "name": "task_name",
        "type": "S",
        "request_parameter": "taskName"
    },
    {
        "name": "team_id",
        "type": "S",
        "request_parameter": "teamId"
    },
    {
        "name": "team_name",
        "type": "S",
        "request_parameter": "teamName"
    }
]

OPTIONAL_FIELDS = [
    {
        "name": "product",
        "type": "S",
        "request_parameter": "product"
    },
    {
        "name": "assignee",
        "type": "S",
        "request_parameter": "assignee"
    },
    {
        "name": "task_desc",
        "type": "S",
        "request_parameter": "taskDesc"
    }
]

DEFAULT_FIELDS = {
    "stage": {
        "N": "-1"
    }
}

TASK_ID_TEMPLATE = "{} {}"


def lambda_handler(event, context):
    # initiate Boto3
    ddb_client = boto3.client('dynamodb')
    
    # check ACL to see if user is permitted
    print("TODO: implement ACL")
    
    # get basic info from request 
    # TODO: ACTIALLY DO THIS... need to stop hardcoding the team.  Does team need to be one of the primary keys?  or should I set up a GSI?
    team_id = "team_01"
    task_id = event['taskId']
    print(event)
    
    
    # edit specified field in db
    response = ddb_client.update_item(
        TableName=TABLE_NAME,
         Key={
            'team_id': {
                'S': team_id
            },
            'task_id': {
                'S': task_id
            }
        },
        **map_request(event)
    )
    print(response)
    
    # respond
    return respond(200, "Response", cors=True)


def nextTask(client, team_id):
    response = client.query(
        TableName=TABLE_NAME,
        KeyConditionExpression="team_id = :v1 AND begins_with ( task_id, :v2 )",
        ExpressionAttributeValues={
        ":v1": {
            "S": team_id
        },
        ":v2": {
            "S": "#PROFILE#"
        }
    })
    
    return response['Items'][0]['next_task']['N']


def map_request(request_data):
    # TODO: make it able to handle more than one property to update?
    
#    UpdateExpression='SET next_task = next_task + :val1',
#    ExpressionAttributeValues={
#        ':val1': {
#            "N": "1"
#        }
#    }
    
#    {
#      "taskId": "task_01",
#      "properties": [
#        {
#            'name': 'stage',
#            'type': 'N'
#            'value': 2
#        }
#      ]
#    }
    
    expression_template = 'SET {property} = :val1' # number to change if we make this more complex
    
    
    return {
        'UpdateExpression': expression_template.format(property=request_data['properties'][0]['name']), 
        'ExpressionAttributeValues': {
            ':val1': {
                request_data['properties'][0]['type']: str(request_data['properties'][0]['value'])
            }
        }
    }
    

def safe_get(d, k, default):
    try:
        return d[k]
    except:
        return default
        
        
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