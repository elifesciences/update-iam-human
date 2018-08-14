from src import main
from src import utils
from datetime import timedelta, datetime
from unittest.mock import patch, DEFAULT

def test_rotate_very_old_credentials():
    """a user with a single, very old credential will go through these steps:
    1. create new credential
    2. wait until grace period is up
    3. disable old credential
    4. call again (next day presumably)
    5. delete any disabled credentials
    """
    test_csv_row = {'iam-username': 'FooBar'}
    today = utils.utcnow()
    two_years_ago = today - timedelta(days=(365*2))
    max_key_age = 90 # days
    grace_period = 7 # days

    # 1. very old key
    key_list = [
        {'access_key_id': 'AKIA-DUMMY', 'create_date': two_years_ago, 'status': 'Active'} # 'Active' or 'Inactive'
    ]
    with patch('src.main.key_list', return_value=key_list):
        updated_csv_row = main.user_report(test_csv_row, max_key_age, grace_period)

    expected_actions = [
        ('create', 'new')
    ]
    assert expected_actions == updated_csv_row['actions']


    # 2. assume the report is executed and that new key for this user is created,
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

    
    # 3. now that the old key is deactivated, it will be deleted on the next execution
    key_list = [
        {'access_key_id': 'AKIA-DUMMY', 'create_date': two_years_ago, 'status': 'Inactive'}, # original key, now inactive
        {'access_key_id': 'AKIA-DUMMY2', 'create_date': today, 'status': 'Active'}, # new key, just created
    ]
    with patch('src.main.key_list', return_value=key_list):
        # date doesn't matter but lets be consistent
        with patch('src.main.utcnow', return_value=a_graceperiod_from_now):
            future_csv_row2 = main.user_report(test_csv_row, max_key_age, grace_period)

    expected_actions = [
        ('delete', 'AKIA-DUMMY')
    ]
    assert expected_actions == future_csv_row2['actions']

def test_multiple_active_credentials():
    """multiple active credentials no longer supported, the oldest will be disabled after a grace period. 
    max key age on youngest is ignored for simplicity"""
    # note: only exeter match this case and they are being handled separately
    test_csv_row = {'iam-username': 'FooBar'}
    two_days_ago = utils.utcnow() - timedelta(days=2)
    three_days_ago = utils.utcnow() - timedelta(days=3)
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
    two_days_ago = utils.utcnow() - timedelta(days=2)
    three_days_ago = utils.utcnow() - timedelta(days=3)
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
    two_days_ago = utils.utcnow() - timedelta(days=2)
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
    two_days_ago, two_months_ago = utils.utcnow() - timedelta(days=2), utils.utcnow() - timedelta(days=28*2)
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

#
#
#

def test_execute_user_report():
    actions = [('delete', 'AKIA-DUMMY1'), ('disable', 'AKIA-DUMMY2'), ('create', 'new')]
    test_user_report = {
        'iam-username': 'FooBar',
        #'success?': True, 'state': 'ideal', 'reason': '...', # unnecessary to execute report
        'actions': actions
    }

    with patch.multiple('src.main', delete_key=DEFAULT, disable_key=DEFAULT, create_key=DEFAULT) as mocks:
        results = main.execute_user_report(test_user_report)

        # test each of the mocks was called ...
        assert mocks['delete_key'].call_count == 1
        assert mocks['disable_key'].call_count == 1
        assert mocks['create_key'].call_count == 1

        # and in the correct order ...
        # results are keyed by their action, the result values are just mocks
        expected = utils.lmap(utils.first, actions)
        assert expected == list(results['results'].keys())

#
#
#

def test_create_user_gist():
    test_user_result = {
        'name': 'Pants',
        'grace-period-days': 7,
        'results': {'create': {'aws-access-key': 'AKIA-DUMMY', 'aws-secret-key': 'as89dffds9a'}},
    }
    mock_gist = {'gist-html-url': 'https://example.org', 'gist-id': -1, 'gist-created-at': datetime(year=2001, month=1, day=1)}
    with patch('src.main.create_gist', return_value=mock_gist):
        result = main.gh_create_user_gist(test_user_result)

    expected = test_user_result.copy()
    expected.update(mock_gist)
        
    assert expected == result

#
#
#

def test_email_user__new_credentials():
    test_user_result = {
        'name': 'Pants', 'email': 'foo@example.org',
        'grace-period-days': 7,

        'gist-html-url': 'https://example.org',
        'gist-id': -1,
        'gist-created-at': datetime(year=2001, month=1, day=1)
    }
    with patch('src.main.send_email'):
        result = main.email_user__new_credentials(test_user_result)
    assert 'email-sent' in result
