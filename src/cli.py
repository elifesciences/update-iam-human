"creates a temporary csv file for a single user and feeds it to update-iam-human script"

import csv, tempfile
from . import main
import argparse

def prompt(field):
    uin = input("%s: " % field)
    return uin

def cli_main(execute=False, **kwargs):
    field_names = ['name', 'email', 'iam-username']
    try:
        with tempfile.NamedTemporaryFile('w+') as csv_path:
            writer = csv.writer(csv_path, field_names)
            writer.writerow(field_names)

            #row = ['Luke Test', 'l.skibinski@elifesciences.org', 'LukeTest']
            row = list(map(prompt, field_names))
            writer.writerow(row)

            csv_path.seek(0)
            main.main(csv_path.name, execute=execute, **kwargs)

    except KeyboardInterrupt:
        print('ctrl-c caught, quitting')

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', default=False, action='store_true')
    parser.add_argument('--max-key-age', default=main.MAX_KEY_AGE_DAYS)
    parser.add_argument('--grace-period-days', default=main.GRACE_PERIOD_DAYS)
    kwargs = parser.parse_args().__dict__ # {'execute': False}
    cli_main(**kwargs)
