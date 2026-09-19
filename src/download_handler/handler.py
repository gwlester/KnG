"""Download Lambda: resolves a request against the private matrix and redirects.

GET ?app=&platform=&version=&format=&arch=&v=1   -> 302 to a 5-minute signed URL
GET ?doc=&format=&version=&v=1                   -> 302 to a signed URL for a guide
GET ?status=1&v=1                                -> JSON of what is available (no file locations)

The matrix (matrix.json in the private downloads bucket) is written by the
publish-downloads workflow and never leaves the server: callers only ever get
a redirect or the status summary. Only keys found in the matrix are signed.
"""

import json
import os
import re
import time

FORMAT_VERSION = 1
PRESIGN_SECONDS = int(os.environ.get("PRESIGN_SECONDS", "300"))
MATRIX_KEY = os.environ.get("MATRIX_KEY", "matrix.json")
CACHE_SECONDS = 60
# Paid products are delivered through the sales platform, never from this bucket.
BLOCKED_APPS = {a for a in os.environ.get("BLOCKED_APPS", "server,midi-player").split(",") if a}

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
FORMAT_RE = re.compile(r"^[a-z0-9]{1,10}$")
VERSION_RE = re.compile(r"^(current|previous|v[0-9A-Za-z.\-]{1,40})$")

INLINE_TYPES = {"html": "text/html", "txt": "text/plain", "md": "text/plain"}
ATTACHMENT_TYPES = {"pdf": "application/pdf"}

_s3_client = None
_cache = {"at": 0.0, "matrix": None}


def _s3():
    global _s3_client
    if _s3_client is None:
        import boto3  # bundled in the Lambda runtime; imported lazily so tests need no boto3

        _s3_client = boto3.client("s3")
    return _s3_client


def _bucket() -> str:
    return os.environ["DOWNLOADS_BUCKET"]


def _load_matrix() -> dict:
    now = time.time()
    if _cache["matrix"] is not None and now - _cache["at"] < CACHE_SECONDS:
        return _cache["matrix"]
    try:
        body = _s3().get_object(Bucket=_bucket(), Key=MATRIX_KEY)["Body"].read()
        matrix = json.loads(body)
    except Exception:
        matrix = {"FormatVersion": FORMAT_VERSION, "releases": []}
    _cache["at"], _cache["matrix"] = now, matrix
    return matrix


def _json(status: int, payload: dict, cache: str = "no-store") -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Cache-Control": cache},
        "body": json.dumps(payload),
    }


def _error(status: int, message: str) -> dict:
    return _json(status, {"ok": False, "error": message})


def _redirect(url: str) -> dict:
    return {"statusCode": 302, "headers": {"Location": url, "Cache-Control": "no-store"}, "body": ""}


def visible_releases(matrix: dict) -> list:
    """Stable releases once any exist; until then every release (labelled Beta)."""
    releases = matrix.get("releases", [])
    stable = [r for r in releases if r.get("channel") == "stable"]
    return stable or releases


def resolve_release(matrix: dict, version: str):
    visible = visible_releases(matrix)
    if version == "current":
        return visible[0] if visible else None
    if version == "previous":
        return visible[1] if len(visible) > 1 else None
    for release in visible:
        if release.get("version") == version:
            return release
    return None


def _presign(key: str, filename: str, fmt: str) -> str:
    if not key.startswith("releases/"):
        raise ValueError("unexpected key")
    params = {"Bucket": _bucket(), "Key": key}
    if fmt in INLINE_TYPES:
        params["ResponseContentType"] = INLINE_TYPES[fmt]
        params["ResponseContentDisposition"] = f'inline; filename="{filename}"'
    else:
        if fmt in ATTACHMENT_TYPES:
            params["ResponseContentType"] = ATTACHMENT_TYPES[fmt]
        params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
    return _s3().generate_presigned_url("get_object", Params=params, ExpiresIn=PRESIGN_SECONDS)


def _log(**fields) -> None:
    print(json.dumps({"event": "download", **fields}))


def _status(matrix: dict) -> dict:
    def summarize(release):
        if release is None:
            return None
        files = {}
        for f in release.get("files", []):
            if f["app"] in BLOCKED_APPS:
                continue
            files.setdefault(f'{f["app"]}:{f["platform"]}', set()).add(f["format"])
        for link_key, link in matrix.get("links", {}).items():
            files.setdefault(link_key, set()).add(link["type"])
        docs = {}
        for d in release.get("documents", []):
            docs.setdefault(d["kind"], set()).add(d["format"])
        return {
            "version": release["version"],
            "channel": release.get("channel", "beta"),
            "published": release.get("published", ""),
            "signed": release.get("signed"),
            "available": {k: sorted(v) for k, v in files.items()},
            "documents": {k: sorted(v) for k, v in docs.items()},
        }

    return _json(
        200,
        {
            "FormatVersion": FORMAT_VERSION,
            "current": summarize(resolve_release(matrix, "current")),
            "previous": summarize(resolve_release(matrix, "previous")),
        },
        cache=f"public, max-age={CACHE_SECONDS}",
    )


def _download(matrix: dict, qs: dict) -> dict:
    app, platform = qs.get("app", ""), qs.get("platform", "")
    fmt, arch = qs.get("format", ""), qs.get("arch", "")
    version = qs.get("version", "current")
    if not NAME_RE.match(app) or not NAME_RE.match(platform):
        return _error(400, "Unknown app or platform.")
    if app in BLOCKED_APPS:
        return _error(404, "That download is not available yet.")
    if fmt and not FORMAT_RE.match(fmt) or arch and not FORMAT_RE.match(arch):
        return _error(400, "Invalid format or architecture.")
    if not VERSION_RE.match(version):
        return _error(400, "Invalid version.")

    link = matrix.get("links", {}).get(f"{app}:{platform}")
    if link and link.get("url", "").startswith("https://") and not fmt:
        _log(app=app, platform=platform, version="link", type=link.get("type"))
        return _redirect(link["url"])

    release = resolve_release(matrix, version)
    if release is None:
        return _error(404, "That version is not available.")
    candidates = [f for f in release.get("files", []) if f["app"] == app and f["platform"] == platform]
    if arch:
        candidates = [f for f in candidates if f.get("arch") == arch]
    if fmt:
        candidates = [f for f in candidates if f["format"] == fmt]
    if not candidates:
        return _error(404, "That download is not available yet.")
    chosen = next((f for f in candidates if f.get("default")), candidates[0])
    try:
        url = _presign(chosen["key"], chosen["filename"], chosen["format"])
    except ValueError:
        return _error(404, "That download is not available yet.")
    _log(app=app, platform=platform, version=release["version"], format=chosen["format"])
    return _redirect(url)


def _document(matrix: dict, qs: dict) -> dict:
    kind, fmt = qs.get("doc", ""), qs.get("format", "")
    version = qs.get("version", "current")
    if not NAME_RE.match(kind) or (fmt and not FORMAT_RE.match(fmt)):
        return _error(400, "Unknown document.")
    if not VERSION_RE.match(version):
        return _error(400, "Invalid version.")
    release = resolve_release(matrix, version)
    if release is None:
        return _error(404, "That version is not available.")
    candidates = [d for d in release.get("documents", []) if d["kind"] == kind]
    if fmt:
        candidates = [d for d in candidates if d["format"] == fmt]
    if not candidates:
        return _error(404, "That document is not available yet.")
    chosen = candidates[0]
    try:
        url = _presign(chosen["key"], chosen["filename"], chosen["format"])
    except ValueError:
        return _error(404, "That document is not available yet.")
    _log(doc=kind, version=release["version"], format=chosen["format"])
    return _redirect(url)


def handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    if method not in ("GET", "HEAD"):
        return _error(405, "Method not allowed.")
    qs = event.get("queryStringParameters") or {}
    if qs.get("v", "1") != "1":
        return _error(400, "Unsupported API version.")
    matrix = _load_matrix()
    if qs.get("status"):
        return _status(matrix)
    if qs.get("doc"):
        return _document(matrix, qs)
    if qs.get("app"):
        return _download(matrix, qs)
    return _error(400, "Nothing requested.")
