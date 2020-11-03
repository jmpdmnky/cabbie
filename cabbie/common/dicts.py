
#TODO for ALL: add behavior to handle KeyError. shoul dbe able to choose whether to err out or continue

def list_where(l, k, v):
    for d in l:
        if d[k] == v:
            return d


def safe_dict_val(d, k, default=False, error=False):
    try:
        return d[k]
    except Exception as e:
        if error:
            raise e
        else:
            return default


def dict_append(d, k, v):
    if k in d.keys():
        d[k].append(v)
    else:
        d[k] = [v]


def dict_increment(d, k, v):
    if k in d.keys():
        d[k] += v
    else:
        d[k] = v


def dict_where(d, *key_vals):
    # args should be (k,v) tuples to test against
    #k, v = key_vals[0]
    for sub_dict_key, sub_dict in d.items():
        if all([ True if sub_dict[k] == v else False for k, v in key_vals ]):
            return {sub_dict_key: sub_dict}


def dict_wheres(d, *key_vals):
    # args should be (k,v) tuples to test against
    #k, v = key_vals[0]
    for sub_dict_key, sub_dict in d.items():
        try:
            if all([ True if sub_dict[k] == v else False for k, v in key_vals ]):
                yield {sub_dict_key: sub_dict}
        except: # if keu does not exist, then don't return it
            pass


def dict_wheres_2(d, *key_vals):
    # args should be (k,v) tuples to test against
    #k, v = key_vals[0]
    new_dict = {}
    for sub_dict_key, sub_dict in d.items():
        try:
            if all([ True if sub_dict[k] == v else False for k, v in key_vals ]):
                new_dict[sub_dict_key] = sub_dict
        except: # if keu does not exist, then don't return it
            pass

    return new_dict


def fwalk_dict_2(d, indent='', indent_char=' ', f=lambda x, kc: x, args={}, print_keys=False, key_crumbs=[]):
    try:
        # if we were passed a dict, walk the dict
        new_dict = {}
        for k,v in d.items():
            print('{}{}:'.format(indent, k)) if print_keys else ''
            if isinstance(v, dict):
                #print('{}{}:'.format(indent, k))
                new_dict[k] = fwalk_dict_2(v, indent+indent_char, indent_char, f, args, print_keys, key_crumbs=key_crumbs + [k])
            elif isinstance(v, list):
                new_dict[k] = []
                for item in v:
                    new_dict[k].append(fwalk_dict_2(item, indent+indent_char, indent_char, f, args, print_keys, key_crumbs=key_crumbs + [k]))
            else:
                #print('{}{}: {}'.format(indent, k, v))
                new_dict[k] = f(v, key_crumbs, **args)
        return new_dict
    except:
        # if we were passed a non-dict, assume we are at a "leaf level" and return it
        print('{}{}'.format(indent, d)) if print_keys else ''
        return d


def fwalk_dict(d, indent='', indent_char=' ', f=lambda x: x, args={}, print_keys=False):
    try:
        # if we were passed a dict, walk the dict
        new_dict = {}
        for k,v in d.items():
            print('{}{}:'.format(indent, k)) if print_keys else ''
            if isinstance(v, dict):
                #print('{}{}:'.format(indent, k))
                new_dict[k] = fwalk_dict(v, indent+indent_char, indent_char, f, args, print_keys)
            elif isinstance(v, list):
                new_dict[k] = []
                for item in v:
                    new_dict[k].append(fwalk_dict(item, indent+indent_char, indent_char, f, args, print_keys))
            else:
                #print('{}{}: {}'.format(indent, k, v))
                new_dict[k] = f(v, **args)
        return new_dict
    except:
        # if we were passed a non-dict, assume we are at a "leaf level" and return it
        print('{}{}'.format(indent, d)) if print_keys else ''
        return d


def dict_select(d, keys):
    return { k: d[k] for k in keys }


def list_select(l, keys): # TODO: implement
    return [ dict_select(d, keys) for d in l ]


def list_from_key(l, key): # TODO Rename
    return [ d[key] for d in l ]


def dict_dotval(d, s, split_val='.'): #TODO: i hate this name
    keys = s.split(split_val)
    val = d
    for k in keys:
        val = val[k]

    return val

