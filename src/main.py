import boto3
import json
from datetime import datetime, timezone
#from dateutil import parser as date_parser
import sys, os, csv

"""input CSV must have these columns: name, email, iam-username
output CSV looks like: name, email, iam-username, message"""

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
lfilter = lambda fn, lst: list(filter(fn, lst))

def spy(val):
    print('spying: %s' % val)
    return val


# states

UNKNOWN = '?'

IDEAL = 'ideal'
GRACE_PERIOD = 'in-grace-period'

ALL_CREDENTIALS_ACTIVE = 'all-credentials-active'
NO_CREDENTIALS_ACTIVE = 'no-credentials-active'
OLD_CREDENTIALS = 'old-credentials'
NO_CREDENTIALS = 'no-credentials'

MANY_CREDENTIALS = 'many-credentials'

STATE_DESCRIPTIONS = {
    IDEAL: "1 active set of credentials younger than max age of credentials",
    GRACE_PERIOD: "two active sets of credentials, one set created in the last $grace-period days",
    ALL_CREDENTIALS_ACTIVE: "two active sets of credentials, both sets older than $grace-period days",
    NO_CREDENTIALS_ACTIVE: "credentials present but none are active",
    OLD_CREDENTIALS: "credentials are old and will be rotated",
    NO_CREDENTIALS: "no credentials exist",

    # bad states
    MANY_CREDENTIALS: "more than 2 sets of credentials exist (program error)",
    UNKNOWN: "credentials are in an unhandled state (program error)"
}

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

def delete_key(key):
    #key.delete()
    pass

def key_list(iamuser):
    iamuser.load() # also re-loads
    return list(iamuser.access_keys.all())

def create_date(key):
    # key.create_date ll: 2013-01-15 15:15:57+00:00
    #return date_parser.parse(key.create_date)
    return key.create_date # turns out this is already parsed

def update_iam_user(user_csvrow, max_key_age=90, grace_period_days=7):
    try:
        today = datetime.now(tz=timezone.utc)
        state = UNKNOWN
        actions = []

        iam = boto3.resource('iam')
        iamuser = iam.User(user_csvrow['iam-username'])

        access_keys = key_list(iamuser)
        ensure(len(access_keys) > 0, NO_CREDENTIALS)
        ensure(len(access_keys) < 3, MANY_CREDENTIALS) # there must only ever be 0, 1 or 2 keys

        active_keys, inactive_keys = splitfilter(lambda key: key.status != 'Inactive', access_keys)
        ensure(active_keys, NO_CREDENTIALS_ACTIVE)

        if len(active_keys) > 1:
            state = ALL_CREDENTIALS_ACTIVE
            # we have two active keys
            # * user is possibly using both sets, which is no longer supported, or
            # * user was granted a new set of credentials by this script
            newest_key, oldest_key = sorted(active_keys, key=create_date)
            if (today - create_date(newest_key)) > grace_period_days:
                # grace period is over
                # mark the oldest of the two active keys as inactive
                inactive_keys.append(oldest_key)
                active_keys.remove(oldest_key)

        # always prune inactive keys
        [actions.append({'delete': key.access_key_id}) for key in inactive_keys]

        # state: 1 or 2 active keys. no inactive keys.

        if len(active_keys) > 1:
            # transition period, nothing else to do until grace period expires
            state = GRACE_PERIOD

        else:
            # 1 active key
            active_key = active_keys[0]
            then = create_date(active_key)
            if (today - then).days > max_key_age:
                # remaining key is too old
                state = OLD_CREDENTIALS
                actions += [
                    {'disable': active_key.access_key_id},
                    {'create': 'new'}
                ]
            else:
                state = IDEAL

        return {
            'success?': True,
            'state': state,
            'reason': STATE_DESCRIPTIONS[state],
            'original-row': user_csvrow,
            'actions': actions,
        }
    except AssertionError as err:
        state = str(err)
        return {
            'success?': False,
            'state': state,
            'reason': STATE_DESCRIPTIONS[state],
            'original-row': user_csvrow,
            'actions': []
        }

def write_report(passes, fails):
    report = {'passes': passes, 'fails': fails}
    path = 'report.json'
    print(json.dumps(report, indent=4))
    json.dump(report, open(path, 'w'), indent=4)
    return path

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
        print('err:',err)
        retcode = getattr(err, 'retcode', 1)
        sys.exit(retcode)
