import boto3
import sys, os, csv

"""Flow:

you: generate csv report
you: filter to just those users to receive new credentials automatically
you: call me with ./update-iam-users.sh csvfile
 me: for each user in your csv file
 me: fail user if two active sets of credentials
 me: fail user if no credentials (we are *updating existing* access, not *creating new*)
 me: remove any disabled/inactive credentials
 me: disable any remaining credentials
 me: create new credentials
 me: create a new secret GIST with the credentials
 me: send emails to all affected users
 me: write csv report


TODO: call this to rotate credentials? for example:
* first call creates new set of credentials, writes gist, sends email
* second call checks last-used-by and if beyond a threshold (7 days?) disables the oldest created


input CSV must have these columns: name, email, iam-username
output CSV looks like: name, email, IAM username, pass/fail message"""

def ensure(b, m, retcode=1):
    if not b:
        inst = AssertionError(m)
        inst.retcode = retcode
        raise inst

def splitfilter(fn, lst):
    ensure(callable(fn) and isinstance(lst, list), "bad arguments to splitfilter")
    group_a, group_b = [], []
    [(group_a if fn(x) else group_b).append(x) for x in lst]
    return group_a, group_b

lmap = lambda fn, lst: list(map(fn, lst))

def spy(val):
    print('spying: %s' % val)
    return val

#
#
#

INPUT_HEADER = ['name', 'email', 'iam-username']

def read_input(user_csvpath):
    ensure(os.path.exists(user_csvpath), "path not found: %s" % user_csvpath)
    ensure(os.path.isfile(user_csvpath), "path is not a file: %s" % user_csvpath)
    with open(user_csvpath) as fh:
        retval = list(csv.DictReader(fh, fieldnames=INPUT_HEADER))
        ensure(len(retval) > 1, "csv file is empty")        
        header = list(retval.pop(0).keys()) # skip the header
        ensure(header == INPUT_HEADER, "csv file has incorrect header: %s" % header)
        return retval

def update_iam_user(user_csvrow):
    try:
        iam = boto3.resource('iam')
        iamuser = iam.User(user_csvrow['iam-username'])
        iamuser.load() # urgh

        access_keys = list(iamuser.access_keys.all())
        ensure(len(access_keys) > 0, "no access keys to rotate")

        active_keys, inactive_keys = splitfilter(lambda key: key.status != 'Inactive', access_keys)
        ensure(active_keys, "no *active* keys to rotate")
        ensure(len(active_keys) == 1, "more than one active key")

        # ideal state
        # we have 1 active key
        # we have 0 or 1 inactive keys
        
        #k1 = access_keys[0]
        #print(k1.access_key_id)
        #print(k1.create_date)
        #print(k1.status)
        
        return {
            'success?': True,
            'original-row': user_csvrow,
        }
    except AssertionError as err:
        return {
            'success?': False,
            'reason': str(err)
        }

def write_report(passes, fails):
    print('results',passes,fails)
    return '/path/to/report.csv'

def main(user_csvpath):
    csv_contents = read_input(user_csvpath)
    results = lmap(update_iam_user, csv_contents)
    pass_rows, fail_rows = splitfilter(lambda row: row['success?'], results)
    print('wrote: ', write_report(pass_rows, fail_rows))
    return len(fail_rows)

if __name__ == '__main__':
    try:
        args = sys.argv[1:]
        ensure(len(args) == 1, "exactly one argument required: path-to-csvfile")
        user_csvpath = args[0]
        sys.exit(main(user_csvpath))
    except AssertionError as err:
        print(err)
        retcode = getattr(err, 'retcode', 1)
        sys.exit(retcode)
