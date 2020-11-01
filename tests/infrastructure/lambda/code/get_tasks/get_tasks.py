import json
import boto3
from os import environ


TABLE_NAME = environ['DDB_TABLE_NAME']

# set up lists based on LOD requested

REQUIRED_FIELDS = [
    {
        "name": "task_id",
        "type": "S",
        "request_parameter": "taskId"
    },
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
        "N": "0"
    }
}


ALL_FIELDS = {
    "product": {"S": "NULL"}, 
    "task_desc": {"S": "asdfasdf"}, 
    "team_name": {"S": "HoopDreams"}, 
    "stage": {"N": "0"}, 
    "task_id": {"S": "task 123"}, 
    "assignee": {"S": "NULL"}, 
    "task_name": {"S": "asdf"}, 
    "team_id": {"S": "team_01"}
}

ALL_FIELDS = {
    "product": "S", 
    "task_desc": "S", 
    "team_name": "S", 
    "stage": "N", 
    "task_id": "S", 
    "assignee": "S", 
    "task_name": "S", 
    "team_id": "S"
}

def lambda_handler(event, context):
    # initiate Boto3
    ddb_client = boto3.client('dynamodb')
    
    #print(event)
    
    # check ACL to see if user is permitted
    print("TODO: implement ACL")
        
    # add task to DB
    print("TODO: actually handle response from db")
    response = ddb_client.query(
        TableName=TABLE_NAME,
        KeyConditionExpression="team_id = :v1",
        ExpressionAttributeValues=map_request(event)
    )
    
    items = list(where_not(response['Items'], 'task_id', {'S': '#PROFILE#team_01'}))
    
    #print(map_response(items))
    
    # respond
    return respond(200, map_response(items), cors=True)


def map_request(request_data):
    item = {}
    
    # So far we will only have the ability to query by team
    return {
        ":v1": {
            "S": request_data['teamId']
        }
    }


def map_response(response_data):
    mapped_data = []
    
    for item in response_data:
        temp_item = {}
        for k, v in item.items():
            #print(item[k])
            #print(ALL_FIELDS[k])
            temp_item[k] = item[k][ALL_FIELDS[k]]
            
        mapped_data.append({**temp_item})
        
    return mapped_data


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
    
def where(dl, k, v):
    for d in dl:
        if d[k] == v:
            yield d
            

def where_not(dl, k, v):
    for d in dl:
        if d[k] != v:
            yield d
            
            