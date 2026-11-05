"""Download Lambda: resolves a request against the private matrix and redirects.

GET  ?app=&platform=&version=&format=&arch=&v=1                   -> 302 to a 5-minute signed URL
POST ?app=&platform=&version=&format=&arch=&v=1                   -> 200 {"ok": true, "url": ...} (only for older cached
                                                                       copies of the page, which POST; the body is ignored)
GET  ?doc=&format=&version=&v=1                                   -> 302 to a signed URL for a guide
GET  ?status=1&app=&channel=&v=1                                  -> JSON of availability (no file keys); app (optional,
                                                                       comma-separated) limits current/previous to those apps; channel
                                                                       stable (default) | beta | any also offers
                                                                       betas / alphas, and the same `channel` on a
                                                                       download or doc call resolves "current" alike
GET  ?update=1&app=&platform=&channel=&current=&v=1               -> JSON {update_available, latest} for the app's newest
                                                                       release on that channel (see _update)

The matrix (matrix.json in the private downloads bucket) is written by the
publish-downloads workflow and never leaves the server: callers only ever get
a redirect, a presigned-URL JSON body, or the status summary. Only keys found
in the matrix are signed.

Downloads need no access code: the free apps are free and the paid apps (server,
midi-player) are protected by their license files, which the apps check when
they run (decided 2026-11-04; this replaces the 2026-10-12 order-gated download).
"""

import json
import os
import re
import time

FORMAT_VERSION = 1
PRESIGN_SECONDS = int(os.environ.get("PRESIGN_SECONDS", "300"))
MATRIX_KEY = os.environ.get("MATRIX_KEY", "matrix.json")
CACHE_SECONDS = 60
UPDATE_CHANNELS = {
    # Which kinds of release each update channel may be offered.
    "stable": {"stable"},
    "beta": {"stable", "beta"},
    "any": {"stable", "beta", "alpha"},
}
TAG_RE = re.compile(r"^(?:[a-z][a-z-]*-)?v?(\d{1,5})\.(\d{1,5})\.(\d{1,5})(?:-([ab])\.(\d{1,5}))?$")
KIND_RANK = {"a": 0, "b": 1, None: 2}
KIND_NAME = {"a": "alpha", "b": "beta", None: "stable"}

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
FORMAT_RE = re.compile(r"^[a-z0-9]{1,10}$")
VERSION_RE = re.compile(r"^(current|previous|([a-z][a-z-]{0,20}-)?v[0-9A-Za-z.\-]{1,40})$")

INLINE_TYPES = {"html": "text/html", "txt": "text/plain", "md": "text/plain"}
ATTACHMENT_TYPES = {"pdf": "application/pdf"}

_s3_client = None
_cache = {"at": 0.0, "matrix": None}


def _s3():
    global _s3_client
    if _s3_client is None:
        import boto3  # bundled in the Lambda runtime; imported lazily so tests need no boto3
        from botocore.config import Config

        # Signature Version 4: the default for presigned URLs here was the legacy SigV2.
        _s3_client = boto3.client("s3", config=Config(signature_version="s3v4"))
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


def _channel(qs: dict):
    """The release channel the page selector asks for (stable | beta | any; default stable), or None if unknown."""
    channel = qs.get("channel", "stable")
    return channel if channel in UPDATE_CHANNELS else None


def visible_releases(matrix: dict, app: str = None, channel: str = "stable") -> list:
    """Stable releases once any exist; until then every release (labelled
    Beta). With a `channel` of beta or any, the newest releases (by tag) of the kinds that
    channel allows come first, so a tester can reach betas and alphas. A "deprecated" release (no longer offered for download -- see
    publish_release.py's deprecate_matrix) is excluded either way, before
    the stable/beta fallback is even considered. With `app`, only releases
    that contain that app's files are considered, so each app has its own
    "current" and "previous" (apps are released independently)."""
    releases = [r for r in matrix.get("releases", []) if r.get("channel") != "deprecated"]
    if app:
        releases = [r for r in releases if any(f.get("app") == app for f in r.get("files", []))]
    if channel != "stable":
        allowed = UPDATE_CHANNELS[channel]
        wanted = [r for r in releases if (parse_tag(r.get("version", "")) or (None, None))[1] in allowed]
        wanted.sort(key=lambda r: parse_tag(r["version"])[0], reverse=True)
        if wanted:
            return wanted
    stable = [r for r in releases if r.get("channel") == "stable"]
    return stable or releases


def resolve_release(matrix: dict, version: str, app: str = None, channel: str = "stable"):
    visible = visible_releases(matrix, app, channel)
    if version == "current":
        return visible[0] if visible else None
    if version == "previous":
        return visible[1] if len(visible) > 1 else None
    # An exact version tag is searched for across every release, not just
    # the stable-filtered "visible" ones -- an approved beta tester must
    # still be able to reach a specific beta release by its own tag even
    # once some other release has gone stable and taken over
    # "current"/"previous" (decided 2026-10-12). picker.js doesn't yet
    # have a UI path that requests an explicit non-current/previous
    # version -- this makes the backend capable of it; wiring an actual
    # "beta" selector into the picker is a follow-up, not done here.
    # A deprecated release is deliberately not reachable even here
    # (decided 2026-10-14): unlike the stable-filter above, this isn't a
    # UI-convenience exemption, it's "this build doesn't work with the
    # licensing system" -- the same exclusion applies to every path.
    for release in matrix.get("releases", []):
        if release.get("channel") == "deprecated":
            continue
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


def _per_app(matrix: dict, which: str, channel: str = "stable", only: set = None) -> list:
    """Each app's own current/previous release, de-duplicated (releases that cover every app resolve to one).
    `only` limits it to those apps."""
    apps = {f["app"] for r in matrix.get("releases", []) for f in r.get("files", [])}
    if only is not None:
        apps &= only
    found = {}
    for app in sorted(apps):
        release = resolve_release(matrix, which, app, channel)
        if release is not None:
            found[release["version"]] = release
    return list(found.values())


def _status(matrix: dict, channel: str = "stable", only: set = None) -> dict:
    def summarize(releases):
        releases = [r for r in releases if r is not None]
        if not releases:
            return None
        releases.sort(key=lambda r: (r.get("published", ""), parse_tag(r.get("version", "")) or ()), reverse=True)
        release = releases[0]
        files = {}
        for f in (f for r in releases for f in r.get("files", [])):
            # A paid app's file is always reported available, on every
            # channel: it's always order-gated now (purchase or, on a
            # non-stable channel, an approved beta tester's Test Drive
            # credential), never hidden outright the way "sold elsewhere,
            # not here" used to hide a stable release's file.
            files.setdefault(f'{f["app"]}:{f["platform"]}', set()).add(f["format"])
        for link_key, link in matrix.get("links", {}).items():
            files.setdefault(link_key, set()).add(link["type"])
        docs = {}
        for d in (d for r in releases for d in r.get("documents", [])):
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
            "current": summarize(_per_app(matrix, "current", channel, only)),
            "previous": summarize(_per_app(matrix, "previous", channel, only)),
        },
        cache=f"public, max-age={CACHE_SECONDS}",
    )


def parse_tag(tag: str):
    """(sort key, kind) for a release tag like v1.0.2-a.1, v1.0.2-b.3 or v1.0.2, or None if it isn't one.
    Within a base version, alpha < beta < stable; attempt numbers compare as numbers."""
    match = TAG_RE.match(tag or "")
    if not match:
        return None
    major, minor, patch, kind, attempt = match.groups()
    return (int(major), int(minor), int(patch), KIND_RANK[kind], int(attempt or 0)), KIND_NAME[kind]


def _update(matrix: dict, qs: dict) -> dict:
    """The update check the apps call. Finds the newest release that contains `app` on `platform`, limited
    to the kinds of release the `channel` allows (stable | beta | any; default stable), and says whether it is
    newer than `current`. Answers with the release's version only: the caller then asks for the file with the
    ordinary ?app=&platform=&version=<exact tag> download. Per-app release versions will not change this: it
    already means "newest release containing this app"."""
    app, platform = qs.get("app", ""), qs.get("platform", "")
    channel = qs.get("channel", "stable")
    if not NAME_RE.match(app) or not NAME_RE.match(platform):
        return _error(400, "Unknown app or platform.")
    if channel not in UPDATE_CHANNELS:
        return _error(400, "Unknown channel.")
    current = parse_tag(qs.get("current", ""))
    if current is None:
        return _error(400, "Invalid current version.")
    allowed = UPDATE_CHANNELS[channel]
    best = None
    for release in matrix.get("releases", []):
        if release.get("channel") == "deprecated":
            continue
        parsed = parse_tag(release.get("version", ""))
        if parsed is None or parsed[1] not in allowed:
            continue
        if not any(f["app"] == app and f["platform"] == platform for f in release.get("files", [])):
            continue
        if best is None or parsed[0] > best[0]:
            best = (parsed[0], parsed[1], release)
    latest = None
    if best:
        release = best[2]
        latest = {"version": release["version"], "kind": best[1], "published": release.get("published", "")}
    return _json(
        200,
        {
            "ok": True,
            "FormatVersion": FORMAT_VERSION,
            "update_available": bool(best and best[0] > current[0]),
            "latest": latest,
            "requires_access_code": False,  # kept (always false) so existing clients still parse the reply
        },
        cache=f"public, max-age={CACHE_SECONDS}",
    )


def _download(matrix: dict, qs: dict, post: bool = False) -> dict:
    app, platform = qs.get("app", ""), qs.get("platform", "")
    fmt, arch = qs.get("format", ""), qs.get("arch", "")
    version = qs.get("version", "current")
    if not NAME_RE.match(app) or not NAME_RE.match(platform):
        return _error(400, "Unknown app or platform.")
    if fmt and not FORMAT_RE.match(fmt) or arch and not FORMAT_RE.match(arch):
        return _error(400, "Invalid format or architecture.")
    if not VERSION_RE.match(version):
        return _error(400, "Invalid version.")

    link = matrix.get("links", {}).get(f"{app}:{platform}")
    if link and link.get("url", "").startswith("https://") and not fmt:
        _log(app=app, platform=platform, version="link", type=link.get("type"))
        return _redirect(link["url"])

    channel = _channel(qs)
    if channel is None:
        return _error(400, "Unknown channel.")
    release = resolve_release(matrix, version, app, channel)
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
    # A POST comes from an older cached copy of the page, which expects the address in JSON.
    if post:
        return _json(200, {"ok": True, "url": url, "filename": chosen["filename"]})
    return _redirect(url)


def _document(matrix: dict, qs: dict) -> dict:
    kind, fmt = qs.get("doc", ""), qs.get("format", "")
    version = qs.get("version", "current")
    if not NAME_RE.match(kind) or (fmt and not FORMAT_RE.match(fmt)):
        return _error(400, "Unknown document.")
    if not VERSION_RE.match(version):
        return _error(400, "Invalid version.")
    channel = _channel(qs)
    if channel is None:
        return _error(400, "Unknown channel.")
    release = resolve_release(matrix, version, None, channel)
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
    # POST is accepted only for older cached copies of the download page; the body is ignored.
    if method not in ("GET", "HEAD", "POST"):
        return _error(405, "Method not allowed.")
    qs = event.get("queryStringParameters") or {}
    if qs.get("v", "1") != "1":
        return _error(400, "Unsupported API version.")
    matrix = _load_matrix()
    if qs.get("status"):
        channel = _channel(qs)
        if channel is None:
            return _error(400, "Unknown channel.")
        only = None
        if qs.get("app"):
            only = set(qs["app"].split(","))
            if not all(NAME_RE.match(a) for a in only):
                return _error(400, "Unknown app.")
        return _status(matrix, channel, only)
    if qs.get("update"):
        return _update(matrix, qs)
    if qs.get("doc"):
        return _document(matrix, qs)
    if qs.get("app"):
        return _download(matrix, qs, post=method == "POST")
    return _error(400, "Nothing requested.")
