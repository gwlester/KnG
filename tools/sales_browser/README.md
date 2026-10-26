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

On most modern systems, the system Python refuses a plain `pip install`
("externally managed environment") -- use a virtual environment:

```
python3 -m venv .venv
source .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install -r requirements.txt   # boto3 -- not a dependency of the site itself
aws login
python3 app.py
```

Every time you come back to run it again, just `source .venv/bin/activate`
first (no need to re-run `pip install`). If you see "No module named
boto3" when using Add/Refresh, this step was skipped or you're running
a different `python3` than the one `pip install` used.

If AWS commands/credentials come from the newer `aws login` (browser-based)
flow rather than a static key or SSO profile, and you see
`MissingDependencyException: ... pip install "botocore[crt]"` when using
Add/Refresh, that's `requirements.txt`'s `botocore[crt]` line not having
installed cleanly -- re-run `pip install -r requirements.txt` inside the
venv.

Options: `--table NAME` (default `kng-license-issuance`),
`--beta-testers-table NAME` (default `kng-beta-testers`), `--region NAME`
(default `us-east-1`), `--profile NAME` (default: whatever `aws` CLI
would use).

## File menu

- **Refresh** (Ctrl+R): refreshes whichever tab is currently active.
- **Set Log Level**: Debug/Info/Warning/Error, applies immediately.
- **View Logs...**: shows the current log file in a window. The log
  file itself lives at `~/.kng-license-management/logs/license_management.log`
  and is appended to across runs (not truncated on start).

## Filtering (both tabs)

Click **Filters...** to open a modal dialog: a checkbox each for a From
and To date (a calendar popup appears when its checkbox is checked --
there's no plain typed date field), an Email contains box, and -- Sales
tab only -- a Product dropdown. **Apply** re-filters instantly from
already-loaded data (no new AWS call); **Clear Filters** resets to
showing everything; **Clear Filters** and **Cancel** both close the
dialog. Active filters show as small labels under the action buttons
("From: 2026-10-01", "Email: pastor", ...) so it's obvious at a glance
whether you're looking at a filtered view -- "No filters applied."
when you're not.

- **From / To**: inclusive on both ends. A purchase made before
  `created_at` existed on purchase rows (or a beta tester added before
  this tool tracked `added_at`) won't match either bound -- leave both
  unchecked to see it regardless.
- **Email contains**: case-insensitive substring match.
- **Product** (Sales tab only): All, Server, or MIDI Player.

Both tabs' results are sorted most-recent-first. Each tab also
auto-loads the first time you switch to it (and the Sales tab loads
immediately at launch, since it's already showing) -- after that,
Refresh is manual, so a filter change never gets overwritten by a
surprise reload.

## Beta Testers

One email per row, approved for both products at once (there's no
per-product approval). Add prompts for an email (normalized to
lowercase, same as the Lambdas that check this table) and stamps it
with the current time; Remove deletes the selected row immediately
after a confirmation. Removing someone takes effect on their next Test
Drive request or download attempt -- it doesn't revoke an access code
already issued and still within its 90-day window in advance.
