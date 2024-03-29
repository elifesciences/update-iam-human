# update-iam-human

A script to rotate IAM credentials of human beings.

1. using a list of human beings, 

## Usage:

### 1. Generate a CSV file of human beings:

    $ ./generate-csv.sh

This will generate a set of CSV files using the results of the AWS credentials report.

The one we need is called `humans.csv` and has just three columns: `name`, `iam-username` and `email`. 

This file is used to send emails to those users.

The `name` and `email` columns **must be** filled.

Copying the `humans.csv` file from it-admin into `private` will save some time filling in missing names and emails.

See `example.csv`.

### 2. Generate a plan of action

    $ ./update-iam.sh csv-file

This generates a list of actions to be performed and writes the plan to `$csvfile-report-$datestamp.json`.

For example, `humans-report-2019-01-01.json`

Review the actions to be taken.

Do not modify the file, it will be regenerated on execution. Instead, modify AWS IAM and `humans.csv` if necessary and re-run `update-iam.sh`.

When credentials must be rotated earlier than the default rotation age (180 days), specify a `--max-key-age`.

For example, to rotate *all* credentials *now*, do:

    $ ./update-iam.sh csv-file --max-key-age=0

To force the rotation of credentials that are mid-transition (the grace period hasn't expired yet and two sets of 
credentials exist), a shorter grace period can be set:

    $ ./update-iam.sh csv-file --grace-period=0

### 3. Execute the plan of action.

    $ ./update-iam.sh csv-file --execute

After execution a report will be written in the form of `$csvfile-results-$datestamp.json`.

For example, `humans-results-2019-01-01.json`


## missing features

`update-iam-human` does *not*:

* notify a user when credentials are disabled
* delete the generated Github Gists as users update their credentials

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
