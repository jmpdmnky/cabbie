import re
import json
from time import sleep

from common import fwalk_dict


class DependecyNotMetError(Exception):
    pass


def dependency(d):
    pattern = r"\${[A-Za-z0-9.:'/_-]+}" # TODO: store this pattern in a standard location so we can import as needed?

    if re.search(pattern, json.dumps(d)):
        raise DependecyNotMetError()


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

