"""
General flow:  We open up the resource_template.json in the main method.  For each resource, create a
corresponding resource object and add to the build queue, modify queue.  attempt to build one by one.  if
dependecies not met, throw error.  catch error, move to back of queue.  repeat for modify.
"""

import boto3
from random import getrandbits


from .resources import dependency
from common.dicts import dict_select
from common.dicts import dict_dotval


# TODO: come up with a way to template-ize functions?
# TODO: add verbose print statements
# TODO: add option to re-up session/client when calling build/update/destroy
# TODO: modify should create invalidation

SERVICE = 'cloudfront'

# bucket

class distribution:


    def __init__(self, session, name='', attributes={}, resource_template={}, live_data={}, verbose=False):
        self.__name = name
        self.__resource_template = resource_template
        self.__attributes = attributes
        self.__live_data = live_data if live_data else self.__init_live_data()
        self.__client = session.client(SERVICE)
        self.__verbose = verbose

        self.__actions = {
            'build': self.__init_build_actions(),
            'update': [],
            'destroy': []
        }

    
    # standard functions that should be roughly the same for all types of resources.
    def build(self, attributes={}, resource_template={}, session=None):
        """executes build actions 1 by 1 and marks them as done.  raise error if dependencies found"""
        # if given an updated template, client, replace existing
        if resource_template:
            self.__resource_template = resource_template 
        if attributes:
            self.__attributes = attributes 
        if session:
            self.__client = session.client(SERVICE)

        for action in self.__actions['build']:
            if not action['complete']:
                function, arg_names = action['execution']

                args = dict_select(self.__attributes, arg_names)
                
                dependency(args) # raises error if dependencies found

                self.__live_data = { **self.__live_data, **function(**args) }

                action['complete'] = True
                
                yield self.live_data()
    

    def update(self, attributes={}, resource_template={}, session=None):
        """executes update actions 1 by 1 and marks them as done.  raise error if dependencies found"""
        # TODO: only return actions that have the needed attributes 
        pass


    def destroy(self, session):
        """executes destroy actions 1 by 1 and marks them as done.  raise error if dependencies found"""
        pass


    def __init_build_actions(self):
        """processes the saved resource template and returns build actions, args"""
        return [
            {
                'execution': ( self.__create_distribution, ['description', 'default_root', 'origins', 'default_origin', 'cache_behaviors', 'custom_errors', 'enabled'] ),
                'complete': False
            }
        ]


    def __init_update_actions(self):
        """processes the saved resource template and returns update actions, args"""
        actions = []
        if self.__resource_template['update_mode'] == 'rebuild':
            actions = self.__init_destroy_actions() + self.__init_build_actions()
        
        return actions


    def __init_destroy_actions(self):
        """processes the saved resource data and returns destroy actions, args"""
        # TODO this seems super complicated and annoying to do.  you have to "Disable", the wait 15 min then delete
        return []

    
    def __init_live_data(self):
        return {}


    # standard accessors
    def live_data(self):
        return {
            self.__name : self.__live_data
        }

    
    def name(self):
        return self.__name

    # custom method for finding orphaned resources
    @classmethod
    def list_resources(cls, session=None):
        """yields a generator of all resources of this type that exist in the aws account"""
        client = session.client(SERVICE)

        distros = client.list_distributions()['DistributionList']['Items']

        for distro in distros:
            yield cls(
                session,
                name=distro['Id'],
                live_data={ # TODO: come up with a way to template-ize this?
                    'name': distro['Id'],
                    ##'region': response['Location'],  TODO
                    'id': distro['Id'],
                    'arn': distro['ARN']
                }
            )

    # custom functions to be called in build, update, destroy
    def __create_distribution(self, **kwargs):
        origins = []
        for origin in kwargs['origins']:
            if "default" in origin.keys():
                if origin['default']:
                    default_origin = origin['name']

            origins.append({ # TODO: do we need to get the other properties?
                'Id': origin['name'], 
                'DomainName': origin['domain'], 
                'OriginPath': '', 
                'CustomHeaders': {
                    'Quantity': 0
                }, 
                'S3OriginConfig': {
                    'OriginAccessIdentity': ''
                }
            })

        default_cache_behavior = {}
        cache_behaviors = []
        for cb in kwargs["cache_behaviors"]:
            mapped_cb = {
                'TargetOriginId': cb["target_origin"], 
                'ViewerProtocolPolicy': cb["viewer_protocol_policy"], # allow all
                'AllowedMethods': {  # I dont know what this is, i don't remember setting it up... maybe try without first?
                    'Quantity': len(cb["allowed_methods"]), # 2
                    'Items': cb["allowed_methods"], #['HEAD', 'GET']
                    'CachedMethods': {
                        'Quantity': len(cb["cached_methods"]), #2
                        'Items': cb["cached_methods"] #['HEAD', 'GET']
                    }
                },
                'TrustedSigners': { # apparently needed?
                    'Enabled': False,
                    'Quantity': 0,
                },
                'ForwardedValues': { # apparently needed?
                    'QueryString': False, 
                    'Cookies': {
                        'Forward': 'none'
                    }, 
                    'Headers': {
                        'Quantity': 0
                    }, 
                    'QueryStringCacheKeys': {
                        'Quantity': 0
                    }
                },
                'MinTTL': 0,  # apparently needed?
            }

            if "default" in origin.keys():
                if cb['default']:
                    default_cache_behavior = mapped_cb 
                else:
                    cache_behaviors.append(mapped_cb)

        custom_errors = []
        for err in kwargs['custom_errors']:
            custom_errors.append({
                'ErrorCode': err['error_code'],
                'ResponsePagePath': err['redirect_path'], 
                'ResponseCode': err['response_code'], 
                'ErrorCachingMinTTL': err['caching_ttl']
            })
        
        price_class = 'PriceClass_200' # TODO need a smarter way to do this, to lazy to think of now
        
        certificate = {  # not required, modify?  # TODO: need a smarter way to do this, to lazy to think of now
            'CloudFrontDefaultCertificate': True, 
            'MinimumProtocolVersion': 'TLSv1', # 'SSLv3'|'TLSv1'|'TLSv1_2016'|'TLSv1.1_2016'|'TLSv1.2_2018'|'TLSv1.2_2019'
            'CertificateSource': 'cloudfront' #'cloudfront'|'iam'|'acm'
        }


        response = self.__client.create_distribution(
            DistributionConfig={
                'CallerReference': ("%016x" % getrandbits(64)).upper(), # unique string, create a random hash and log it.  maybe just use resourcename instead?
                'DefaultRootObject': kwargs["default_root"], 
                'Origins': {
                    'Quantity': len(origins), 
                    'Items': origins
                },
                'DefaultCacheBehavior': default_cache_behavior,
                # 'CacheBehaviors': { # TODO based on cache
                #     'Quantity': 0
                # }
                'CustomErrorResponses': { # not required, modify?
                    'Quantity': len(custom_errors), # 2
                    'Items': custom_errors
                },
                'Comment': kwargs['description'], # TODO: make optional
                'PriceClass': price_class, # not required, modify? 
                'Enabled': kwargs['enabled'], # TODO: make optional
                'ViewerCertificate': certificate, # not required, modify?
            }
        )

        return { # TODO: come up with a way to template-ize this?
            'name': response['Distribution']['Id'],
            'caller_reference': response['Distribution']['DistributionConfig']['CallerReference'],
            ##'region': response['Location'],  TODO
            'id': response['Distribution']['Id'],
            'arn': response['Distribution']['ARN']
        }

