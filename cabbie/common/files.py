import os
import json



# specific file type openers
def join_path(*args):
    return '/'.join(args)


def file_bytes(filename):
    with open(filename, 'rb') as infile:
        return infile.read()


def file_string(filename):
    with open(filename, 'r') as infile:
        return infile.read()


def file_obj(file):
        return open(file, 'rb') 


def file_json(filename):
    with open(filename, 'r') as infile:
        return json.loads(infile.read())


# general file helpers
def list_dir(directory):
    for root, directories, files in os.walk(directory): 
            for filename in files: 
                # join the two strings in order to form the full filepath. 
                yield os.path.join(root, filename).replace('\\', '/') 


def ensure_valid_path(filepath):
    # make sure all of the necessary directories exist
    path = ''
    for path_dir in filepath.split('/')[0:-1]:
        path = '{}/{}'.format(path, path_dir) if path else path_dir
        try:
            os.mkdir(path)
        except:
            pass


