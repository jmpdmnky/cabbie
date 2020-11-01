import os
#import re
#import shutil
import json



def join_path(*args):
    return '/'.join(args)


# def file_copy_forward(filename):
#     # make sure all of the necessary directories exist
#     path = ''
#     for path_dir in active_stage_filename(filename).split('/')[0:-1]:
#         path = '{}/{}'.format(path, path_dir) if path else path_dir
#         try:
#             os.mkdir(path)
#         except:
#             pass
    
#     # copy file
#     shutil.copy(previous_stage_filename(filename), active_stage_filename(filename))
#     # with open(previous_stage_filename(filename), 'r') as infile:
#     #     with open(active_stage_filename(filename), 'w') as outfile:
#     #         outfile.write(infile.read())


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


def list_dir(directory):
    for root, directories, files in os.walk(directory): 
            for filename in files: 
                # join the two strings in order to form the full filepath. 
                yield os.path.join(root, filename).replace('\\', '/') 