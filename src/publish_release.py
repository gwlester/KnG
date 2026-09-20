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


def asset_names(entry: dict, tag: str) -> list:
    """`asset` is one file name or a list of alternatives (a renamed product ships under a new file name; releases
    from before the rename keep the old one). All names are expanded with the tag."""
    raw = entry["asset"]
    return [expand(n, tag) for n in (raw if isinstance(raw, list) else [raw])]


def find_asset(entry: dict, tag: str, assets: dict):
    """(name, path) of the first alternative present in the release, else (first name, None)."""
    names = asset_names(entry, tag)
    for name in names:
        if name in assets:
            return name, assets[name]
    return names[0], None


def plan_release(tag: str, assets: dict, artifact_map: dict, published: str, signatures: dict = None) -> dict:
    """assets: filename -> Path of every downloaded release asset.
    signatures: filename -> bool from verify_signatures.py; None means nothing was verified."""
    checksum_name = artifact_map.get("checksum_asset", "SHA256SUMS.txt")
    sums = parse_checksums(assets[checksum_name].read_text(encoding="utf-8")) if checksum_name in assets else {}
    prefix = f"releases/{tag}"
    files, documents, uploads, warnings = [], [], [], []

    for entry in artifact_map["files"]:
        if not entry.get("public", True):
            continue
        name, path = find_asset(entry, tag, assets)
        if path is None:
            warnings.append("missing asset: " + " or ".join(asset_names(entry, tag)))
            continue
        digest = sha256_of(path)
        if name not in sums:
            raise PublishError(f"{name} is not listed in {checksum_name}")
        if sums[name] != digest:
            raise PublishError(f"checksum mismatch for {name}")
        signing = entry.get("signing", "none")
        record = {
            "app": entry["app"], "platform": entry["platform"], "arch": entry["arch"],
            "format": entry["format"], "default": bool(entry.get("default")),
            "key": f"{prefix}/{name}", "filename": name, "sha256": digest, "size": path.stat().st_size,
            "signing": signing,
        }
        if signing != "none":
            record["signed"] = bool(signatures and signatures.get(name) is True)
        files.append(record)
        uploads.append((path, f"{prefix}/{name}", content_type(name)))

    for entry in artifact_map["documents"]:
        name, path = find_asset(entry, tag, assets)
        if path is None:
            warnings.append("missing document: " + " or ".join(asset_names(entry, tag)))
            continue
        if name in sums and sums[name] != sha256_of(path):
            raise PublishError(f"checksum mismatch for {name}")
        documents.append({"kind": entry["kind"], "format": entry["format"], "key": f"{prefix}/{name}", "filename": name})
        uploads.append((path, f"{prefix}/{name}", content_type(name)))

    if not files:
        raise PublishError("no publishable installers were found in the release assets")
    unsigned = [f["filename"] for f in files if f.get("signed") is False]
    release = {
        "version": tag, "channel": channel_for(tag), "published": published,
        "signed": not unsigned, "unsigned_files": unsigned,
        "files": files, "documents": documents,
    }
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


def unsigned_releases(matrix: dict) -> list:
    """(version, unsigned file names) for every listed release that is not fully signed.
    A release without a `signed` flag (published before signing was tracked) counts as unsigned."""
    found = []
    for release in matrix.get("releases", []):
        if release.get("signed") is True:
            continue
        names = release.get("unsigned_files") or ["(signing status unknown)"]
        found.append((release["version"], names))
    return found


def cmd_check_live(args) -> int:
    path = Path(args.matrix)
    matrix = json.loads(path.read_text(encoding="utf-8")) if path.exists() and path.stat().st_size else {}
    bad = unsigned_releases(matrix)
    if not bad:
        print("ok: every release listed in the downloads matrix is signed (or none are listed)")
        return 0
    print("error: unsigned releases are still listed in the downloads matrix:", file=sys.stderr)
    for version, names in bad:
        print(f"  {version}: {', '.join(names[:6])}{' ...' if len(names) > 6 else ''}", file=sys.stderr)
    print("Publish a signed release until these age out, or delete their releases/<tag>/ folders and matrix entries.", file=sys.stderr)
    return 1


def cmd_plan(args) -> int:
    artifact_map = json.loads(Path(args.map).read_text(encoding="utf-8"))
    assets = {p.name: p for p in Path(args.assets).iterdir() if p.is_file()}
    matrix_path = Path(args.matrix)
    matrix = json.loads(matrix_path.read_text(encoding="utf-8")) if matrix_path.exists() and matrix_path.stat().st_size else {}
    signatures = None
    if args.signatures and Path(args.signatures).exists():
        signatures = json.loads(Path(args.signatures).read_text(encoding="utf-8"))
    try:
        plan = plan_release(args.tag, assets, artifact_map, args.published, signatures)
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
        f"{len(plan['release']['documents'])} documents; signed: {plan['release']['signed']}; releases kept: "
        f"{[r['version'] for r in new_matrix['releases']]}; dropping: {dropped}"
    )
    return 0


def cmd_assets(args) -> int:
    """Print the release asset names the workflow needs to download."""
    artifact_map = json.loads(Path(args.map).read_text(encoding="utf-8"))
    names = [n for e in artifact_map["files"] if e.get("public", True) for n in asset_names(e, args.tag)]
    names += [n for d in artifact_map["documents"] if d["asset"] != "release-notes.md" for n in asset_names(d, args.tag)]
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
    plan.add_argument("--signatures", help="signatures.json from verify_signatures.py")
    plan.set_defaults(func=cmd_plan)
    check = sub.add_parser("check-live", help="fail if any listed release is unsigned")
    check.add_argument("--matrix", required=True)
    check.set_defaults(func=cmd_check_live)
    assets = sub.add_parser("assets", help="list the release assets to download")
    assets.add_argument("--tag", required=True)
    assets.add_argument("--map", default=str(DEFAULT_MAP))
    assets.set_defaults(func=cmd_assets)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
