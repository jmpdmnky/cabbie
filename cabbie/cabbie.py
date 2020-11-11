####################################
#
# cloud app builder script for resource deployment automation-ish
# TODO: move resource args into separate json registry file
# TODO: promote copy of resource args to stage folder
# TODO: make generic rather than hard code functions for each service
# TODO: replace sleeps w/ retries?
# TODO: handle failure better... probably roll back
# TODO: probably no reason to have the 'attributes' key in resource template?
# TODO: add ability to add "modules" like auth, website boilerplates, etc
# TODO: gracefully handle missing keys in resource_template
# TODO: treat apigateway api as one resource, instead a bunch of small ones
# TODO: switch iam roles to use ${resource} identifiers in policy list
# TODO: switch apigateway api_method integration.uri to be something more human readable like endpoint_resource and automatically build the uri
# TODO: stop hardcoding region.  probably need to save as a part of every resource
# TODO: Cors config seem to work for POST but not PUT... need to figure that out
# TODO: implement build queue
#
####################################

####################################
# 
# AUTOMATION OPPORTUNITIES:
# TODO: adding resource permissions to lambda is a pain
# TODO: testing!
# TODO: Auto-build list of dependencies based on what refers to which resources 
# 
####################################

####################################
# 
# BUGS TO WORK AROUND:
# TODO: deleting and recreating iam/lambda with same name too quickly can create error when invoking lambda... something about IAM role not being able to be assumed by lambda.  maybe create all lambda functions with a dummy role, attach real one at end, then delete dummy? maybe init with real role, switch to dummy, switch back to real?
#
####################################


####################################
# 
# Future workflow:
# 1. build lists of resources to build/modify/destroy with args (not parsed yet)
# 1a. if resources/vars referenced, add as dependency
# 2. iterate through list, execute if no dependency, or if dependency resolved
# 3. if any unresolved dependencies, error
# 
####################################

import boto3
import json
import sys
import os
import re
import shutil
from time import sleep
from zipfile import ZipFile 

from common.files import file_bytes
from common.files import file_string
from common.files import file_obj
from common.files import file_json
from common.files import join_path
from common.files import list_dir

from common.dicts import list_where
from common.dicts import safe_dict_val
from common.dicts import dict_where
from common.dicts import dict_wheres
from common.dicts import fwalk_dict
from common.dicts import dict_select
from common.dicts import dict_dotval

from common.safety import try_retry
from common.safety import try_default

from aws.resources import distribution
from aws.resources import DependecyNotMetError

from core import cloud_app


# basic init actions

config = { 
    'project_name': 'cognito_auth',
    'project_home': 'C:/Users/rwhoo/Desktop/Stuff/cognito-auth/', 
    'template': 'resource_template.json',
    'stages': ['dev', 'qa', 'prod']
}


# Are we building or destroying?
# TODO: replace with some kind of CLI arg
destroy = False
rebuild = True
active_stage = 'dev'


print("initializing cabbie")
app = cloud_app(active_stage)

live_resources = app.live_resources

# profiles = { # TODO: move this to a hidden file that is not pushed to github 
#     'dev': 'kanban-dev',
#     'qa': 'kanban-qa',
#     'prod': 'kanban-prod
# }

session = boto3.session.Session(profile_name=app.aws_profile)

clients = {
    'iam': session.client('iam'),
    'ddb': session.client('dynamodb'),
    'lambda': session.client('lambda'),
    'apigateway': session.client('apigateway'),
    'cognito': session.client('cognito-idp'),
    'sts': session.client('sts'),
    's3' : session.client('s3')
}

# TODO: can use other response items for tracking?
account_id = clients['sts'].get_caller_identity()['Account']

# # load in current list of resources for env
# live_resource_filepaths = {
#     'dev': 'dev/resources.json',
#     'qa': 'qa/resources.json',
#     'prod': 'prod/resources.json'
# }




def create_dummy_lambda_role():
    trust_doc = "{ \"Version\": \"2012-10-17\", \"Statement\": [ { \"Effect\": \"Allow\", \"Principal\": { \"Service\": \"lambda.amazonaws.com\" }, \"Action\": \"sts:AssumeRole\" } ] }"

    return clients['iam'].create_role(
        RoleName='cabbie_dummy_lambda_role', #TODO rename this to refer to some official error tracker
        AssumeRolePolicyDocument=trust_doc,
        Description='temp role to fix lambda bug' #TODO change this to refer to some official error tracker
    )['Role']['Arn']


def delete_dummy_lambda_role():
    response = clients['iam'].delete_role(
        RoleName='cabbie_dummy_lambda_role'
    )


def add_cors(rest_api_id, resource_id, path, resource):
    resource_data = {
        'http_method': 'OPTIONS',
        'path': path,
        'api_id': rest_api_id
    }

    response = clients['apigateway'].put_method(
        restApiId=rest_api_id,
        resourceId=resource_id,
        httpMethod='OPTIONS',
        authorizationType='NONE',
    )

    resource_data['arn'] = 'arn:aws:execute-api:us-east-1:{account_id}:{api_id}/*/{http_method}{path}'.format(
        account_id=account_id,
        api_id=rest_api_id,
        http_method='OPTIONS',
        path=re.sub(r'{.+}', '*', path) # handle path params
    )

    sleep(1)

    response = clients['apigateway'].put_method_response(
        restApiId=rest_api_id,
        resourceId=resource_id,
        httpMethod='OPTIONS',
        statusCode='200',
        responseParameters={
            'method.response.header.Access-Control-Allow-Headers': False, 
            'method.response.header.Access-Control-Allow-Methods': False, 
            'method.response.header.Access-Control-Allow-Origin': False
        },
        responseModels={
            'application/json': 'Empty'
        }
    )

    sleep(1)

    response = clients['apigateway'].put_integration(
        restApiId=rest_api_id,
        resourceId=resource_id,
        httpMethod='OPTIONS',
        type='MOCK',
        uri='string',
        requestTemplates={
            'application/json': '{"statusCode": 200}'
        },
        passthroughBehavior='WHEN_NO_MATCH',
        timeoutInMillis=29000
    )

    sleep(1)

    response = clients['apigateway'].put_integration_response(
        restApiId=rest_api_id,
        resourceId=resource_id,
        httpMethod='OPTIONS',
        statusCode='200',
        responseParameters={
            'method.response.header.Access-Control-Allow-Headers': "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'", 
            'method.response.header.Access-Control-Allow-Methods': "'OPTIONS,POST'", 
            'method.response.header.Access-Control-Allow-Origin': "'*'"
        }
    )

    return resource_data


def external_file(path):
    try:
        manifest = file_json('{}/manifest.json'.format(path))
    except Exception as e:
        print(e)
        print('failed to open manifest!')

    try:
        template = file_string('{}/{}'.format(path, manifest['template']))
    except Exception as e:
        print(e)
        print('failed to open template!')

    try:
        with open(manifest['destination'], 'w') as outfile:
            outfile.write(evaluate(template))
    except Exception as e:
        print(e)
        print('failed to write to destination!')


def zip_lambda(zip_file, project_dir=None):
    # zip project_dir and wrote to zip_file
    if project_dir:
        file_paths = [] 
    
        # crawling through directory and subdirectories 
        for root, directories, files in os.walk(project_dir): 
            for filename in files: 
                # join the two strings in order to form the full filepath. 
                filepath = os.path.join(root, filename) 
                arcname = os.path.join(root.replace(project_dir,''), filename) 
                file_paths.append({'file_path': filepath, 'arcname': arcname}) 

        print('Zipping following project files:') 
        for file_name in file_paths: 
            print(file_name['arcname']) 

        # writing files to a zipfile 
        with ZipFile(zip_file, 'w') as zip: 
            # writing each file one by one 
            for file in file_paths: 
                zip.write(file['file_path'], arcname=file['arcname']) # make arcname the correct path within the zipfile

    # open, return bytes
    with open(zip_file, 'rb') as infile:
        return infile.read()


def check_err(expression, err=Exception()):
    if expression:
        raise err


def resource_attribute(resource_name): 
    #return dict_dotval(live_resources, attr)
    return live_resources[resource_name]


def session_data(var):
    # TODO: make this smarter and add more data about active session... acct_id?  user who made change? date? stuff?
    if var == 'stage':
        return active_stage
    if var == 'account_id':
        return account_id


def force_bytes(string, encoding='utf-8'): #TODO might need to replace/rename/expand if we need to make more things into bytes...
    if isinstance(string, bytes): # string might already be bytes...
        return string

    return bytes(string, encoding)


def force_string(b, encoding='utf-8'): # TODO might need to replace/rename/expand if we need to make more things into strings...
    return b.decode(encoding)


def open_file(filename, prefix='@/infrastructure', f=file_bytes):
    return app._cloud_app__open_file(
            '/'.join([prefix, filename]),
            fopen=f,
            copy_forward=True
        )


def evaluate(string):
    functions = {
        'file': open_file,#file_bytes, #should this know that the file is in the infrastructure folder and automatically prepend that? 
        'string': force_string,
        'bytes': force_bytes,
        'resource': resource_attribute,
        'session': session_data,
        'eval': evaluate
    }
    #print('evaluating ', string)

    # if string is not actually a string (eg. int), don't evaluate
    if not isinstance(string, str):
        return string

    # find all expressions to evaluate
    pattern = r"\${[A-Za-z0-9.:'/_-]+}"
    try:
        matches = re.findall(pattern, string)
        for match in matches:
            actions, val = match[2:-1].split(':') #trim off the '${' and '}'
            
            if 'bytes' in actions: # TODO: we run into issues with substituting bytes objects into a string... this might not be the smartest way to handle this
                if len(matches) > 1:
                    raise ValueError("Bytes-like objects must evaluated alone.") # TODO: reword this error message

            if actions.split('.')[0] in ['resource']: # we might have other data accessors... vars?
                action, keys = actions.split('.', 1) 
                val = dict_dotval(functions[action](val), keys) # TODO: this feels hardcode-y
            else:
                for action in actions.split('.'): # execute list of actions one by one
                    val = functions[action](val)

            if 'bytes' in actions: # TODO: this seems too hardcode-y
                return val
            string = string.replace(match, val)

    except Exception as e:
        print(e)

    #print(string)
    return string


def template_item(item):
    # TODO: validate template item
    # TODO: evaluate vals that as needed
    keys = list(item.keys())
    key = keys[0] #TODO: make sure there is only 1!
    attr = item[key]['attributes']

    return key, fwalk_dict(attr, f=evaluate)


# def list_dir(directory):
#     for root, directories, files in os.walk(directory): 
#             for filename in files: 
#                 # join the two strings in order to form the full filepath. 
#                 yield os.path.join(root, filename).replace('\\', '/') 


############ First, create resources that need to be created ############
def create_resources(template, live_resources):
    # create iam roles
    print("creating iam roles")
    iam_roles = dict_wheres(template, ('service', 'iam'), ('type', 'role'))

    for role in iam_roles:
        name, attr = template_item(role)
        args = dict_select(attr, ['RoleName', 'AssumeRolePolicyDocument'])

        if name in live_resources.keys():
            print('-skipping', name)
        else:
            print('-creating', name)
            try:
                response = clients['iam'].create_role(**args)['Role']
            except Exception as e:
                print(e)
                print("create failed, rolling back deployment")
                sleep(15)
                #destroy_resources(live_resources, template)
                return False
        
            # we only need to keep RoleName, but we'll add arn just in case
            live_resources[name] = {
                'name': response['RoleName'],
                'arn': response['Arn']
            }
            save_live_resources(active_stage, live_resources)
    
    # create ddb
    print("creating ddb tables")
    tables = dict_wheres(template, ('service', 'dynamodb'), ('type', 'table'))

    for table in tables:
        name, attr = template_item(table)
        args = dict_select(attr, ['AttributeDefinitions', 'TableName', 'KeySchema', 'BillingMode'])

        if name in live_resources.keys():
            print('-skipping', name)
        else:
            print('-creating', name)
            try:
                response = clients['ddb'].create_table(**args)['TableDescription']
            except Exception as e:
                print(e)
                print("create failed, rolling back deployment")
                sleep(15)
                #destroy_resources(live_resources, template)
                return False
                #sys.exit(0)

            live_resources[name] = {
                    'name': response['TableName'],
                    'arn': response['TableArn']
                }
            save_live_resources(active_stage, live_resources) 
    
    # create lambda functions
    # TODO: Dead-letter queue

    ####### TEMPORARY FIX #######
    # Zip project files for upload... probably only need to do this for dev
    # TODO: probably move this to some kind of external utility that can be added to config as a custom action?
    lambda_functions = dict_wheres(template, ('service', 'lambda'), ('type', 'function'))
    if active_stage == 'dev':
        for function in lambda_functions:
            keys = list(function.keys())
            function_name = keys[0] #TODO: make sure there is only 1!
            zipfile = '../infrastructure/lambda/{}.zip'.format(function_name) # TODO: be smart about finding where this should go... SEE: greater file structure effort
            zip_lambda(zipfile, project_dir=function[function_name]['code_dir'])
    #############################

    print("creating lambda functions")
    lambda_functions = dict_wheres(template, ('service', 'lambda'), ('type', 'function'))

    #sleep(10) # needed to make sure iam roles created... TODO replace this with actually checking that they are created?

    for function in lambda_functions:
        name, attr = template_item(function)
        args = dict_select(attr, ['FunctionName', 'Runtime', 'Role', 'Handler', 'Code', 'Timeout', 'MemorySize', 'Publish']) #TODO: move timeout, memorysize to modify

        if name in live_resources.keys():
            print('-skipping', name)
        else:
            print('-creating', name)
            #print(args['Code'])
            #print(args['Role'])
            try:
                args['Role'] = dummy_role_arn # TODO: keep tabs on this bug and hoepfully get rid of this..
                response = try_retry(
                    clients['lambda'].create_function, 
                    args=args,
                    wait=2, 
                    fwait=lambda x: x * x
                )
                #response = clients['lambda'].create_function(**args)
            except Exception as e:
                print(e)
                print("create failed, rolling back deployment")
                sleep(15)
                #destroy_resources(live_resources, template)
                return False
                #sys.exit(0)

            live_resources[name] = {
                    'name': response['FunctionName'],
                    'arn': response['FunctionArn']
                }
            save_live_resources(active_stage, live_resources)

            sleep(1)

    
    # create api
    print("creating apis")
    # import apis from open_api files
    apis = dict_wheres(template, ('service', 'apigateway'), ('type', 'rest_api'), ('model', 'import'))

    ## create all apis that don't already exist and add the resulting details to the live_resources dict
    for api in apis:
        name, attr = template_item(api)
        args = dict_select(attr, ['body'])
        
        if name in live_resources.keys():
            print('-skipping', name)
        else:
            print('-creating', name)
            try:
                response = clients['apigateway'].import_rest_api(**args)
            except Exception as e:
                print(e)
                print("create failed, rolling back deployment")
                sleep(15)
                #destroy_resources(live_resources, template)
                return False
            
            live_resources[name] = {
                'id': response['id'],
                'name': response['name']
            }
            save_live_resources(active_stage, live_resources)
        
            sleep(1)


    # create any other apis manually
    apis = dict_wheres(template, ('service', 'apigateway'), ('type', 'rest_api'), ('model', 'default'))
    
    for api in apis:
        name, attr = template_item(api)
        args = dict_select(attr, ['name'])
        
        if name in live_resources.keys():
            print('-skipping', name)
        else:
            print('-creating', name)
            try:
                response = clients['apigateway'].create_rest_api(**args)
            except Exception as e:
                print(e)
                print("create failed, rolling back deployment")
                sleep(15)
                #destroy_resources(live_resources, template)
                return False
            
            live_resources[name] = {
                'id': response['id'],
                'name': response['name']
            }
            save_live_resources(active_stage, live_resources)

            sleep(5)
            # we need to get the resource ID for '/' path
            get_response = clients['apigateway'].get_resources(
                restApiId=response['id'],
            )

            live_resources[name]['/'] = get_response['items'][0] # TODO: we probably shouldnt assume that this will always be the only item... add logic to just get the '/' resource
            save_live_resources(active_stage, live_resources) 
        
            sleep(1)

    # add api resources
    api_resources = dict_wheres(template, ('service', 'apigateway'), ('type', 'api_resource'))

    for resource in api_resources:
        name, attr = template_item(resource)
        args = dict_select(attr, ['restApiId', 'parentId', 'pathPart'])
        
        if name in live_resources.keys():
            print('-skipping', name)
        else:
            print('-creating', name)
            try:
                response = try_retry(
                    clients['apigateway'].create_resource, 
                    args=args,
                    wait=2, 
                    fwait=lambda x: x * x
                )
                #response = clients['apigateway'].create_resource(**args)
            except Exception as e:
                print(e)
                print("create failed, rolling back deployment")
                sleep(15)
                #destroy_resources(live_resources, template)
                return False
            
            # TODO maybe add this as a nested subresource under the api?
            live_resources[name] = {
                'id': response['id'],
                'path': response['path'],
                'api_id': args['restApiId']
            }
            save_live_resources(active_stage, live_resources)

            # if cors, add an options method to resource_template
            if 'cors' in attr.keys():
                if attr['cors']:
                    live_resources['{}_CORS_OPTIONS'.format(name)] = add_cors(args['restApiId'], response['id'], response['path'], name)

        
            sleep(1)


    # add api methods
    api_methods = dict_wheres(template, ('service', 'apigateway'), ('type', 'api_method'))

    for method in api_methods:
        name, attr = template_item(method)
        args = dict_select(attr, ['restApiId', 'resourceId', 'httpMethod', 'authorizationType'])
        
        if name in live_resources.keys():
            print('-skipping', name)
        else:
            print('-creating', name)
            try:
                response = try_retry(
                    clients['apigateway'].put_method, 
                    args=args,
                    wait=2, 
                    fwait=lambda x: x * x
                )
                #response = clients['apigateway'].put_method(**args)
            except Exception as e:
                print(e)
                print("create failed, rolling back deployment")
                sleep(15)
                #destroy_resources(live_resources, template)
                return False
            
            # TODO maybe add this as a nested subresource under the api?
            resource = template[name]['attributes']['resource']
            live_resources[name] = {
                'http_method': response['httpMethod'],
                'path': live_resources[resource]['path'],
                'arn': 'arn:aws:execute-api:us-east-1:{account_id}:{api_id}/*/{http_method}{path}'.format(
                    account_id=account_id,
                    api_id=args['restApiId'],
                    http_method=response['httpMethod'],
                    path=re.sub(r'{.+}', '*', live_resources[resource]['path']) # handle path params
                ),
                'api_id': args['restApiId']
            }
            save_live_resources(active_stage, live_resources)

            # create method response
            if 'responses' in attr.keys():
                sleep(1)
                args = dict_select(attr, ['restApiId', 'resourceId', 'httpMethod', 'responses'])

                for res in args['responses']:
                    clients['apigateway'].put_method_response(
                        restApiId=args['restApiId'],
                        resourceId=args['resourceId'],
                        httpMethod=args['httpMethod'],
                        statusCode=res['statusCode'],
                        responseModels=res['models']
                    )

                    # not sure that we actually need to log anything here
                    # live_resources[name]['integration'] = args['integration']
                    # save_live_resources(active_stage, live_resources)

            # create integration
            if 'integration' in attr.keys():
                sleep(5)
                args = dict_select(attr, ['restApiId', 'resourceId', 'httpMethod', 'integration'])

                clients['apigateway'].put_integration(
                    restApiId=args['restApiId'],
                    resourceId=args['resourceId'],
                    httpMethod=args['httpMethod'],
                    integrationHttpMethod=args['httpMethod'],
                    type=args['integration']['type'],
                    uri=args['integration']['uri']
                )

                live_resources[name]['integration'] = args['integration']
                save_live_resources(active_stage, live_resources)
        
            sleep(1)

    # deploy API
    # need to deploy after creating the api, then again after modifying
    print("deploying api")

    apis = dict_wheres(template, ('service', 'apigateway'), ('type', 'rest_api'))

    for api in apis:
        name, attr = template_item(api)
        args = dict_select(attr, ['stageName'])
        args = {
            'restApiId': live_resources[name]['id'],
            **args
        }

        try:
            response = try_retry(
                clients['apigateway'].create_deployment, 
                args=args,
                wait=2, 
                fwait=lambda x: x * x
            )
            #response = clients['apigateway'].create_deployment(**args)
        except Exception as e:
            print(e)
            print("create failed, rolling back deployment")
            sleep(15)
            #destroy_resources(live_resources, template)
            return False
            #sys.exit(0)
    
        live_resources[name]['stage'] = args['stageName']
        live_resources[name]['deployment_id'] = response['id']
        save_live_resources(active_stage, live_resources)

        sleep(1)


    # create API usage plan
    print("creating api usage plan")

    usage_plans = dict_wheres(template, ('service', 'apigateway'), ('type', 'usage_plan'))

    for plan in usage_plans:
        name, attr = template_item(plan)
        args = dict_select(attr, ['name', 'apiStages', 'throttle', 'quota'])

        if name in live_resources.keys():
            print('-skipping', name)
        else:
            print('-creating', name)
            try:
                response = clients['apigateway'].create_usage_plan(**args)
            except Exception as e:
                print(e)
                print("create failed, rolling back deployment")
                sleep(15)
                #destroy_resources(live_resources, template)
                return False
                #sys.exit(0)
        
            live_resources[name] = {
                'id': response['id']
            }
            save_live_resources(active_stage, live_resources)

            sleep(1)

    # create cognito 
    print("creating cognito user pools")
    user_pools = dict_wheres(template, ('service', 'cognito'), ('type', 'user_pool'))

    for pool in user_pools:
        name, attr = template_item(pool)
        args = dict_select(attr, ['PoolName', 'Policies', 'LambdaConfig', 'UsernameConfiguration', 'Schema', 'AutoVerifiedAttributes', 'VerificationMessageTemplate']) #TODO: most of these are not mandatory for create and can be moved to modify...
        
        if name in live_resources.keys():
            print('-skipping', name)
        else:
            print('-creating', name)
            try:
                response = clients['cognito'].create_user_pool(**args)['UserPool']
            except Exception as e:
                print(e)
                print("create failed, rolling back deployment")
                sleep(15)
                #destroy_resources(live_resources, template)
                return False
                #sys.exit(0)

            # TODO: figure out what else i need to sace
            live_resources[name] = {
                'name': response['Name'],
                'arn': response['Arn'],
                'id': response['Id']
            }
            save_live_resources(active_stage, live_resources)

        sleep(1)

    ####### TEMPORARY FIX #######
    # write to external files as needed
    # TODO: move this to some kind of external utility
    print("updating external files")
    external_file('../infrastructure/external_files/kanban_prod_env') # TODO: be smart about finding where this should go... SEE: greater file structure effort
    print("building web-app")
    os.system('cd ../kanban && npm run build && cd ../infrastructure')
    #############################

    # create s3 buckets
    print("creating s3 buckets")
    buckets = dict_wheres(template, ('service', 's3'), ('type', 'bucket'))

    for bucket in buckets:
        name, attr = template_item(bucket)
        args = dict_select(attr, ['Bucket'])

        if name in live_resources.keys():
            print('-skipping', name)
        else:
            print('-creating', name)
            try:
                response = clients['s3'].create_bucket(**args)
            except Exception as e:
                print(e)
                print("create failed, rolling back deployment")
                sleep(15)
                #destroy_resources(live_resources, template)
                return False
        
            # we only need to keep RoleName, but we'll add arn just in case
            live_resources[name] = {
                'name': args['Bucket'],
                'region': response['Location'],
                'arn': 'arn:aws:s3:::{}'.format(args['Bucket'])
            }
            save_live_resources(active_stage, live_resources)

        sleep(1)

    # create s3 objects
    print("creating s3 objects")
    objects = dict_wheres(template, ('service', 's3'), ('type', 'object'))

    for obj in objects:
        name, attr = template_item(obj)
        args = dict_select(attr, ['Bucket', 'source', 'prefix'])

        # iterate over list of files in source path
        source_paths = [args['source']] 
        if(args['source'][-1] == '/'):  #if source is a dir, the overwrite
            source_paths = list(list_dir(args['source']))

        live_resources[name] = {
                'bucket': args['Bucket'],
                'keys': live_resources[name]['keys'] if name in live_resources.keys() else []
            }

        for path in source_paths:
            key = "{prefix}/{suffix}".format(prefix=args['prefix'], suffix=path.split(args['source'], 1)[-1]) if args['prefix'] else path.split(args['source'], 1)[-1]
            
            ############## TEMPORARY FIX ##############
            metadata_lookup = { 
                'js': 'application/javascript',
                'html': 'text/html',
                'css': 'text/css',
                'png': 'image/png',
                'gz': 'application/javascript'
            }
            ###########################################

            if key in live_resources[name]['keys']:
                print('-skipping', key) 
            else:
                print('-creating', key)
                try:                    
                    response = clients['s3'].put_object(
                        Bucket=args['Bucket'],
                        Body=file_obj(path),
                        Key=key,
                        ContentType=metadata_lookup[key.split('.')[-1]]
                    )
                except Exception as e:
                    print(e)
                    print("create failed, rolling back deployment")
                    sleep(15)
                    #destroy_resources(live_resources, template)
                    return False
            
                # we only need to keep RoleName, but we'll add arn just in case
                live_resources[name]['keys'].append(key)
                save_live_resources(active_stage, live_resources)

            #sleep(1)

    # create iam policies
    print("creating iam policies")
    # TODO: move to json
    # TODO: rework aws managed policies

    ## get all AWS managed policies in case those are needed
    aws_policies = clients['iam'].list_policies(
        Scope='AWS',
        MaxItems=1000
        )['Policies']

    iam_policies = dict_wheres(template, ('service', 'iam'), ('type', 'policy'))

    ## create all policies that don't already exist and add the resulting details to the live_resources dict
    for policy in iam_policies:
        name, attr = template_item(policy)
        args = dict_select(attr, ['PolicyName', 'PolicyDocument'])
        
        if name in live_resources.keys():
            print('-skipping', name)
        else:
            print('-creating', name)
            # if not AWS managed, create.  else get from list of aws managed
            if policy_doc := safe_dict_val(args, 'PolicyDocument'): # TODO: throw error if AWS managed AND gave policy doc
                check_err(
                    policy_doc and list_where(aws_policies, 'PolicyName', args['PolicyName']),
                    err=Exception("Cannot provide a PolicyDocument for an AWS Managed Policy")
                )
                #if args['PolicyDocument']:
                try:
                    response = clients['iam'].create_policy(**args)['Policy']
                except Exception as e:
                    print(e)
                    print("create failed, rolling back deployment")
                    sleep(15)
                    #destroy_resources(live_resources, template)
                    return False
                    #sys.exit(0)
            else:
                response = list_where(aws_policies, 'PolicyName', args['PolicyName']) #aws_policies[args['PolicyName']]

            # Need ARN and name
            live_resources[name] = {
                'name': response['PolicyName'],
                'arn': response['Arn']
            }
            save_live_resources(active_stage, live_resources)
    
            sleep(1)

    # create cloudfont distributions
    print("creating cloudfront distributions")
    cf_distros = dict_wheres(template, ('service', 'cloudfront'), ('type', 'distribution'))

    ## create all distributions that don't already exist and add the resulting details to the live_resources dict
    for distros in cf_distros:
        name, attr = template_item(distros)
        args = dict_select(attr, ['description', 'default_root', 'origins', 'default_origin', 'cache_behaviors', 'custom_errors', 'enabled'])
        
        if name in live_resources.keys():
            print('-skipping', name)
        else:
            print('-creating', name)
            distro = distribution(session, name=name, attributes=attr)

            build_queue = distro.build()
            try:
                for resource_data in build_queue:
                    # print(resource_data)
                    #live_resources = { **live_resources, **resource_data }  #this doesnt work?
                    live_resources[name] = distro.live_data()[name]
                    save_live_resources(active_stage, live_resources)
            except DependecyNotMetError as e:
                print('aws.resources.resources.DependecyNotMetError')
                print (e)
                sys.exit(0)
                
    return True


############ next, update resources as needed ############
def modify_resources(template, live_resources):
    # TODO: do we want to rollback on failed modify?  probably yes, but not a full delete...
    # attach iam policies
    print("attaching iam policies")
    iam_roles = dict_wheres(template, ('service', 'iam'), ('type', 'role'))

    for role in iam_roles:
        name, attr = template_item(role)

        #policies = attr['policies']
        for policy_name in attr['policies']:
            response = clients['iam'].attach_role_policy(
                RoleName=live_resources[name]['name'],
                PolicyArn=live_resources[policy_name]['arn']
            )

        # I don't think we need to add anything else to live_resources?
        # live_resources[name] = {
        #     'RoleName': response['RoleName'],
        #     'Arn': response['Arn']
        # }

    # modify s3 buckets
    # configure bucket website
    print("configuring bucket website")
    buckets = dict_wheres(template, ('service', 's3'), ('type', 'bucket'))

    for bucket in buckets:
        name, attr = template_item(bucket)

        args = dict_select(attr, ['Bucket', 'WebsiteConfiguration'])
        #policies = attr['policies']
        response = clients['s3'].put_bucket_website(**args)

        # TODO: get region?
        live_resources[name]['website'] = 'http://{}.s3-website-us-east-1.amazonaws.com'.format(live_resources[name]["name"])

    # modify s3 objects
    # put object ACL
    print("putting object acl")
    buckets = dict_wheres(template, ('service', 's3'), ('type', 'object'))

    for bucket in buckets:
        name, attr = template_item(bucket)

        args = dict_select(attr, ['Bucket', 'GrantRead'])
        #policies = attr['policies']
        for key in live_resources[name]['keys']:
            response = clients['s3'].put_object_acl(
                **args,
                Key=key
                )

        #live_resources[name]['website'] = 'http://{}.s3-website-us-east-1.amazonaws.com'.format(live_resources[name]["name"])


    # modify ddb
    # TODO: this might be were any seeding/restoring is done
    # update table
    ##### for now just adding GSI... might need more?
    # TODO: re-evaluate GSI...
    # TODO: not actually modifying anything here...
    print("modifying ddb tables")
    tables = dict_wheres(template, ('service', 'dynamodb'), ('type', 'table'))

    for table in tables:
        name, attr = template_item(table)
        args = attr

        print('-updating', name)
        try:
            response = clients['ddb'].update_table(**args)['TableDescription']
        except:
            print("modify ddb table {} failed".format(name))
            sleep(1)
            #destroy_resources(live_resources, template)
            #return False
            #sys.exit(0)

        # not sure what actually needs to be saved
        # live_resources[name] = {
        #         'name': response['TableName'],
        #         'arn': response['TableArn']
        #     }

        sleep(1)

    # modify cognito (needs to be before lambda, lambda needs the user pool client id)
    print("creating cognito app clients")
    user_pools = dict_wheres(template, ('service', 'cognito'), ('type', 'user_pool'))

    for pool in user_pools:
        name, attr = template_item(pool)
        args = dict_select(attr, ['ClientName', 'GenerateSecret', 'ExplicitAuthFlows'])
        args['UserPoolId'] = live_resources[name]['id']

        print('-updating', name)
        try:
            response = clients['cognito'].create_user_pool_client(**args)['UserPoolClient']
        except Exception as e:
            print(e)
            print("create failed, rolling back deployment")
            sleep(15)
            #destroy_resources(live_resources, template)
            #return False
            #sys.exit(0)

        # not sure what actually needs to be saved
        live_resources[name]['app_client_id'] = response['ClientId']
        save_live_resources(active_stage, live_resources)

        sleep(1)

    print("creating cognito user pool domains")
    user_pools = dict_wheres(template, ('service', 'cognito'), ('type', 'user_pool'))
    for pool in user_pools:
        name, attr = template_item(pool)
        args = dict_select(attr, ['Domain'])
        args['UserPoolId'] = live_resources[name]['id']

        print('-updating', name)
        try:
            response = clients['cognito'].create_user_pool_domain(**args)
        except Exception as e:
            print(e)
            print(args)
            print("create failed, rolling back deployment")
            sleep(15)
            #destroy_resources(live_resources, template)
            #return False
            #sys.exit(0)

        # not sure what actually needs to be saved
        live_resources[name]['domain'] = args['Domain']
        save_live_resources(active_stage, live_resources)

        sleep(1)

    # modify lambda
    # update function code
    print("updating lambda function code")

    lambda_functions = dict_wheres(template, ('service', 'lambda'), ('type', 'function'))

    for function in lambda_functions:
        name, attr = template_item(function)
        args = dict_select(attr, ['FunctionName', 'Publish'])
        args['ZipFile'] = attr['Code']['ZipFile'] # TODO: rework how code is handled...  this is too hard-codey and assumes that users ONLY use zipfile

        print('-updating', name)
        try:
            response = clients['lambda'].update_function_code(**args)
        except Exception as e:
            print(e)
            print("create failed, rolling back deployment")
            sleep(15)
            #destroy_resources(live_resources, template)
            #return False
            #sys.exit(0)

    # update function configuration
    print("updating lambda function configuration")

    lambda_functions = dict_wheres(template, ('service', 'lambda'), ('type', 'function'))

    for function in lambda_functions:
        name, attr = template_item(function)
        try:
            args = dict_select(attr, ['FunctionName', 'Environment', 'Role'])
        except:
            # if we don't have the needed args, just skip 
            # TODO: make smarter
            continue

        print('-updating', name)
        try:
            response = clients['lambda'].update_function_configuration(**args)
        except Exception as e:
            print(e)
            print("create failed, rolling back deployment")
            sleep(15)
            #destroy_resources(live_resources, template)
            #return False
            #sys.exit(0)


    # Add permissions as needed
    print("updating lambda resource-based permissions")


    lambda_functions = dict_wheres(template, ('service', 'lambda'), ('type', 'function'))

    for function in lambda_functions:
        name, attr = template_item(function)
        try:
            args = dict_select(attr, ['FunctionName'])
            args = { **args, **dict_select(attr['permissions'], ['StatementId', 'Action', 'Principal', 'SourceArn']) } # TODO: what if we need to add more than one permission?
        except Exception as e:
            # if we don't have the needed args, just skip 
            # TODO: make smarter
            print(e)
            continue

        print('-updating', name)
        try:
            response = clients['lambda'].add_permission(**args)
        except Exception as e:
            print(e) # TODO handle different errors differently... ResourceConflictException means permission already exists.  either skip because this si fine, or delete then readd?
            print("adding permission {} to {} failed, continuing".format(args['StatementId'], name))
            sleep(1)
            #destroy_resources(live_resources, template)
            #return False
            #sys.exit(0)

    # modify api
    # deploy API
    # copypasta from create
    print("deploying api")

    apis = dict_wheres(template, ('service', 'apigateway'), ('type', 'rest_api'))

    for api in apis:
        name, attr = template_item(api)
        args = dict_select(attr, ['stageName'])
        args = {
            'restApiId': live_resources[name]['id'],
            **args
        }

        print('-updating', name)
        try:
            response = clients['apigateway'].create_deployment(**args)
        except Exception as e:
            print(e)
            print("create failed, rolling back deployment")
            sleep(15)
            #destroy_resources(live_resources, template)
            return False
            #sys.exit(0)
        
        live_resources[name]['stage'] = args['stageName']
        live_resources[name]['deployment_id'] = response['id']
        save_live_resources(active_stage, live_resources)

        sleep(1)


############ destroy resources ############
def destroy_resources(resources, template):
    # delete lambda
    ###################################
    # TEMPORARY FIX
    lambda_functions = [
        'api_idea_get_lambda',
        'api_idea_put_lambda',
        'api_idea_edit_lambda',
        'api_category_get_lambda',
        'api_category_put_lambda',
        'api_category_edit_lambda',
        'api_user_add_lambda',
        'backend_user_add_record_lambda'
    ]

    lambda_functions = [list(k.keys())[0] for k in dict_wheres(template, ('service', 'lambda'), ('type', 'function'))]

    to_delete = []
    for name in lambda_functions:
        if name in resources.keys():
            to_delete.append(name)
    ###################################
    
    for name in to_delete:
        print("deleting", name)
        clients['lambda'].delete_function(
            FunctionName=live_resources[name]['name']
        )

        live_resources.pop(name, None)
        save_live_resources(active_stage, live_resources)

    # delete api
    ###################################
    # TEMPORARY FIX
    apis = [
        'ideaverse_api'
    ]

    apis = [list(k.keys())[0] for k in dict_wheres(template, ('service', 'apigateway'), ('type', 'rest_api'))]

    to_delete = []
    for name in apis:
        if name in resources.keys():
            to_delete.append(name)
    ###################################
    
    for name in to_delete:
        print("deleting", name)
        retries = 0
        sleep_time = 5
        while retries < 5:
            try:
                response = clients['apigateway'].delete_rest_api(
                    restApiId=live_resources[name]['id']
                )
                retries = 9001
            except:
                print('Failed, retrying in {} seconds'.format(sleep_time))
                sleep_time *= 2
                retries += 1


        # also need to remove subresources that are automatically deleted
        subresources = [list(k.keys())[0] for k in dict_wheres(live_resources, ('api_id', live_resources[name]['id']))]
        for sub in subresources:
            live_resources.pop(sub, None)

        live_resources.pop(name, None)
        
        save_live_resources(active_stage, live_resources)

    # delete usage plan
    ###################################
    # TEMPORARY FIX
    usage_plans = [list(k.keys())[0] for k in dict_wheres(template, ('service', 'apigateway'), ('type', 'usage_plan'))]

    to_delete = []
    for name in usage_plans:
        if name in resources.keys():
            to_delete.append(name)
    ###################################
    
    for name in to_delete:
        print("deleting", name)
        response = clients['apigateway'].delete_usage_plan(
            usagePlanId=live_resources[name]['id']
        )

        live_resources.pop(name, None)
        save_live_resources(active_stage, live_resources)

    # delete api keys
    # TODO: need to clean up api keys


    # delete cognito user pools
    # TODO: need to delete any attached domains
    ###################################
    # TEMPORARY FIX
    user_pools = [
        'cognito_user_pool'
    ]

    user_pools = [list(k.keys())[0] for k in dict_wheres(template, ('service', 'cognito'), ('type', 'user_pool'))]

    to_delete = []
    for name in user_pools:
        if name in resources.keys():
            to_delete.append(name)
    ###################################
    
    for name in to_delete:
        print("deleting", name)
        try:
            response = clients['cognito'].delete_user_pool_domain(
                UserPoolId=live_resources[name]['id'],
                Domain=live_resources[name]['domain'],
            )
        except Exception as e:
            print(e)
        sleep(10)
        response = clients['cognito'].delete_user_pool(
            UserPoolId=live_resources[name]['id']
        )

        live_resources.pop(name, None)
        save_live_resources(active_stage, live_resources)

    # delete iam roles
    ###################################
    # TEMPORARY FIX
    iam_roles = [
        'lambda_ddb_write_role',
        'lambda_ddb_read_role',
        'lambda_cognito_read_write_role'
    ]

    iam_roles = [list(k.keys())[0] for k in dict_wheres(template, ('service', 'iam'), ('type', 'role'))]

    to_delete = []
    for name in iam_roles:
        if name in resources.keys():
            to_delete.append(name)
    ###################################

    for name in to_delete:
        print("deleting", name)
        # get all attached policies
        attached_policies = clients['iam'].list_attached_role_policies(
            RoleName=live_resources[name]['name']
        )['AttachedPolicies']

        # detach policies
        for policy in attached_policies:
            response = clients['iam'].detach_role_policy(
                RoleName=live_resources[name]['name'],
                PolicyArn=policy['PolicyArn']
            )

            sleep(1)

        # delete roles
        clients['iam'].delete_role(
            RoleName=live_resources[name]['name']
        )

        live_resources.pop(name, None)
        save_live_resources(active_stage, live_resources)

    # delete iam policies
    ###################################
    # TEMPORARY FIX
    iam_policies = [
        'ddb_fullaccess_policy',
        'ddb_readonly_policy',
        'lambda_basic_execution_policy',
        'cognito_poweruser_policy'
    ]

    iam_policies = [list(k.keys())[0] for k in dict_wheres(template, ('service', 'iam'), ('type', 'policy'))]

    to_delete = []
    for name in iam_policies:
        if name in resources.keys():
            to_delete.append(name)
    ###################################

    for name in to_delete:
        try: #TODO: right now we are hoping that the only reason why this fails is that the policy is AWS Managed... need to make this smarter
            response = clients['iam'].delete_policy(
                PolicyArn=live_resources[name]['arn']
            )
        except:
            pass
        
        live_resources.pop(name, None)
        save_live_resources(active_stage, live_resources)

    # delete ddb
    ###################################
    # TEMPORARY FIX
    tables = [
        'ideas_db'
    ]

    tables = [list(k.keys())[0] for k in dict_wheres(template, ('service', 'dynamodb'), ('type', 'table'))]

    to_delete = []
    for name in tables:
        if name in resources.keys():
            to_delete.append(name)
    ###################################

    for name in to_delete:
        print("deleting", name)
        clients['ddb'].delete_table(
            TableName=live_resources[name]['name']
        )

        live_resources.pop(name, None)
        save_live_resources(active_stage, live_resources)

    # delete s3 objects
    ###################################
    # TEMPORARY FIX
    objects = [list(k.keys())[0] for k in dict_wheres(template, ('service', 's3'), ('type', 'object'))]

    to_delete = []
    for name in objects:
        if name in resources.keys():
            to_delete.append(name)
    ###################################
    
    for name in to_delete:
        for key in live_resources[name]['keys']:
            print("deleting", key)
            response = clients['s3'].delete_object(
                Bucket=live_resources[name]['bucket'],
                Key=key
            )

        live_resources.pop(name, None)
        save_live_resources(active_stage, live_resources)

    # delete s3 buckets
    ###################################
    # TEMPORARY FIX
    buckets = [list(k.keys())[0] for k in dict_wheres(template, ('service', 's3'), ('type', 'bucket'))]

    to_delete = []
    for name in buckets:
        if name in resources.keys():
            to_delete.append(name)
    ###################################
    
    #TODO: if bucket still not empty, get list of remaining items, allow user to review and delete or cancel
    for name in to_delete:
        print("deleting", name)
        response = clients['s3'].delete_bucket(
            Bucket=live_resources[name]['name']
        )

        live_resources.pop(name, None)
        save_live_resources(active_stage, live_resources)


# load resource data
def resource_template(stage, config):
    # open resource_template file
    # We always open the resource_template from the previous stage (eg. changes flow from master > dev > qa > prod)
    template_filename = 'resource_template.json'

    try:
        template_raw = file_json(template_filename)
        print('opening {} resource template'.format(template_filename))
    except Exception as e:
        print(e)
        print('failed to open {} resource template'.format(template_filename))
        exit(1)
    
    return template_raw


def update_live_resource(stage, resource, *attr):
    live_resources = {}
    try:
        live_resources = file_json('{stage}/resources.json'.format(stage=stage), copy=False)
    except:
        print('failed to access {} resource file'.format(live_resource_filepaths[stage]))
        return {} # TODO: exit ?

    if resource not in live_resources.keys():
        live_resources[resource] = {}


def save_live_resources(stage, resource_dict):
    out_path = '../.cabbie/{stage}/resources.json'.format(stage=stage)
    with open(out_path, 'w') as outfile:
        outfile.write(json.dumps(resource_dict, indent=4))

# try:
#     live_resources = file_json('resources.json'.format(stage=active_stage), copy=False)
#     print('opening {} resource file'.format(live_resource_filepaths[active_stage]))
# except Exception as e:
#     print(e)
#     print('failed to open {} resource file'.format(live_resource_filepaths[active_stage]))

# TODO: can use other response items for tracking?

try:
    delete_dummy_lambda_role()
except:
    pass

dummy_role_arn = create_dummy_lambda_role()

if __name__ == '__main__':
    new_process = True
    
    if new_process:
        #### NEW ####
        app = cloud_app(active_stage)

        if not destroy:
            app.build()
        else:
            app.destroy()

    else:
        #### OLD ####
        stage_template = app.resource_template

        if rebuild:
            destroy_resources(live_resources, stage_template)
            sleep(10)
        
        if not destroy:
            print("deploying {} to {}".format(active_stage, account_id))
            success = create_resources(stage_template, live_resources)
            if success:
                modify_resources(stage_template, live_resources)
        else:
            destroy_resources(live_resources, stage_template)

    
        delete_dummy_lambda_role()

        # write resources to file
        save_live_resources(active_stage, live_resources)


