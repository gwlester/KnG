# License management desktop

A local Tkinter tool with two tabs:

- **Sales & Test Drives** (read-only): browses `kng-license-issuance`
  (every FastSpring purchase and Test Drive record) without going to
  the AWS console.
- **Beta Testers**: add/remove approved emails in `kng-beta-testers` --
  the allowlist `trial.html`'s Test Drive request checks before issuing
  anyone a beta access code.

Runs on your own machine with your own AWS credentials (the same
default credential chain the `aws` CLI already uses). The Sales tab
never writes to its table; the Beta Testers tab does (that's its whole
purpose).

## Run it

```
pip install -r requirements.txt   # boto3 -- not a dependency of the site itself
python3 app.py
```

Options: `--table NAME` (default `kng-license-issuance`),
`--beta-testers-table NAME` (default `kng-beta-testers`), `--region NAME`
(default `us-east-1`), `--profile NAME` (default: whatever `aws` CLI
would use).

## Sales & Test Drives filters

- **From / To**: `YYYY-MM-DD`, inclusive on both ends. A purchase made
  before `created_at` existed on purchase rows won't match either bound
  -- leave both blank to see it.
- **Email contains**: case-insensitive substring match.
- **Product**: All, Server, or MIDI Player.

Results are sorted most-recent-first.

## Beta Testers

One email per row, approved for both products at once (there's no
per-product approval). Add prompts for an email and stamps it with the
current time; Remove deletes the selected row immediately after a
confirmation. Removing someone takes effect on their next Test Drive
request or download attempt -- it doesn't revoke an access code
already issued and still within its 90-day window in advance.
