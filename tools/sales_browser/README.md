# Sales/Test Drive browser

A local Tkinter tool for looking at the `kng-license-issuance` DynamoDB
table (every FastSpring purchase and Test Drive record) without going to
the AWS console. Runs on your own machine with your own AWS credentials
(the same default credential chain the `aws` CLI already uses) and never
writes to the table.

## Run it

```
pip install -r requirements.txt   # boto3 -- not a dependency of the site itself
python3 app.py
```

Options: `--table NAME` (default `kng-license-issuance`), `--region NAME`
(default `us-east-1`), `--profile NAME` (default: whatever `aws` CLI
would use).

## Filters

- **From / To**: `YYYY-MM-DD`, inclusive on both ends. A purchase made
  before `created_at` existed on purchase rows won't match either bound
  -- leave both blank to see it.
- **Email contains**: case-insensitive substring match.
- **Product**: All, Server, or MIDI Player.

Results are sorted most-recent-first.
