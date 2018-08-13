from src import main
from src.main import ensure
import pytest
from datetime import timedelta
from unittest.mock import patch

def test_ensure():
    ensure(1 == 1, "working")
    with pytest.raises(AssertionError):
        ensure(1 == 2, "not working")    

def test_rotate_very_old_credentials():
    """a user with a single, very old credential will go through these steps:
    1. create new credential
    2. wait until grace period is up
    3. disable old credential"""
    test_csv_row = {'iam-username': 'FooBar'}
    today = main.utcnow()
    two_years_ago = today - timedelta(days=(365*2))
    key_list = [
        {'access_key_id': 'AKIA-DUMMY', 'create_date': two_years_ago, 'status': 'Active'} # 'Active' or 'Inactive'
    ]
    max_key_age = 90 # days
    grace_period = 7 # days

    with patch('src.main.key_list', return_value=key_list):
        updated_csv_row = main.user_report(test_csv_row, max_key_age, grace_period)

    expected_actions = [
        ('create', 'new')
    ]
    assert expected_actions == updated_csv_row['actions']

    # assume the report is exected and that new key for this user is created,
    # zip forward $grace-period + 1 days and run the report again
    a_graceperiod_from_now = today + timedelta(days=grace_period + 1)
    key_list.append({'access_key_id': 'AKIA-DUMMY2', 'create_date': today, 'status': 'Active'})
    with patch('src.main.key_list', return_value=key_list):
        with patch('src.main.utcnow', return_value=a_graceperiod_from_now):
            future_csv_row = main.user_report(test_csv_row, max_key_age, grace_period)

    expected_actions = [
        ('disable', 'AKIA-DUMMY'),
    ]
    assert expected_actions == future_csv_row['actions']

def test_multiple_active_credentials():
    """multiple active credentials no longer supported, the oldest will be disabled after a grace period. 
    max key age on youngest is ignored for simplicity"""
    # note: only exeter match this case and they are being handled separately
    test_csv_row = {'iam-username': 'FooBar'}
    two_days_ago = main.utcnow() - timedelta(days=2)
    three_days_ago = main.utcnow() - timedelta(days=3)
    max_key_age, grace_period = 90, 7
    key_list = [
        {'access_key_id': 'AKIA-DUMMY1', 'create_date': three_days_ago, 'status': 'Active'},
        {'access_key_id': 'AKIA-DUMMY2', 'create_date': two_days_ago, 'status': 'Active'}
    ]
    with patch('src.main.key_list', return_value=key_list):
        updated_csv_row = main.user_report(test_csv_row, max_key_age, grace_period)
    expected_actions = [] # nothing to do
    assert expected_actions == updated_csv_row['actions']
    assert main.GRACE_PERIOD == updated_csv_row['state']

def test_credentials_full():
    "when there is one old but active credentials and one inactive credentials"
    test_csv_row = {'iam-username': 'FooBar'}
    two_days_ago = main.utcnow() - timedelta(days=2)
    three_days_ago = main.utcnow() - timedelta(days=3)
    max_key_age, grace_period = 1, 7
    key_list = [
        {'access_key_id': 'AKIA-DUMMY1', 'create_date': three_days_ago, 'status': 'Inactive'},
        {'access_key_id': 'AKIA-DUMMY2', 'create_date': two_days_ago, 'status': 'Active'}
    ]
    with patch('src.main.key_list', return_value=key_list):
        updated_csv_row = main.user_report(test_csv_row, max_key_age, grace_period)
    expected_actions = [('delete', 'AKIA-DUMMY1'), ('create', 'new')] # order is important
    assert expected_actions == updated_csv_row['actions']
    assert main.OLD_CREDENTIALS == updated_csv_row['state']

def test_credentials_empty():
    "when there are no credentials to work with"
    test_csv_row = {'iam-username': 'FooBar'}
    max_key_age, grace_period = 90, 7
    key_list = []
    with patch('src.main.key_list', return_value=key_list):
        updated_csv_row = main.user_report(test_csv_row, max_key_age, grace_period)
    expected_actions = [] # nothing
    assert expected_actions == updated_csv_row['actions']
    assert main.NO_CREDENTIALS == updated_csv_row['state']
    assert False == updated_csv_row['success?']

def test_delete_single_inactive_credential():
    "any disabled credentials will be deleted"
    test_csv_row = {'iam-username': 'FooBar'}
    two_days_ago = main.utcnow() - timedelta(days=2)
    max_key_age, grace_period = 90, 7
    key_list = [{'access_key_id': 'AKIA-DUMMY', 'create_date': two_days_ago, 'status': 'Inactive'}]
    with patch('src.main.key_list', return_value=key_list):
        updated_csv_row = main.user_report(test_csv_row, max_key_age, grace_period)
    expected_actions = [('delete', 'AKIA-DUMMY')]
    assert expected_actions == updated_csv_row['actions']
    assert main.NO_CREDENTIALS_ACTIVE == updated_csv_row['state']

def test_delete_multiple_inactive_credentials():
    "any disabled credentials will be deleted"
    test_csv_row = {'iam-username': 'FooBar'}
    two_days_ago, two_months_ago = main.utcnow() - timedelta(days=2), main.utcnow() - timedelta(days=28*2)
    max_key_age, grace_period = 90, 7
    key_list = [
        {'access_key_id': 'AKIA-DUMMY1', 'create_date': two_days_ago, 'status': 'Inactive'},
        {'access_key_id': 'AKIA-DUMMY2', 'create_date': two_months_ago, 'status': 'Inactive'}
    ]
    with patch('src.main.key_list', return_value=key_list):
        updated_csv_row = main.user_report(test_csv_row, max_key_age, grace_period)
    expected_actions = [('delete', 'AKIA-DUMMY1'), ('delete', 'AKIA-DUMMY2')]
    assert expected_actions == updated_csv_row['actions']
    assert main.NO_CREDENTIALS_ACTIVE == updated_csv_row['state']
