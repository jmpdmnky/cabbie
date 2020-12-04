import re
import json
from time import sleep

from common import fwalk_dict

from common.dicts import dict_select
from common.dicts import dict_dotval
from common.dicts import safe_dict_val


class DependecyNotMetError(Exception):
    pass


def dependency(d):
    pattern = r"\${[A-Za-z0-9.:@'/_-]+}" # TODO: store this pattern in a standard location so we can import as needed?
    print('dependency()', d)

    def check_dep(s):
        if isinstance(s, str):
            if re.search(pattern, s):
                raise DependecyNotMetError()


    fwalk_dict(d, f=check_dep)
    # if re.search(pattern, json.dumps(d)):
    #     raise DependecyNotMetError()


def boto_try(f, args={}, max_retries=5, wait=0, fwait=lambda x: x * x, verbose=False):
    # TODO: add custom actions for different errors we might encounter, for now we just retry but we probably want most of them to break
    retries = 0
    while retries < max_retries:
        try:
            return f(**args)
        except Exception as e:
            if verbose:
                print(e)
            retries += 1
            sleep(wait)
            wait = fwait(wait)
    
    raise Exception('Max retries exceeded')


class resource:


    def __init__(self, session, service, name='', attributes={}, resource_template={}, live_data={}, verbose=False):
        self.name = name
        self.resource_template = resource_template
        self.attributes = attributes
        self.live_data = live_data #if live_data else self.__init_live_data() # TODO: probably need to move init to build, after the "skip if"
        self.service = service
        self.client = session.client(service)
        self.verbose = verbose

        self.default_actions = {
            'build': self.init_build_actions(),
            'update': self.init_update_actions(),
            'destroy': self.init_destroy_actions()
        }

        self.plugins = {
            'build': {
                'pre' : [],
                'post': []
            },
            'update': {
                'pre' : [],
                'post': []
            },
            'destroy': {
                'pre' : [],
                'post': []
            }
        }

    
    # standard functions that should be roughly the same for all types of resources.
    def build(self, attributes={}, resource_template={}, session=None):
        """executes build actions 1 by 1 and marks them as done.  raise error if dependencies found"""
        # if already exists, skip
        if self.live_data:
            if self.verbose:
                print('-skipping', self.name)
            return self.live_data
        else:
            self.live_data = self.init_live_data()
            if self.verbose:
                print('-creating', self.name)

        # if given an updated template, client, replace existing
        if resource_template:
            self.resource_template = resource_template 
        if attributes:
            self.attributes = attributes 
        if session:
            self.client = session.client(self.service)

        for action in self.actions('build'):
            if not action['complete']:
                function, arg_names = action['execution']

                # TODO: make dict_select return some default empty value for missing arguments, let each function validate missing args
                args = dict_select(self.attributes, arg_names)
                
                dependency(args) # raises error if dependencies found

                self.live_data = { **self.live_data, **function(**args) }

                action['complete'] = True

                yield self.live_data
    

    def update(self, attributes={}, resource_template={}, session=None):
        """executes update actions 1 by 1 and marks them as done.  raise error if dependencies found"""
        # TODO: only return actions that have the needed attributes 
        for action in self.actions('update'):
            if not action['complete']:
                function, arg_names = action['execution']

                args = dict_select(self.attributes, arg_names)
                
                dependency(args) # raises error if dependencies found

                self.live_data = { **self.live_data, **function(**args) }

                action['complete'] = True

                yield self.live_data


    def destroy(self, attributes={}, session=None):
        """executes destroy actions 1 by 1 and marks them as done.  raise error if dependencies found"""
        if not self.live_data:
            print('-skipping', self.name)
            return {}
        else:
            print('-deleting', self.name)

        for action in self.actions('destroy'):
            if not action['complete']:
                function, arg_names = action['execution']

                args = dict_select(self.attributes, arg_names)

                #dependency(args) # raises error if dependencies found TODO do i need this?
                
                function(**args)

                self.live_data = {} # TODO: this doesnt actually work... need to delete elements one by one as we execute actions and then remove from resources file once empty

                action['complete'] = True

                yield self.live_data


    ##############  Implement in child ##############

    def init_build_actions(self):
        """processes the saved resource template and returns build actions, args"""
        return []


    def init_update_actions(self):
        """processes the saved resource template and returns update actions, args"""
        return []


    def init_destroy_actions(self):
        """processes the saved resource data and returns destroy actions, args"""
        return []


    def init_live_data(self):
        return {}

    #################################################


    def init_plugin(self, plugin_details, opts={}, pre=[], post=[]):
        self.attributes = { **self.attributes, **opts }
        self.resource_template['attributes'] = { **self.resource_template['attributes'], **opts }

        for stage in pre:
            self.plugins[stage]['pre'] = sorted( self.plugins[stage]['pre'] + [plugin_details], key=lambda x: x['priority'] )

        for stage in post:
            self.plugins[stage]['post'] = sorted( self.plugins[stage]['post'] + [plugin_details], key=lambda x: x['priority'] )


    def actions(self, key):
        return self.plugins[key]['pre'] + self.default_actions[key] + self.plugins[key]['post']


    # standard accessors
    # def live_resource_data(self):
    #     return {
    #         self.name : self.live_data
    #     }

    
    # def name(self):
    #     return self.__name


    def template(self):
        return self.resource_template


    # def attributes(self):
    #     return self.__attributes


    ##############  Implement in child ##############
    # custom method for finding orphaned resources
    @classmethod
    def list_resources(cls, session=None):
        """yields a generator of all resources of this type that exist in the aws account"""
        pass

    #################################################
