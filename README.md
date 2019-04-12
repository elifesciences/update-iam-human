# update-iam-human

A script to rotate IAM credentials for human beings.

## Usage:

### 1. Generate a CSV file of human beings:

    $ ./generate-csv.sh

This will generate a set of CSV files that are partitions of the AWS credentials report.

The one we need is called `humans.csv` and has just three columns: `name`, `iam-username` and `email`. 

This file is used to send emails to those users. 

The `name` and `email` columns will need to be filled out if they can't be filled from an existing `humans.csv` file.

See `example.csv`.

### 2. Generate a plan of action

    $ ./update-iam.sh csv-file

This generates a list of actions to be performed and writes the plan to `$csvfile-report-$datestamp.json`.

For example, `humans-report-2019-01-01.json` typically.

Review the actions.

Do not modify the file, it will be regenerated on execution.

### 3. Execute the plan of action.

    $ ./update-iam.sh csv-file --execute

After execution a report will be written in the form of `$csvfile-results-$datestamp.json`.

For example, `humans-results-2019-01-01.json` typically.

An example report:

```json
{
    "passes": {
        "notified": [
            {
                "name": "John Doe",
                "email": "j.doe@example.org",
                "iam-username": "dummyuser1",
                "grace-period-days": 7,
                "max-key-age": 90,
                "success?": true,
                "state": "old-credentials",
                "reason": "credentials are old and will be rotated",
                "actions": [
                    [
                        "create",
                        "new"
                    ]
                ],
                "results": {
                    "create": {
                        "aws-access-key": "AKIAASDFFDSA",
                        "aws-secret-key": "[redacted]"
                    }
                },
                "gist-html-url": "[redacted]",
                "gist-id": "03f45a234f2452a345f345243",
                "gist-created-at": "2001-01-01",
                "email-id": "8d9f89asd8fa98d9a8dfa9sd",
                "email-sent": "2001-01-01",
            },
        ],
        "unnotified": [
            {
                "name": "John Doe",
                "email": "j.doe@example.org",
                "iam-username": "dummyuser2",
                "grace-period-days": 7,
                "max-key-age": 90,
                "success?": true,
                "state": "ideal",
                "reason": "1 active set of credentials younger than max age of credentials",
                "actions": [
                    [
                        "delete",
                        "AKIAIFDSASDASDSA"
                    ]
                ],
                "results": {
                    "delete": true
                }
            }
        ]
    },
    "fails": [
        {
            "name": "John Doe",
            "email": "j.doe@example.org",
            "iam-username": "NonExistantUser1",
            "success?": false,
            "state": "no-credentials",
            "reason": "no credentials exist",
            "actions": []
        }
    ]
}
```

## Requirements

* Github credentials to create a secret gist
* AWS credentials to list and update IAM users and send SES emails

Github credentials live in the file `private.json` in the root of the project and look like:

    {"key": "<your api token>"}

AWS Credentials are referenced from the usual places.

## Install

    $ ./install.sh
    
## Test

    $ ./test.sh
