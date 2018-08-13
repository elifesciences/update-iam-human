import boto3
from datetime import datetime, timezone
#from dateutil import parser as date_parser
import sys, os, csv
from github import Github
from github.InputFileContent import InputFileContent
import json
import smtplib
from email.message import EmailMessage

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

def vals(d, *kl):
    return [d[k] for k in kl if k in d]

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
# aws IAM
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

def coerce_key(kp):
    return {
        'access_key_id': kp.access_key_id,
        'create_date': kp.create_date,
        'status': kp.status,
        '-obj': kp,
    }

def _get_user(iam_username):
    iam = boto3.resource('iam')
    return iam.User(iam_username)

def key_list(iam_username):
    return lmap(coerce_key, _get_user(iam_username).access_keys.all())

def get_key(iam_username, key_id):
    iamuser = _get_user(iam_username)
    return lfilter(lambda kp: kp['access_key_id'] == key_id, key_list(iamuser))

def utcnow():
    return datetime.now(tz=timezone.utc)

def user_report(user_csvrow, max_key_age, grace_period_days):
    "given a row, returns the same row with a list of action"
    try:
        today = utcnow()
        state = UNKNOWN
        actions = []

        access_keys = key_list(user_csvrow['iam-username'])
        ensure(len(access_keys) > 0, NO_CREDENTIALS)
        ensure(len(access_keys) < 3, MANY_CREDENTIALS) # there must only ever be 0, 1 or 2 keys

        active_keys, inactive_keys = splitfilter(lambda key: key['status'] != 'Inactive', access_keys)
        ensure(active_keys, NO_CREDENTIALS_ACTIVE)

        # always prune inactive keys
        [actions.append(('delete', key['access_key_id'])) for key in inactive_keys]

        if len(active_keys) > 1:
            # we have two active keys
            # * user is possibly using both sets, which is no longer supported, or
            # * user was granted a new set of credentials by this script
            oldest_key, newest_key = sorted(active_keys, key=lambda kp: kp['create_date']) # ASC
            if (today - newest_key['create_date']).days > grace_period_days:
                state = ALL_CREDENTIALS_ACTIVE
                # grace period is over. mark the oldest of the two active keys as inactive.
                # it will be deleted on the next turn
                actions.append(('disable', oldest_key['access_key_id']))
            else:
                # we're in the grace period, nothing to do until it ends
                state = GRACE_PERIOD

        else:
            # 1 active key
            active_key = active_keys[0]
            if (today - active_key['create_date']).days <= max_key_age:
                state = IDEAL
            else:
                # remaining key is too old
                state = OLD_CREDENTIALS
                actions += [
                    ('create', 'new')
                ]

        user_csvrow.update({
            'success?': True,
            'state': state,
            'reason': STATE_DESCRIPTIONS[state],
            'actions': actions,
        })
        return user_csvrow

    except AssertionError as err:
        state = str(err)
        user_csvrow.update({
            'success?': False,
            'state': state,
            'reason': STATE_DESCRIPTIONS[state],
            'actions': []
        })
        return user_csvrow

def delete_key(iam_username, key_id):
    get_key(iam_username, key_id)['-obj'].delete()
    return True

def disable_key(iam_username, key_id):
    get_key(iam_username, key_id)['-obj'].disable()
    return True

def create_key(iam_username, _):
    iamuser = _get_user(iam_username)
    key = iamuser.create_access_key_pair()
    return (key.access_key_id, key.secret_access_key)

def execute_user_report(user_report_data):
    actions = {
        'delete': delete_key,
        'disable': disable_key,
        'create': create_key,
    }
    iam_username = user_report_data['iam-username']    
    actions = user_report_data['actions']
    results = [actions[fnkey](iam_username, val) for fnkey, val in actions]
    user_report_data['results'] = list(zip(actions, results))
    return user_report_data

def execute_report(report_data):
    """executes the actions against each user in the given report data.
    a report is a dict of `passes` and `failures`. `passes` is a list of 
    dicts generated by `user_report`"""
    pass


#
# aws gist
#

def aws_credentials():
    return json.load(open('private.json', 'r'))

def aws_user():
    "returns a user that can create gists"
    credentials = aws_credentials()
    gh = Github(credentials['key'])
    return gh.get_user()

def aws_create_gist(user_csvrow):
    authenticated_user = aws_user()
    public = False
    description = "new AWS API credentials"
    content = '''Hello, {insert-name-of-human}

Your new AWS credentials are:

aws_access_key={insert-access-key}
aws_secret_access_key={insert-secret-key}

Your old credentials and this message will expire on {insert-expiry-date}.'''
    content = content.format({
        'insert-name-of-human': user_csvrow['name'],
        'insert-access-key': user_csvrow['aws-access-key'],
        'insert-secret-key': user_csvrow['aws-secret-key'],
        'insert-expiry-date': user_csvrow['aws-old-key-expiry-date']
    })
    content = InputFileContent(content)
    gist = authenticated_user.create_gist(public, {'content': content}, description)
    user_csvrow.update({
        'gist-html-url': gist.html_url,
        'gist-id': gist.id,
        'gist-created-at': gist.created_at
    })
    return user_csvrow


#
# email
#

def notify_user(user_csvrow):
    user_csvrow = aws_create_gist(user_csvrow)
    name, email_to = vals(user_csvrow, 'name', 'email')
    email_from = 'it-admin@elifesciences.org'
    subject = 'Replacement AWS credentials'
    content = '''Hello {insert-name-of-human},

Your AWS credentials are being rotated. 

This means a new set of credentials has been created for you and your 
old credentials ({insert-old-key-id}) will be removed after the grace 
period ({insert-expiry-date} days).

Your new set of credentials can be found here:
{insert-gist-url}

Please contact it-admin@elifesciences.org if you have any concerns.'''
    content = content.format_map({
        'insert-name-of-human': user_csvrow['name'],
        'insert-old-key-id': user_csvrow['old-key-id'],
        'insert-expiry-date': user_csvrow['aws-old-key-expiry-date'],
        'insert-gist-url': user_csvrow['gist-html-url']
    })

    # build an email message then send it
    # stolen directly from: https://docs.python.org/3/library/email.examples.html
    msg = EmailMessage()
    msg.set_content(content)
    msg['Subject'] = subject
    msg['From'] = email_from
    msg['To'] = email_to

    # https://docs.python.org/3/library/smtplib.html#smtplib.SMTP
    email_host = 'smtp.google.com'
    email_user = 'foo'
    email_pass = 'bar'
    email_port_ssl = 465

    # or is it TLS?
    with smtplib.SMTP_SSL(email_host, email_port_ssl) as smtp:
        smtp.login(email_user, email_pass)
        smtp.send_message(msg)

    # done :)
    
    user_csvrow.update({
        'email-sent': utcnow(),
    })
    return user_csvrow
    
    
    

def notify(report_results):
    pass

def write_report(passes, fails):
    report = {'passes': passes, 'fails': fails}
    path = 'report.json'
    print(json.dumps(report, indent=4))
    json.dump(report, open(path, 'w'), indent=4)
    return path

#
# bootstrap
#

def main(user_csvpath, max_key_age=90, grace_period_days=7):
    csv_contents = read_input(user_csvpath)
    max_key_age = int(max_key_age)
    grace_period_days = int(grace_period_days)
    results = [user_report(row, max_key_age, grace_period_days) for row in csv_contents]
    pass_rows, fail_rows = splitfilter(lambda row: row['success?'], results)
    print('wrote: ', write_report(pass_rows, fail_rows))
    return len(fail_rows)

if __name__ == '__main__':
    try:
        args = sys.argv[1:]
        arglst = ['user_csvpath', 'max_key_age', 'grace_period_days']
        ensure(len(args) > 0, "at least one argument required: path-to-csvfile")
        kwargs = dict(zip(arglst, args))
        sys.exit(main(**kwargs))
    except AssertionError as err:
        print('err:',err)
        retcode = getattr(err, 'retcode', 1)
        sys.exit(retcode)
