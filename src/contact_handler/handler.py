"""Contact-form Lambda: validates a JSON POST and emails it through SES.

Request body (FormatVersion 1):
  {"FormatVersion": 1, "name": str, "email": str, "message": str, "website": str,
   "topic": str (optional), "organization": str (optional)}
"website" is a honeypot -- real visitors never fill it in. "topic" and
"organization" were added later as optional fields; requests without them
are still valid, so FormatVersion stays 1.
"""

import base64
import json
import os
import re

FORMAT_VERSION = 1
MAX_NAME = 100
MAX_EMAIL = 254
MAX_MESSAGE = 5000
MAX_ORGANIZATION = 100
TOPICS = {
    "general": "General question",
    "customization": "Customization",
    "hymnal": "Hymnal metadata consultation",
    "hardware": "Hardware buildout",
    "purchase": "Purchase question",
    "publisher": "Publisher inquiry",
}
EMAIL_RE = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")

_ses = None


def _client():
    global _ses
    if _ses is None:
        import boto3  # bundled in the Lambda runtime; imported lazily so tests need no boto3

        _ses = boto3.client("ses")
    return _ses


def _response(status: int, ok: bool, error: str = "") -> dict:
    body = {"ok": ok}
    if error:
        body["error"] = error
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _parse_body(event: dict) -> dict:
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("body must be a JSON object")
    return data


def _clean_line(value: str) -> str:
    return re.sub(r"[\r\n\t]+", " ", value).strip()


def handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    if method != "POST":
        return _response(405, False, "Method not allowed")

    allowed = [o for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o]
    origin = (event.get("headers") or {}).get("origin")
    if allowed and origin and origin not in allowed:
        return _response(403, False, "Origin not allowed")

    try:
        data = _parse_body(event)
    except (ValueError, UnicodeDecodeError):
        return _response(400, False, "Invalid request")

    if data.get("FormatVersion") != FORMAT_VERSION:
        return _response(400, False, "Unsupported FormatVersion")

    if str(data.get("website", "")).strip():
        return _response(200, True)

    name = _clean_line(str(data.get("name", "")))
    email = str(data.get("email", "")).strip()
    message = str(data.get("message", "")).strip()
    topic = str(data.get("topic") or "general")
    organization = _clean_line(str(data.get("organization") or ""))

    if not name or len(name) > MAX_NAME:
        return _response(400, False, "Please enter your name.")
    if not email or len(email) > MAX_EMAIL or not EMAIL_RE.match(email):
        return _response(400, False, "Please enter a valid email address.")
    if not message or len(message) > MAX_MESSAGE:
        return _response(400, False, "Please enter a message (up to 5000 characters).")

    if topic not in TOPICS:
        return _response(400, False, "Please choose a topic from the list.")
    if len(organization) > MAX_ORGANIZATION:
        return _response(400, False, "Please shorten the organization name.")

    topic_label = TOPICS[topic]
    details = f"Name: {name}\n"
    if organization:
        details += f"Organization: {organization}\n"
    details += f"Email: {email}\nTopic: {topic_label}\n"

    try:
        _client().send_email(
            Source=os.environ["SES_SENDER"],
            Destination={"ToAddresses": [os.environ["SES_RECIPIENT"]]},
            ReplyToAddresses=[email],
            Message={
                "Subject": {
                    "Data": f"[{topic_label}] Website inquiry from {name}",
                    "Charset": "UTF-8",
                },
                "Body": {
                    "Text": {
                        "Data": f"{details}\n{message}\n",
                        "Charset": "UTF-8",
                    }
                },
            },
        )
    except Exception:
        print("SES send failed")
        return _response(502, False, "Could not send your message. Please try again later.")

    return _response(200, True)
