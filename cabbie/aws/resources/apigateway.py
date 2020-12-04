# TODO: maybe rename? we called this lmbda to avoid conflict with lambda reserved word

from .resources import resource
from .resources import DependecyNotMetError


SERVICE = 'apigateway'

# function

class function(resource):


    def __init__(self, session, name='', attributes={}, resource_template={}, live_data={}, plugins={}, verbose=False):
        super().__init__(
            session,
            SERVICE,
            name=name, 
            attributes=attributes, 
            resource_template=resource_template, 
            live_data=live_data,
            verbose=verbose
        )


    def init_build_actions(self):
        """processes the saved resource template and returns build actions, args"""
        return [
            {
                'execution': ( self.__create_function, ['name', 'runtime', 'role', 'handler', 'code', 'timeout', 'memory', 'publish'] ),
                'complete': False
            }
        ]


    def init_update_actions(self):
        """processes the saved resource template and returns update actions, args"""
        actions = [
            {
                'execution': ( self.__update_code, ['name', 'code', 'publish']),
                'complete': False
            },
            {
                'execution': ( self.__update_config, ['name', 'role', 'runtime', 'handler', 'timeout', 'memory', 'environment_variables']),
                'complete': False
            },
            {
                'execution': ( self.__add_permissions, ['name', 'permissions']),
                'complete': False
            }
        ]
        
        # if safe_dict_val(self.__resource_template, 'update_mode', default='default'):
        #     actions = self.__init_destroy_actions() + self.__init_build_actions()

        actions += []
        
        return actions


    def init_destroy_actions(self):
        """processes the saved resource data and returns destroy actions, args"""
        return [
            {
                'execution': ( self.__delete_function, []),
                'complete': False
            }
        ]


    def init_live_data(self):
        return {
            'name': ''
        }


    # custom method for finding orphaned resources
    @classmethod
    def list_resources(cls, session=None):
        """yields a generator of all resources of this type that exist in the aws account"""
        client = session.client(SERVICE)

        policies = client.list_policies(
            Scope='Local',
            MaxItems=1000 # TODO: paginate?
        )['Policies'] # we only care about customer managed policies

        for policy in policies:
            yield cls(
                session,
                name=policy['PolicyName'],
                live_data={
                    'name': policy['PolicyName'],
                    'arn': policy['Arn']
                }
            )

    # custom functions to be called in build, update, destroy
    def __create_function(self, name, runtime, role, handler, code, timeout, memory, publish):
        # TODO: make publish, timeout, memorysize optional

        args = {
            'FunctionName': name,
            'Runtime': runtime,
            'Role': role,
            'Handler': handler,
            'Code': {
                'ZipFile': code # TODO: add options for s3, github, etc...  probably not s3, maybe add a plugin for github?
            }, 
            'Timeout': timeout,
            'MemorySize': memory,
            'Publish': publish
        }

        response = self.client.create_function(**args) # TODO: if we get an error about the IAM role, raise dependency error

        #return self.live_data

        return {
            'name': response['FunctionName'],
            'arn': response['FunctionArn']
        }

    
    def __update_config(self, name, role, runtime, handler, timeout, memory, environment_variables):
        args = {
            'FunctionName': name,
            'Role': role,
            'Handler': handler,
            'Timeout': timeout,
            'MemorySize': memory,
            'Environment': {
                'Variables': environment_variables
            },
            'Runtime': runtime
        }

        response = self.client.update_function_configuration(**args)

        #return self.live_data

        return {
            'aws_managed': True if response else False,
            'name': response['FunctionName'],
            'arn': response['FunctionArn']
        }

    
    def __update_code(self, name, code, publish):

        args = {
            'FunctionName': name,
            'ZipFile': code,
            'Publish': publish
        }

        response = self.client.update_function_code(**args)

        #return self.live_data

        return {}

    
    def __add_permissions(self, name, permissions):

        for permission in permissions:
            args = {
                'FunctionName': name,
                'StatementId': permission['sid'], #TODO should we automate this?  do i need to make people provide this?  i feel like ideally cabbie shoul dknow if identical positions already exist and then add or not based on that, not an SID
                'Action': permission['action'],
                'Principal': permission['principal'],
                'SourceArn': permission['source_arn'],
            }

            response = self.client.add_permission(**args)

        #return self.live_data

        return { }


    def __delete_function(self):
        # response = self.__client.delete_bucket(
        #     Bucket=self.__live_data['name']
        # )
        response = self.client.delete_function(
            FunctionName=self.live_data['name']
        )

        # TODO: if bucketnotempty err, raise DependecyNotMetError()
        
        return {}
