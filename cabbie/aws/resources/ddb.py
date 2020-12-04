from .resources import resource
from .resources import DependecyNotMetError

from common.dicts import list_where_2

SERVICE = 'dynamodb'

# policy

class table(resource):


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
                'execution': ( self.__create_table, ['attributes', 'name', 'keys', 'billing_mode'] ),
                'complete': False
            }
        ]


    def init_update_actions(self):
        """processes the saved resource template and returns update actions, args"""
        actions = []
        
        # if safe_dict_val(self.__resource_template, 'update_mode', default='default'):
        #     actions = self.__init_destroy_actions() + self.__init_build_actions()

        actions += [
            {
                'execution': ( self.__update_table, ['attributes', 'name', 'billing_mode'] ),
                'complete': False
            }
        ]
        
        return actions


    def init_destroy_actions(self):
        """processes the saved resource data and returns destroy actions, args"""
        return [
            {
                'execution': ( self.__delete_table, []),
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

    def __create_table(self, name, attributes, keys, billing_mode):

        # map attributes to AttributeDefinitions
        type_mapping = {
            'string': 'S',
            'number': 'N',
            'binary': 'B'
        }

        mapped_attr = []
        for attr in attributes:
            mapped_attr.append({
                'AttributeName': attr['name'],
                'AttributeType': type_mapping[attr['type']]
            })
        
        # map keys to KeySchema
        key_mapping = {
            'primary': 'HASH',
            'sort': 'RANGE'
        }

        mapped_keys = []
        for key in keys:
            mapped_keys.append({
                'AttributeName': key['name'],
                'KeyType': key_mapping[key['type']]
            })

        # map billing_mode to BillingMode 'PROVISIONED'|'PAY_PER_REQUEST'
        billingmode_mapping = {
            'provisioned': 'PROVISIONED',
            'on_demand': 'PAY_PER_REQUEST'
        }

        args = {
            'AttributeDefinitions': mapped_attr,
            'TableName': name,
            'KeySchema': mapped_keys,
            'BillingMode': billingmode_mapping[billing_mode]
        }
        response = self.client.create_table(**args)

        #return self.live_data

        return {
            'name': response['TableDescription']['TableName'],
            'arn': response['TableDescription']['TableArn']
        }


    def __update_table(self, name, attributes, billing_mode):

        # map attributes to AttributeDefinitions
        type_mapping = {
            'string': 'S',
            'number': 'N',
            'binary': 'B'
        }

        mapped_attr = []
        for attr in attributes:
            mapped_attr.append({
                'AttributeName': attr['name'],
                'AttributeType': type_mapping[attr['type']]
            })
        
        # map billing_mode to BillingMode 'PROVISIONED'|'PAY_PER_REQUEST'
        billingmode_mapping = {
            'provisioned': 'PROVISIONED',
            'on_demand': 'PAY_PER_REQUEST'
        }

        args = {
            'AttributeDefinitions': mapped_attr,
            'TableName': name,
            'BillingMode': billingmode_mapping[billing_mode]
        }

        try:
            response = self.client.update_table(**args)
        except self.client.exceptions.ResourceInUseException as e:
            raise DependecyNotMetError

        #return self.live_data

        return {
            'name': response['TableDescription']['TableName'],
            'arn': response['TableDescription']['TableArn']
        }


    def __delete_table(self):
        response = self.client.delete_table(
            TableName=self.live_data['name']
        )
        
        return {}
