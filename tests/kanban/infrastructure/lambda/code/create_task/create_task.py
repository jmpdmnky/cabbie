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
    # TODO: ACTIALLY DO THIS
    team_id = "team_01"
    next_task_num = int(nextTask(ddb_client, "team_01"))
    
    # figure out the next task_id
    next_task_id = TASK_ID_TEMPLATE.format('task', next_task_num)
    
    # add task to DB
    print("TODO: actually handle response from db")
    #ddb_client.put_item(
    #    TableName=TABLE_NAME,
    #    Item=map_request(event, next_task_id)
    #)
    
    request_items = []
    for item in event:
        request_items.append(
            {
                'PutRequest': {
                    'Item': map_request(item, TASK_ID_TEMPLATE.format('task', next_task_num))
                }
            }
        )
        
        next_task_num += 1
    
    ddb_client.batch_write_item(
        RequestItems={
            TABLE_NAME: request_items
        }
        
    )
    
    # if successful, increment the next task num in the ddb
    ddb_client.update_item(
        TableName=TABLE_NAME,
         Key={
            'team_id': {
                'S': team_id
            },
            'task_id': {
                'S': "#PROFILE#{}".format(team_id)
            }
        },
        UpdateExpression='SET next_task = :val1', #'SET next_task = next_task + :val1
        ExpressionAttributeValues={
            ':val1': {
                "N": str(next_task_num)
            }
        }
    )
    
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


def map_request(request_data, task_id):
    item = {
        'task_id': {
            "S": task_id 
        }
    }
    
    print(request_data)
    
    # First go through the required fields
    # TODO: ADD ERROR HANDLING HERE
    for field in REQUIRED_FIELDS:
        item[field['name']] = {
            field['type']: request_data[field['request_parameter']]
        }
        
    # Next go through the optional fields
    for field in OPTIONAL_FIELDS:
        item[field['name']] = {
            field['type']: safe_get(request_data, field['request_parameter'], 'NULL')
        }

        
    # Next go through the default fields
    item.update(DEFAULT_FIELDS)
    
    return item
    

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