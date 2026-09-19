#!/usr/bin/env python3
"""Plan the publication of one Virtual Church Musician GitHub release to the
downloads bucket. Pure planning, no AWS or network access: the
publish-downloads workflow downloads the release assets, runs `plan`, then
uploads what the plan lists and finally replaces matrix.json.

  python3 src/publish_release.py assets --tag v1.0.1-b.7
  python3 src/publish_release.py plan --tag v1.0.1-b.7 --assets DIR \
      --published 2026-09-11 --matrix current-matrix.json --out OUT

Writes OUT/matrix.json, OUT/uploads.tsv (local path, key, content type) and
OUT/delete-prefixes.txt (release prefixes that fell out of retention).
Exits non-zero on a checksum mismatch or when nothing publishable was found.
"""

import argparse
import hashlib
import json
import mimetypes
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MAP = REPO_ROOT / "content" / "downloads" / "artifact_map.json"
PRERELEASE_RE = re.compile(r"-[ab]\.\d+$")
KEEP_PER_CHANNEL = 2  # current and current - 1


class PublishError(Exception):
    pass


def version_parts(tag: str) -> dict:
    ver = tag[1:] if tag.startswith("v") else tag
    return {"tag": tag, "ver": ver, "base": PRERELEASE_RE.sub("", ver)}


def channel_for(tag: str) -> str:
    return "beta" if PRERELEASE_RE.search(tag) else "stable"


def expand(pattern: str, tag: str) -> str:
    return pattern.format(**version_parts(tag))


def parse_checksums(text: str) -> dict:
    sums = {}
    for line in text.splitlines():
        match = re.match(r"^([0-9a-fA-F]{64})\s+\*?(.+?)\s*$", line)
        if match:
            sums[Path(match.group(2)).name] = match.group(1).lower()
    return sums


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def content_type(name: str) -> str:
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


def plan_release(tag: str, assets: dict, artifact_map: dict, published: str) -> dict:
    """assets: filename -> Path of every downloaded release asset."""
    checksum_name = artifact_map.get("checksum_asset", "SHA256SUMS.txt")
    sums = parse_checksums(assets[checksum_name].read_text(encoding="utf-8")) if checksum_name in assets else {}
    prefix = f"releases/{tag}"
    files, documents, uploads, warnings = [], [], [], []

    for entry in artifact_map["files"]:
        if not entry.get("public", True):
            continue
        name = expand(entry["asset"], tag)
        path = assets.get(name)
        if path is None:
            warnings.append(f"missing asset: {name}")
            continue
        digest = sha256_of(path)
        if name not in sums:
            raise PublishError(f"{name} is not listed in {checksum_name}")
        if sums[name] != digest:
            raise PublishError(f"checksum mismatch for {name}")
        files.append(
            {
                "app": entry["app"], "platform": entry["platform"], "arch": entry["arch"],
                "format": entry["format"], "default": bool(entry.get("default")),
                "key": f"{prefix}/{name}", "filename": name, "sha256": digest, "size": path.stat().st_size,
            }
        )
        uploads.append((path, f"{prefix}/{name}", content_type(name)))

    for entry in artifact_map["documents"]:
        name = expand(entry["asset"], tag)
        path = assets.get(name)
        if path is None:
            warnings.append(f"missing document: {name}")
            continue
        if name in sums and sums[name] != sha256_of(path):
            raise PublishError(f"checksum mismatch for {name}")
        documents.append({"kind": entry["kind"], "format": entry["format"], "key": f"{prefix}/{name}", "filename": name})
        uploads.append((path, f"{prefix}/{name}", content_type(name)))

    if not files:
        raise PublishError("no publishable installers were found in the release assets")
    release = {"version": tag, "channel": channel_for(tag), "published": published, "files": files, "documents": documents}
    return {"release": release, "uploads": uploads, "warnings": warnings}


def merge_matrix(matrix: dict, release: dict, keep: int = KEEP_PER_CHANNEL):
    """Insert the release, drop older ones beyond `keep` per channel, newest first.
    Returns (new matrix, versions dropped)."""
    matrix = json.loads(json.dumps(matrix)) if matrix else {}
    matrix.setdefault("FormatVersion", 1)
    releases = [r for r in matrix.get("releases", []) if r["version"] != release["version"]] + [release]
    releases.sort(key=lambda r: (r.get("published", ""), r["version"]), reverse=True)
    kept, dropped, seen = [], [], {}
    for r in releases:
        channel = r.get("channel", "beta")
        seen[channel] = seen.get(channel, 0) + 1
        (kept if seen[channel] <= keep else dropped).append(r)
    matrix["releases"] = kept
    return matrix, [r["version"] for r in dropped]


def cmd_plan(args) -> int:
    artifact_map = json.loads(Path(args.map).read_text(encoding="utf-8"))
    assets = {p.name: p for p in Path(args.assets).iterdir() if p.is_file()}
    matrix_path = Path(args.matrix)
    matrix = json.loads(matrix_path.read_text(encoding="utf-8")) if matrix_path.exists() and matrix_path.stat().st_size else {}
    try:
        plan = plan_release(args.tag, assets, artifact_map, args.published)
    except PublishError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    new_matrix, dropped = merge_matrix(matrix, plan["release"])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "matrix.json").write_text(json.dumps(new_matrix, indent=2) + "\n", encoding="utf-8")
    (out / "uploads.tsv").write_text("".join(f"{p}\t{k}\t{t}\n" for p, k, t in plan["uploads"]), encoding="utf-8")
    (out / "delete-prefixes.txt").write_text("".join(f"releases/{v}/\n" for v in dropped), encoding="utf-8")
    for warning in plan["warnings"]:
        print(f"warning: {warning}", file=sys.stderr)
    print(
        f"{args.tag} ({plan['release']['channel']}): {len(plan['release']['files'])} installers, "
        f"{len(plan['release']['documents'])} documents; releases kept: "
        f"{[r['version'] for r in new_matrix['releases']]}; dropping: {dropped}"
    )
    return 0


def cmd_assets(args) -> int:
    """Print the release asset names the workflow needs to download."""
    artifact_map = json.loads(Path(args.map).read_text(encoding="utf-8"))
    names = [expand(e["asset"], args.tag) for e in artifact_map["files"] if e.get("public", True)]
    names += [expand(d["asset"], args.tag) for d in artifact_map["documents"] if d["asset"] != "release-notes.md"]
    for name in dict.fromkeys(names):
        print(name)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--tag", required=True)
    plan.add_argument("--assets", required=True)
    plan.add_argument("--published", required=True, help="YYYY-MM-DD")
    plan.add_argument("--matrix", required=True, help="current matrix.json (may not exist)")
    plan.add_argument("--map", default=str(DEFAULT_MAP))
    plan.add_argument("--out", required=True)
    plan.set_defaults(func=cmd_plan)
    assets = sub.add_parser("assets", help="list the release assets to download")
    assets.add_argument("--tag", required=True)
    assets.add_argument("--map", default=str(DEFAULT_MAP))
    assets.set_defaults(func=cmd_assets)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
