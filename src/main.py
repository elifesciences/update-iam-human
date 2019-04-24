import getpass
import argparse
import boto3
import sys, os, csv
from github import Github
from github.InputFileContent import InputFileContent
import json
from datetime import timedelta
from collections import OrderedDict
from . import utils
from .utils import ensure, ymd, splitfilter, vals, lmap, lfilter, utcnow

MAX_KEY_AGE_DAYS, GRACE_PERIOD_DAYS = 180, 7

# states

UNKNOWN = '?'
USER_NOT_FOUND = 'user-not-found'

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
    USER_NOT_FOUND: "user not found",
    MANY_CREDENTIALS: "more than 2 sets of credentials exist (program error)",
    UNKNOWN: "credentials are in an unhandled state (program error)"
}

def current_user():
    # username => signature
    mapping = {
        'luke': 'Luke Skibinski',
        'giorgio': 'Giorgio Sironi'
    }
    return mapping[getpass.getuser()]

#
# aws IAM
#

INPUT_HEADER = ['name', 'email', 'iam-username']

def validate_row(row):
    ensure(isinstance(row, dict), "row must be a dictionary: %s" % (type(row),))
    name, email, username = vals(row, 'name', 'email', 'iam-username')
    ensure(name and email and username, "bad-value: all values in a row must be present: %s" % (row,))
    ensure('@' in email and '.' in email, "bad-value: email doesn't look like an email to me: %s" % (email,))
    return True

def read_input(user_csvpath):
    ensure(os.path.exists(user_csvpath), "path not found: %s" % user_csvpath)
    ensure(os.path.isfile(user_csvpath), "path is not a file: %s" % user_csvpath)
    with open(user_csvpath) as fh:
        rows = list(csv.DictReader(fh, fieldnames=INPUT_HEADER))
        ensure(len(rows) > 1, "csv file is empty")
        header = list(rows.pop(0).keys()) # skip the header
        ensure(header == INPUT_HEADER, "csv file has incorrect header: %s" % header)
        lmap(validate_row, rows)
        return rows

def coerce_key(kp):
    return {
        'access_key_id': kp.access_key_id,
        'create_date': kp.create_date,
        'status': kp.status,
        '-obj': kp,
    }

def _get_user(iam_username):
    try:
        iam = boto3.resource('iam')
        iamuser = iam.User(iam_username)
        iamuser.load()
        return iamuser
    except Exception as err:
        print('warning: %s' % str(err))
        return None

def key_list(iam_username):
    _user = _get_user(iam_username)
    return lmap(coerce_key, _user.access_keys.all()) if _user else None

def get_key(iam_username, key_id):
    keys = lfilter(lambda kp: kp['access_key_id'] == key_id, key_list(iam_username))
    if len(keys) == 1:
        return keys[0]

def user_report(user_csvrow, max_key_age, grace_period_days):
    "given a row, returns the same row with a list of action"
    try:
        today = utcnow()
        state = UNKNOWN
        actions = []

        access_keys = key_list(user_csvrow['iam-username'])
        ensure(access_keys is not None, USER_NOT_FOUND)

        ensure(len(access_keys) > 0, NO_CREDENTIALS)
        ensure(len(access_keys) < 3, MANY_CREDENTIALS) # there must only ever be 0, 1 or 2 keys

        # carry some state around with us for future ops
        user_csvrow.update({
            'grace-period-days': grace_period_days,
            'max-key-age': max_key_age
        })

        active_keys, inactive_keys = splitfilter(lambda key: key['status'] != 'Inactive', access_keys)

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

        elif len(active_keys) == 1:
            active_key = active_keys[0]
            # if max_key_age <= 1, you get a 'create' action on every call
            if (today - active_key['create_date']).days <= max_key_age:
                state = IDEAL
            else:
                # remaining key is too old
                state = OLD_CREDENTIALS
                actions += [
                    ('create', 'new')
                ]
        else:
            state = NO_CREDENTIALS_ACTIVE

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
    print('deleting key for', iam_username)
    key = get_key(iam_username, key_id)
    if key:
        key['-obj'].delete()
        return True
    return False

def disable_key(iam_username, key_id):
    print('disabling key for', iam_username)
    key = get_key(iam_username, key_id)
    if key:
        key['-obj'].deactivate()
        return True
    return False

def create_key(iam_username, _):
    print('creating key for', iam_username)
    iamuser = _get_user(iam_username)
    key = iamuser.create_access_key_pair()
    return {'aws-access-key': key.access_key_id,
            'aws-secret-key': key.secret_access_key}

def execute_user_report(user_report_data):
    ensure(isinstance(user_report_data, dict), "user-report must be a dict")
    dispatch = {
        'delete': delete_key,
        'disable': disable_key,
        'create': create_key,
    }
    iam_username = user_report_data['iam-username']
    actions = user_report_data['actions']
    results = [(fnkey, dispatch[fnkey](iam_username, val)) for fnkey, val in actions]
    # weakness: no more than one type of action per execution else results get squashed
    # for example, can't do two 'disables' or two 'deletes'. not a problem right now
    user_report_data['results'] = OrderedDict(results)
    return user_report_data

def execute_report(report_data):
    "executes the list of actions against each user in the given report data."
    ensure(isinstance(report_data, list), "report data must be a list of user-report dicts")
    return lmap(execute_user_report, report_data)


#
# github gist
#

# ll: {'key': 'github-api-token'}
GH_CREDENTIALS_FILE = os.path.abspath("private.json")

def gh_credentials():
    return json.load(open(GH_CREDENTIALS_FILE, 'r'))

def gh_user():
    "returns a user that can create gists"
    credentials = gh_credentials()
    gh = Github(credentials['key'])
    return gh.get_user()

def create_gist(description, content):
    public = False
    authenticated_user = gh_user()
    content = InputFileContent(content)
    gist = authenticated_user.create_gist(public, {'content': content}, description)
    return {
        'gist-html-url': gist.html_url,
        'gist-id': gist.id,
        'gist-created-at': gist.created_at
    }

def gh_create_user_gist(user_csvrow):
    ensure('results' in user_csvrow, "`gh_create_user_gist` requires the results of calling `execute_user_report`")
    content = '''Hello, {insert-name-of-human}

Your new AWS credentials are:

aws_access_key_id={insert-access-key}
aws_secret_access_key={insert-secret-key}

Your old credentials and this message will expire on {insert-expiry-date}.'''

    new_key = user_csvrow['results']['create']
    content = content.format_map({
        'insert-name-of-human': user_csvrow['name'],
        'insert-access-key': new_key['aws-access-key'],
        'insert-secret-key': new_key['aws-secret-key'],
        'insert-expiry-date': ymd(utcnow() + timedelta(days=user_csvrow['grace-period-days'])),
    })
    print('creating gist for', user_csvrow['name'])
    gist = create_gist("new AWS API credentials", content)
    user_csvrow.update(gist)
    # nullify the secret key, we no longer need it
    user_csvrow['results']['create']['aws-secret-key'] = '[redacted]'
    return user_csvrow


#
# email
#

EMAIL_FROM = 'it-admin@elifesciences.org' # verified SES address
EMAIL_DEV_ADDR = 'tech-team@elifesciences.org'

def send_email(to_addr, subject, content):
    # https://boto3.readthedocs.io/en/latest/reference/services/ses.html?highlight=ses#client
    ses = boto3.client('ses', region_name='us-east-1')

    # https://boto3.readthedocs.io/en/latest/reference/services/ses.html?highlight=ses#SES.Client.send_email
    kwargs = {
        'Source': EMAIL_FROM,
        'Destination': {'ToAddresses': [to_addr]},
        'Message': {
            'Subject': {'Charset': 'UTF-8', 'Data': subject},
            'Body': {'Text': {'Charset': 'UTF-8', 'Data': content}}
        },
        'ReplyToAddresses': [EMAIL_FROM],
        'ReturnPath': EMAIL_DEV_ADDR,
    }
    return ses.send_email(**kwargs)

def email_user__old_credentials_disabled(user_csvrow):
    ensure('results' in user_csvrow, "`email_user__old_credentials_disabled` requires the results of calling `execute_user_report`")
    ensure('disable' in user_csvrow['results'] and user_csvrow['results']['disable'],
           "`email_user__old_credentials_disabled` requires a key was successfully disabled")
    disabled_credential_key = dict(user_csvrow['actions'])['disable']
    name, to_addr = vals(user_csvrow, 'name', 'email')
    subject = 're: Replacement AWS credentials'
    content = '''Hello {insert-name-of-human},

The grace period for updating your AWS credentials is over and "{insert-disabled-credential-key}" has been disabled.

You can find your new credentials linked to in our previous email.

Please contact it-admin@elifesciences.org if you have any problems.

---

This email is not spam, is not a scam and if you have *any* doubts whatsoever about it's authenticity,
please contact someone in the IT team first.

This email was generated {todays-date} by {author} using this program: 
https://github.com/elifesciences/update-iam-human'''
    content = content.format_map({
        'insert-name-of-human': user_csvrow['name'],
        'insert-disabled-credential-key': disabled_credential_key,
        'insert-grace-period': user_csvrow['grace-period-days'],
        'todays-date': ymd(utcnow()),
        'author': current_user()
    })
    print('sending email %r to %s (%s)' % (subject, user_csvrow['name'], to_addr))
    result = send_email(to_addr, subject, content)
    user_csvrow.update({
        'disabled-email-id': result['MessageId'], # probably not at all useful
        'disabled-email-sent': utcnow(),
    })
    return user_csvrow


def email_user__new_credentials(user_csvrow):
    ensure('gist-html-url' in user_csvrow, "`email_user__new_credentials` requires the results of calling `gh_create_user_gist`")
    name, to_addr = vals(user_csvrow, 'name', 'email')
    subject = 'Replacement AWS credentials'
    content = '''Hello {insert-name-of-human},

Your AWS credentials are being rotated.

This means a new set of credentials has been created for you and any
old credentials will be removed after the grace period ({insert-expiry-date}).

Your new set of credentials can be found here:
{insert-gist-url}

Please contact it-admin@elifesciences.org if you have any problems.

---

This email is not spam, is not a scam and if you have *any* doubts whatsoever about it's authenticity,
please contact someone in the IT team first.

This email was generated {todays-date} by {author} using this program: 
https://github.com/elifesciences/update-iam-human'''
    content = content.format_map({
        'insert-name-of-human': user_csvrow['name'],
        'insert-expiry-date': ymd(utcnow() + timedelta(days=user_csvrow['grace-period-days'])),
        'insert-gist-url': user_csvrow['gist-html-url'],
        'todays-date': ymd(utcnow()),
        'author': current_user()
    })
    print('sending email to %s (%s)' % (user_csvrow['name'], to_addr))
    result = send_email(to_addr, subject, content)
    user_csvrow.update({
        'email-id': result['MessageId'], # probably not at all useful
        'email-sent': utcnow(),
    })
    # nullify the gist html url, it contains the secret key
    user_csvrow['gist-html-url'] = '[redacted]'
    return user_csvrow


#
# report wrangling
#

def notify(report_results):
    "notifies users after executing actions in report"
    # TODO: should user be notified if credentials have been disabled after a grace period?
    # create a gist for those users with new credentials
    users_w_new_credentials, unnotified = splitfilter(lambda row: 'create' in row['results'], report_results)
    users_w_gists = lmap(gh_create_user_gist, users_w_new_credentials)
    results = lmap(email_user__new_credentials, users_w_gists)
    return {'notified': results, 'unnotified': unnotified}

def write_report(user_csvpath, passes, fails, executed):
    report = {'passes': passes, 'fails': fails}
    type_of_content = 'results' if executed else 'report'
    path = os.path.splitext(os.path.basename(user_csvpath))[0]
    path = '%s-%s-%s.json' % (path, type_of_content, ymd(utcnow())) # "humans-results-2019-01-01.json"
    data = utils.lossy_json_dumps(report, indent=4)
    print(data)
    with open(path, 'w') as fh:
        fh.write(data)
    return path

def main(user_csvpath, max_key_age=MAX_KEY_AGE_DAYS, grace_period_days=GRACE_PERIOD_DAYS, execute=False):
    csv_contents = read_input(user_csvpath)
    max_key_age, grace_period_days = lmap(int, [max_key_age, grace_period_days])
    print('querying %s users ...' % len(csv_contents))
    results = [user_report(row, max_key_age, grace_period_days) for row in csv_contents]
    pass_rows, fail_rows = splitfilter(lambda row: row['success?'], results)

    if not pass_rows:
        # nothing to do
        return len(fail_rows)

    print(utils.lossy_json_dumps(pass_rows, indent=4))

    if execute:
        results = execute_report(pass_rows)
        results = notify(results)

    print('wrote: ', write_report(user_csvpath, results, fail_rows, execute))

    return 0

if __name__ == '__main__':
    try:
        ensure(os.path.exists(GH_CREDENTIALS_FILE), "no github credentials found: %s" % GH_CREDENTIALS_FILE)
        parser = argparse.ArgumentParser()
        parser.add_argument('user_csvpath')
        parser.add_argument('--execute', default=False, action='store_true')
        parser.add_argument('--max-key-age', default=MAX_KEY_AGE_DAYS)
        parser.add_argument('--grace-period-days', default=GRACE_PERIOD_DAYS)
        kwargs = parser.parse_args().__dict__ # "{'user_csvpath': 'example.csv', 'execute': False, 'max_key_age': 180, 'grace_period_days': 7}"
        sys.exit(main(**kwargs))
    except AssertionError as err:
        print('err:', err)
        retcode = getattr(err, 'retcode', 1)
        sys.exit(retcode)
