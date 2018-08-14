# update-iam-human

A script designed to rotate IAM credentials.

## Usage:

    $ ./update-iam.sh csv-file

The `csv-file` should have the columns `name`, `email`, `iam-username`. See `example.csv`.

After execution a report will be written in the form of `inputfname-report.json`.

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
