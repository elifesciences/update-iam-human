'''
some very rough code for deleting inactive credentials in bulk.

read the code before executing it, then do: $ python -m src.rm_inactive
'''

import boto3
from . import utils
from .main import key_list
import json
import os
import itertools

def shallow_flatten(x):
    return list(itertools.chain(*x))

def get_all_users():
    if os.path.exists('cache.json'):
        return json.load(open('cache.json', 'r'))
    try:
        iam = boto3.client('iam')
        paginator = iam.get_paginator('list_users')
        resp = list(paginator.paginate())
        open('cache.json', 'w').write(utils.lossy_json_dumps(resp))
        return resp
    except Exception as err:
        print('warning: %s' % str(err))
        return None

def list_keys(user):
    print('fetching keys for', user['UserName'])
    return key_list(user['UserName'])

def filter_inactive(key_list):
    return filter(lambda key: key['status'] == 'Inactive', key_list)

def pp(x):
    import pprint
    pprint.pprint(x)

def delete_key(key):
    print('deleting key', key)
    key['-obj'].delete()

def main():
    resp = get_all_users()
    user_list = resp[0]['Users']
    inactive_key_list = list(filter_inactive(shallow_flatten(map(list_keys, user_list))))
    pp(inactive_key_list)
    input('delete these %s inactive keys?' % len(inactive_key_list))
    list(map(delete_key, inactive_key_list))

if __name__ == '__main__':
    main()
