from .resources import resource
from .resources import DependecyNotMetError

from common.dicts import list_where_2

SERVICE = 'iam'

# policy

class policy(resource):


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
                'execution': ( self.__create_policy, ['name', 'policy_document'] ),
                'complete': False
            }
        ]


    def init_update_actions(self):
        """processes the saved resource template and returns update actions, args"""
        actions = []
        
        # if safe_dict_val(self.__resource_template, 'update_mode', default='default'):
        #     actions = self.__init_destroy_actions() + self.__init_build_actions()

        actions += []
        
        return actions


    def init_destroy_actions(self):
        """processes the saved resource data and returns destroy actions, args"""
        return [
            {
                'execution': ( self.__delete_policy, []),
                'complete': False
            }
        ]


    def init_live_data(self):
        return {}


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
    def __aws_managed_policies(self):
        return self.client.list_policies(
            Scope='AWS',
            MaxItems=1000
        )['Policies']

    def __create_policy(self, name, policy_document):
        # get list of aws managed policies
        aws_managed_policies = self.__aws_managed_policies()

        # check if this is an AWS managed policy
        response = list_where_2(aws_managed_policies, 'PolicyName', name)

        if response and policy_document: 
            # its an aws policy, we shouldnt have been given a policy doc
            raise Exception("Cannot provide a PolicyDocument for an AWS Managed Policy")
        if not response and not policy_document:
            # if no policy document given, it should be an aws policy, but not in aws_policies so err
            raise Exception("AWS Managed Policy {} not found.  If this is not an AWS Managed Policy, please provide a valid policy document".format(name))
        elif policy_document: 
            # if not in aws_managed_policies and we have policy_doc, then create
            response = self.client.create_policy(
                PolicyName=name,
                PolicyDocument=policy_document
            )['Policy']

        #return self.live_data

        return {
            'aws_managed': True if response else False,
            'name': response['PolicyName'],
            'arn': response['Arn']
        }


    def __delete_policy(self):
        # response = self.__client.delete_bucket(
        #     Bucket=self.__live_data['name']
        # )
        try:
            if not self.live_data['aws_managed']:
                response = self.client.delete_policy(
                    PolicyArn=self.live_data['arn']
                )
        except self.client.exceptions.DeleteConflictException as e:
            raise DependecyNotMetError
            

        # TODO: if bucketnotempty err, raise DependecyNotMetError()
        
        return {}

# role

class role(resource):


    def __init__(self, session, name='', attributes={}, resource_template={}, live_data={}, verbose=False):
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
                'execution': ( self.__create_role, ['name', 'trust_policy'] ), 
                'complete': False
            }
        ]


    def init_update_actions(self):
        """processes the saved resource template and returns update actions, args"""
        return [
            {
                'execution': ( self.__attach_policies, ['name', 'policies'] ), 
                'complete': False
            }
        ]


    def init_destroy_actions(self):
        """processes the saved resource data and returns destroy actions, args"""
        return [
            {
                'execution': ( self.__detach_policies, ['name'] ),
                'complete': False
            },
            {
                'execution': ( self.__delete_role, ['name'] ),
                'complete': False
            }
        ]


    def init_live_data(self):
        return {
            #'policies': []
        }


    # custom method for finding orphaned resources
    @classmethod
    def list_resources(cls, session=None):
        """yields a generator of all resources of this type that exist in the aws account"""
        client = session.client(SERVICE)

        roles = client.list_policies(
            MaxItems=1000 # TODO: paginate?
        )['Roles'] # we only care about customer managed policies

        for role in roles:
            yield cls(
                session,
                name=role['PolicyName'],
                live_data={
                    'name': response['RoleName'],
                    'arn': response['Arn']
                }
            )


    # custom functions to be called in build, update, destroy
    def __create_role(self, name, trust_policy):
        # TODO: allow users to give a list of services/entities, and we build the trust doc for them

        # iterate over list of files in source path
        response = self.client.create_role(
            RoleName=name,
            AssumeRolePolicyDocument=trust_policy
        )

        # self.live_data = { # TODO: come up with a way to template-ize this?
        #     'name': bucket,
        #     'region': response['Location'], # TODO doesnt actually work
        #     'arn': 'arn:aws:s3:::{}'.format(bucket)
        # }

        # return self.live_data

        return {
            'name': response['Role']['RoleName'],
            'arn': response['Role']['Arn']
        }


    def __attach_policies(self, name, policies):
        """
            "policies": [
                "${resource.arn:lambda_basic_execution_iam_policy}",
                "${resource.arn:cognito_poweruser_iam_policy}"
            ],
        """

        for policy_arn in policies:
            response = self.client.attach_role_policy(
                RoleName=name,
                PolicyArn=policy_arn
            )

            #self.live_data['policies'].append(
            #    policy_arn
            #)

        #return self.live_data
        

        return {} # Nothing new to return


    def __delete_role(self, name):
        try:
            response = self.client.delete_role(
                RoleName=name
            )
        except self.client.exceptions.DeleteConflictException as e: # TODO: do i actually want this?
            raise DependecyNotMetError

        return {}


    def __detach_policies(self, name):
        # TODO probably just set this up to list attached policies then remove them all.  We can then re-add as needed.
        policies = self.client.list_attached_role_policies(
            RoleName=name
        )['AttachedPolicies']

        print(policies)

        for policy in policies:
            response = self.client.detach_role_policy(
                RoleName=name,
                PolicyArn=policy['PolicyArn']
            )

        return {}

