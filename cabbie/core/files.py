import os
from shutil import copy

from common.files import file_json
from common.files import ensure_valid_path



class config:

    def __init__(self, config_file=".cabbie/config.json"):
        self.config_file = config_file
        self.project_home = self.__project_home(config_file)
        self.config = file_json('/'.join([self.project_home, config_file])) # TODO: I think we actually only need alias?


    def __project_home(self, config_file):
        """gets the absolute path of the project home directory, or throws an error if not found"""
        current_path = re.split(r'[/\\]', os.getcwd())  # will this break on paths w/ spaces?  those might have escape chars
        config_path = []

        while current_path:
            config_path = current_path + [config_file]
            if not os.path.exists('/'.join(config_path)):
                current_path.pop()
            else:
                return '/'.join(current_path)

    
    def rconfig(self, config_file=".cabbie/config.json"):
        self.__init__(config_file=config_file)


file_config = config()


def re_config(config_file=".cabbie/config.json")

# cabbie specific helpers
def alias(self, filename):
    # replace all instances of all aliases... no reason why you cant have an alias in the middle?
    for a in config.config['alias'].keys():
        alias = '@{}'.format(a) # prepend @ before substituting
        filename = filename.replace(alias, config.config['alias'][a])

    return filename


def full_path(self, filename, *prefix):
    """takes a filename and returns the full path of the file within the project
    @/ = project home
    """
    # TODO: eventually make the structure more flexible?
    # TODO: do we need prefix?  I dont remember why i added it
    if not prefix:
        prefix = file_config.project_home
    else:
        prefix = '/'.join(prefix)

    filename = alias(filename)
    
    if '@' in filename: # 'absolute' path
        return filename.replace('@/', '{}/'.format(file_config.project_home))
    
    # TODO if not given an 'absolute' path, we need to establish where we are in the project 
    return filename


# generic cabbie file opener
def open_file(self, filename, fopen=file_bytes, copy_forward=False): #fopen=file_string
    """takes a filename, an optonal open function, and an option to copy the file forward to the next stage"""
    filepath = full_path(filename)
    active_filepath = full_path(self.active_stage_filename(filename))
    previous_filepath = full_path(self.previous_stage_filename(filename))

    # print(filepath)
    # print(active_filepath)
    # print(previous_filepath)

    # if copy is true, we want to copy the file to the next 
    if copy_forward:
        ensure_valid_path(active_filepath) # if we're copying the file for the first time the path to the file might nto exist...
        copy(previous_filepath, active_filepath)

    return fopen(active_filepath)


