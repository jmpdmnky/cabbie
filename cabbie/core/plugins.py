import os
import re


from common.files import file_bytes
from common.files import file_string
from common.files import file_obj
from common.files import file_json


def evaluate(self, string):
    functions = {
        'file': self.__temp_open_file,
        'string': self.__force_string,
        'bytes': self.__force_bytes,
        'resource': self.__resource_attribute,
        'session': self.__session_data,
        'eval': self.__evaluate
    }
    #print('evaluating ', string)

    # if string is not actually a string (eg. int), don't evaluate
    if not isinstance(string, str):
        return string

    # handle any @s in filenames TODO: evaluate if this is the right place for this
    string = self.__full_path(string)

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


def os_command(command, exec_dir=None):
    if exec_dir:
        cwd = os.getcwd().replace('\\', '/')
        os.system('cd {}'.format(exec_dir))

    os.system(command)
    
    if exec_dir:
        os.system('cd {}'.format(cwd))

    return {}


def external_file(path, function): # pass in evaluate
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

    return {}


def zip_path(output_path, input_path=None):
    # TODO: adapt this to work with files too?
    # zip project_dir and wrote to zip_file
    if input_path:
        file_paths = [] 
    
        # crawling through directory and subdirectories 
        for root, directories, files in os.walk(input_path): 
            for filename in files: 
                # join the two strings in order to form the full filepath. 
                filepath = os.path.join(root, filename) 
                arcname = os.path.join(root.replace(input_path,''), filename) 
                file_paths.append({'file_path': filepath, 'arcname': arcname}) 

        print('Zipping following project files:') 
        for file_name in file_paths: 
            print(file_name['arcname']) 

        # writing files to a zipfile 
        with ZipFile(output_path, 'w') as zip: 
            # writing each file one by one 
            for file in file_paths: 
                zip.write(file['file_path'], arcname=file['arcname']) # make arcname the correct path within the zipfile

    # open, return bytes
    with open(output_path, 'rb') as infile:
        return infile.read()


# TODO: make these names a little more distinct... maybe prepend with "plugin_"?
plugins = {
    'external_file': {
        'execution': ( external_file, ['path', 'function'] ),
        'complete': False
    },
    'os_command': {
        'execution': ( os_command, ['command', 'exec_dir'] ),
        'complete': False
    },
    'zip': {
        'execution': ( zip_path, ['input_path', 'output_path'] ),
        'complete': False
    }
}