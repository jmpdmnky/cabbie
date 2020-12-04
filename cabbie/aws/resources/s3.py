"""
General flow:  We open up the resource_template.json in the main method.  For each resource, create a
corresponding resource object and add to the build queue, modify queue.  attempt to build one by one.  if
dependecies not met, throw error.  catch error, move to back of queue.  repeat for modify.
"""

import boto3

from .resources import dependency
from .resources import DependecyNotMetError
from .resources import resource

from common.files import file_obj
from common.files import list_dir


from common.dicts import dict_select
from common.dicts import dict_dotval
from common.dicts import safe_dict_val


# TODO: come up with a way to template-ize functions?
# TODO: add verbose print statements
# TODO: add option to re-up session/client when calling build/update/destroy

SERVICE = 's3'

# bucket

class bucket(resource):


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
                'execution': ( self.__create_bucket, ['bucket'] ),
                'complete': False
            }
        ]


    def init_update_actions(self):
        """processes the saved resource template and returns update actions, args"""
        # if self.verbose:
        #     print('-updating', self.name)
        actions = []
        
        # if safe_dict_val(self.__resource_template, 'update_mode', default='default'):
        #     actions = self.__init_destroy_actions() + self.__init_build_actions()

        actions += [
            {
                'execution': ( self.__configure_website, ['bucket', 'website_config'] ),
                'complete': False
            }
        ]
        
        return actions


    def init_destroy_actions(self):
        """processes the saved resource data and returns destroy actions, args"""
        return [
            {
                'execution': ( self.__delete_bucket, []),
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

        buckets = client.list_buckets()['Buckets']

        for bucket in buckets:
            yield cls(
                session,
                name=bucket['Name'],
                live_data={
                    'name': bucket['Name'],
                    'region': '',
                    'arn': 'arn:aws:s3:::{}'.format(bucket['Name'])
                }
            )

    # custom functions to be called in build, update, destroy
    def __create_bucket(self, bucket):
        # if self.live_data:
        #     if self.verbose:
        #         print('-skipping', bucket) 
        #     return self.live_data
        # else:
            # if self.verbose:
            #     print('-creating', bucket)
        response = self.client.create_bucket(
            Bucket=bucket
        )

        self.live_data = { # TODO: come up with a way to template-ize this?
            'name': bucket,
            'region': response['Location'], # TODO doesnt actually work
            'arn': 'arn:aws:s3:::{}'.format(bucket)
        }

        return self.live_data
    

    def __configure_website(self, bucket, website_config):
        """
            "website_config": {
                    "index": --> WebsiteConfiguration["IndexDocument"]["Suffix"],
                    "error": --> WebsiteConfiguration["ErrorDocument"]["Suffix"],
                    "redirect": {
                        "hostname": --> WebsiteConfiguration["RedirectAllRequestsTo"]["HostName"]
                        "https": True|False --> WebsiteConfiguration["RedirectAllRequestsTo"]["Protocol"]
                    },
                    "routing": --> not sure how to handle this
                }
        """

        if self.verbose:
            print('-configuring website for', self.name)

        args = {
            'IndexDocument': {
                'Suffix': website_config['index']  # this is the only mandatory parameter
            }
        }   
        
        # TODO: go through other possible args and add int args if they exist

        response = self.client.put_bucket_website(
            Bucket=bucket,
            WebsiteConfiguration=args
            )

        # TODO: get region?
        self.live_data['website'] = 'http://{}.s3-website-us-east-1.amazonaws.com'.format(bucket)
        self.live_data['domain'] = '{}.s3.amazonaws.com'.format(bucket)

        # return {
        #     'website': 'http://{}.s3-website-us-east-1.amazonaws.com'.format(bucket),
        #     'domain': '{}.s3.amazonaws.com'.format(bucket)
        # }
        return self.live_data


    def __delete_bucket(self):
        # response = self.__client.delete_bucket(
        #     Bucket=self.__live_data['name']
        # )
        try:
            response = self.client.delete_bucket(
                Bucket=self.live_data['name']
            )
        except self.client.exceptions.ClientError as e:
            if 'BucketNotEmpty' in str(e):
                raise DependecyNotMetError('An error occurred (BucketNotEmpty) when calling the DeleteBucket operation: The bucket you tried to delete is not empty') from e
            raise e

        # TODO: if bucketnotempty err, raise DependecyNotMetError()
        
        return {}

# object

class object(resource):


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
                'execution': ( self.__put_objects, ['bucket', 'source', 'prefix'] ), 
                'complete': False
            }
        ]


    def init_update_actions(self):
        """processes the saved resource template and returns update actions, args"""
        return [
            {
                'execution': ( self.__put_objects, ['bucket', 'source', 'prefix'] ), 
                'complete': False
            },
            {
                'execution': ( self.__put_object_acl, ['bucket', 'acls'] ),
                'complete': False
            }
        ]


    def init_destroy_actions(self):
        """processes the saved resource data and returns destroy actions, args"""
        return [
            {
                'execution': ( self.__delete_objects, [] ),
                'complete': False
            }
        ]


    def init_live_data(self):
        return {
            'bucket': '',
            'keys': []
        }


    # custom method for finding orphaned resources
    @classmethod
    def list_resources(cls, session=None):
        """yields a generator of all resources of this type that exist in the aws account"""
        client = session.client(SERVICE)

        buckets = client.list_buckets()['Buckets']

        for bucket in buckets:
            bucket_objects = response = client.list_objects( # TODO: will we have pagination issues?
                Bucket='string'
            )['Contents']
            yield cls(
                session,
                name='{}_objects'.format(bucket['Name']),
                live_data={
                    'bucket': bucket['Name'],
                    'region': '', # TODO: region
                    'keys': [ obj['Key'] for obj in bucket_objects ]
                }
            )


    # custom functions to be called in build, update, destroy
    def __put_objects(self, bucket, source, prefix):

        self.live_data['bucket'] = bucket #TODO should this be handled elsewhere?

        # iterate over list of files in source path
        source_paths = [source] 
        if(source[-1] == '/'):  # if source is a dir, the overwrite
            source_paths = list(list_dir(source))

        for path in source_paths:
            key = "{prefix}/{suffix}".format(prefix=prefix, suffix=path.split(source, 1)[-1]) if prefix else path.split(source, 1)[-1]
            
            ############## TEMPORARY FIX ##############
            metadata_lookup = {
                'js': 'application/javascript',
                'html': 'text/html',
                'css': 'text/css',
                'png': 'image/png',
                'gz': 'application/javascript'
            }
            ###########################################

            if key in self.live_data['keys']: # TODO: get rid of these checks, should just be in "build" function
                if self.verbose:
                    print('-skipping', key) 
            else:
                if self.verbose:
                    print('-creating', key)
                try: # TODO: come with some standard boto try except that handles expected boto errors?
                    response = self.client.put_object(
                        Bucket=bucket,
                        Body=file_obj(path),
                        Key=key,
                        ContentType=metadata_lookup[key.split('.')[-1]]
                    )
                    self.live_data['keys'].append(key)
                except Exception as e:
                    print(e)

        return self.live_data # TODO this feels weird... should these just update live_data as they go and return nothing?


    def __put_object_acl(self, bucket, acls):
        """
            "acls": {
                "read": ["ALL"]
            },
        """

        grants = {
            'full_control': 'GrantFullControl',
            'read': 'GrantRead',
            'read_acp': 'GrantReadACP',
            'write': 'GrantWrite',
            'write_acp': 'GrantWriteACP',
        }


        args = {}

        for access_type in acls.keys():
            if grants[access_type] not in args.keys():
                args[grants[access_type]] = ''
            if "ALL" in acls[access_type]:
                args[grants[access_type]] = 'uri=http://acs.amazonaws.com/groups/global/AllUsers'
            # TODO: handle if they give you more accessthingies

        #policies = attr['policies']
        for key in self.live_data['keys']:
            response = self.client.put_object_acl(
                **args,
                Bucket=bucket,
                Key=key
            )

        return self.live_data # Nothing new to return


    def __delete_objects(self):
        for key in self.live_data['keys']:
            response = self.client.delete_object(
                Bucket=self.live_data['bucket'],
                Key=key
            )

        return {}

