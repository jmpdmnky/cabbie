from time import sleep

def try_retry(f, args={}, max_retries=5, wait=0, fwait=lambda x: x, verbose=False):
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


def try_default(f, args={}, default=None, verbose=False):
    try:
        f(args)
    except Exception as e:
        if verbose:
            print(e)
        return default

