"""FindCache log-upload digest Lambda: emails one daily summary of uploads.

Runs once a day (EventBridge schedule, terraform/findcache_logs.tf). It reads
the <id>.json records the upload Lambda (src/findcache_log) wrote to the logs
bucket for the previous UTC day and sends a single plain-text email through
SES to the same inbox as the contact form. No uploads means no email. Each
entry gives the time, FindCache version, device, the user's description and
the `aws s3 cp` command that fetches the log. Descriptions come from an
unauthenticated endpoint, so they are treated as untrusted: control
characters are stripped and lengths are capped, and the email is plain text.
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone

MAX_ENTRIES = 50
MAX_DESCRIPTION_CHARS = 1000
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")

_s3_client = None
_ses_client = None


def _s3():
    global _s3_client
    if _s3_client is None:
        import boto3  # bundled in the Lambda runtime; imported lazily so tests need no boto3

        _s3_client = boto3.client("s3")
    return _s3_client


def _ses():
    global _ses_client
    if _ses_client is None:
        import boto3

        _ses_client = boto3.client("ses")
    return _ses_client


def _clean(text, limit) -> str:
    return _CONTROL_RE.sub("", str(text))[:limit]


def _records(bucket: str, day: datetime) -> list:
    prefix = f"findcache/{day:%Y/%m/%d}/"
    records = []
    token = None
    while True:
        kwargs = {"Bucket": bucket, "Prefix": prefix}
        if token:
            kwargs["ContinuationToken"] = token
        page = _s3().list_objects_v2(**kwargs)
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".json"):
                body = _s3().get_object(Bucket=bucket, Key=obj["Key"])["Body"].read()
                try:
                    records.append(json.loads(body))
                except ValueError:
                    continue
        token = page.get("NextContinuationToken")
        if not token:
            return sorted((r for r in records if isinstance(r, dict)), key=lambda r: str(r.get("received", "")))


def build_digest(bucket: str, day: datetime, records: list) -> tuple:
    lines = [f"{len(records)} FindCache log upload(s) on {day:%Y-%m-%d} (UTC).", ""]
    for record in records[:MAX_ENTRIES]:
        key = _clean(record.get("log_key", ""), 200)
        lines += [
            f"{_clean(record.get('received', ''), 30)}  id {_clean(record.get('id', ''), 40)}",
            f"FindCache {_clean(record.get('app_version', ''), 32)} on {_clean(record.get('device', ''), 80)}",
            "Problem: " + (_clean(record.get("description", ""), MAX_DESCRIPTION_CHARS) or "(none given)"),
            f"aws s3 cp s3://{bucket}/{key} .",
            "",
        ]
    if len(records) > MAX_ENTRIES:
        lines.append(f"... and {len(records) - MAX_ENTRIES} more under s3://{bucket}/findcache/{day:%Y/%m/%d}/")
    return f"FindCache log uploads {day:%Y-%m-%d}: {len(records)}", "\n".join(lines)


def handler(event, context):
    bucket = os.environ["LOG_BUCKET"]
    day = datetime.now(timezone.utc) - timedelta(days=1)
    records = _records(bucket, day)
    if not records:
        return {"sent": False, "uploads": 0}
    subject, text = build_digest(bucket, day, records)
    _ses().send_email(
        Source=os.environ["SES_SENDER"],
        Destination={"ToAddresses": [os.environ["SES_RECIPIENT"]]},
        Message={"Subject": {"Data": subject}, "Body": {"Text": {"Data": text}}},
    )
    return {"sent": True, "uploads": len(records)}
