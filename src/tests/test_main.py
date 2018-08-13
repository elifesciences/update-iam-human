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
    test_csv_row = {
        # not used in func
        'name': '',
        'email': '',
        'iam-username': 'FooBar'
    }
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

