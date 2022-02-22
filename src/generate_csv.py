"generates the csv input for `update_iam_human.main`"

import boto3
from .utils import ensure, first, splitfilter, select_keys, keys
import time
import sys
import os
import csv

def client():
    return boto3.client('iam')

def coerce(row):
    value_lookups = {
        'false': False,
        'true': True,
        'N/A': None,
        'no_information': None # wtf? treat as N/A
    }
    return {key: value_lookups.get(val, val) for key, val in row.items()}

def load_csv(path):
    with open(path, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        return [coerce(row) for row in reader]

def dump_csv(path, list_of_dicts):
    with open(path, 'w') as csvfile:
        fieldnames = keys(first(list_of_dicts))
        writer = csv.DictWriter(csvfile, fieldnames)
        writer.writeheader()
        for row in list_of_dicts:
            writer.writerow(row)
    return path

def num_uppercase(string):
    return sum(1 for char in string if char.isupper())

def idx(key, data_list):
    return {row.get(key): row for row in data_list}

# ---

def generate_credential_report():
    iam = client()
    print('requesting report')
    while True:
        resp = iam.generate_credential_report()
        # only three possible states. the other is 'COMPLETED'
        if resp['State'] not in ['STARTED', 'INPROGRESS']:
            print('done.')
            break
        sys.stdout.write('polling ... ')
        time.sleep(2) # seconds
    ensure(resp['State'] == 'COMPLETE', "failed to generate credential report. final response: %s" % resp)
    resp = iam.get_credential_report()
    ensure(resp['ResponseMetadata']['HTTPStatusCode'] == 200, "failed to download credential report. final response: %s" % resp)
    ensure(resp['ReportFormat'] == 'text/csv', "unexpected report format %r. final response: %s" % (resp['ReportFormat'], resp))
    filename = 'private/credentials-report.csv'
    open(filename, 'wb').write(resp['Content'])
    print("wrote %r" % filename)
    return filename

def partition_report(path_to_credentials_report):
    """splits the AWS credentials report into three: humans, machines and needs-review.
    interesting humans have either access keys 1 or 2 active, or a password enabled, and at least two uppercase letters in their name.
    The rest are MACHINES or candidates for review"""
    ensure(os.path.exists(path_to_credentials_report), "credentials report does not exist")
    report = load_csv(path_to_credentials_report)

    # humans with machine names
    exceptions = [
        '<root_account>',
        'nathanlisgo',
        'james_gilbert',
        'melissa_harrison'
    ]

    no_access_users, rest_of_report = splitfilter(lambda row: not any(select_keys(row, ['access_key_1_active', 'access_key_2_active', 'password_enabled'])), report)
    probable_humans, machines = splitfilter(lambda row: row['user'] in exceptions or num_uppercase(row['user']) >= 2, rest_of_report)

    report_list = [
        (no_access_users, 'private/no-access-users-needing-review-report.csv'),
        (probable_humans, 'private/humans-report.csv'),
        (machines, 'private/machines-report.csv')
    ]
    for rows, filename in report_list:
        dump_csv(filename, rows)
        print("wrote %r" % filename)

def generate_humans_file(humans_csv):
    """using the list of humans derived from the credentials report, create a three column csv file for use as input to `update_iam_human.main`.
    re-uses an existing humans.csv file if found."""
    outfile = "private/humans.csv"

    # this file may be old, contain partial information or non-existant
    # you can find a copy in `it-admin/humans.csv`
    humans_idx = idx('iam-username', load_csv(outfile)) if os.path.exists(outfile) else {}

    report_rows = sorted(load_csv(humans_csv), key=lambda row: row['user'])
    rows = []
    for row in report_rows:
        # we can't affect this user
        if row['user'] == '<root_account>':
            continue
        human = humans_idx.get(row['user'], {}) # we join on 'iam-username'
        rows.append({
            'name': human.get('name'),
            'email': human.get('email'),
            'iam-username': human.get('iam-username', row['user'])
        })
    dump_csv(outfile, rows)
    print("wrote %r <-- this is what you want" % outfile)
    return outfile

if __name__ == "__main__":
    os.system("mkdir -p private")
    credential_report = generate_credential_report()
    partition_report(credential_report)
    generate_humans_file("private/humans-report.csv")
