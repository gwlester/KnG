#!/usr/bin/env python3
"""Detect whether downloaded release installers are signed, for the
publish-downloads workflow. Writes {filename: true|false} for every public
installer that must be signed (see "signing" in content/downloads/artifact_map.json).

  apk           signed with a non-debug certificate (apksigner)
  authenticode  a Windows signature is present (osslsigncode); presence only
  apple         cannot be checked on Linux, so it is attested by the caller
  none          not required (Linux packages)

  python3 src/verify_signatures.py --tag v1.0.1-b.7 --assets DIR \
      --apksigner PATH --attest-apple false --out signatures.json
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish_release as pr  # noqa: E402

DEBUG_DN = re.compile(r"CN=Android Debug", re.IGNORECASE)


def run(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def apk_signed(output: str):
    """True: a non-debug certificate. False: debug or failed verification. None: unknown."""
    if "DOES NOT VERIFY" in output:
        return False
    dns = re.findall(r"certificate DN:\s*(.+)", output)
    if not dns:
        return None
    return not any(DEBUG_DN.search(dn) for dn in dns)


def check_apk(path, apksigner, runner=run):
    _, output = runner([apksigner, "verify", "--print-certs", str(path)])
    return apk_signed(output)


def check_authenticode(path, runner=run):
    with tempfile.TemporaryDirectory() as tmp:
        code, output = runner(["osslsigncode", "extract-signature", "-in", str(path), "-out", str(Path(tmp) / "sig.der")])
    if code == 0:
        return True
    if "no signature" in output.lower() or "not signed" in output.lower():
        return False
    return None


def verify_assets(tag, assets, artifact_map, attest_apple, apksigner, runner=run):
    """assets: filename -> Path. Returns {filename: bool} for files that need a signature."""
    results = {}
    for entry in artifact_map["files"]:
        if not entry.get("public", True):
            continue
        kind = entry.get("signing", "none")
        if kind == "none":
            continue
        name = pr.expand(entry["asset"], tag)
        path = assets.get(name)
        if path is None:
            continue
        if kind == "apk":
            outcome = check_apk(path, apksigner, runner)
        elif kind == "authenticode":
            outcome = check_authenticode(path, runner)
        elif kind == "apple":
            outcome = bool(attest_apple)
        else:
            outcome = None
        results[name] = outcome is True
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--assets", required=True)
    parser.add_argument("--map", default=str(pr.DEFAULT_MAP))
    parser.add_argument("--apksigner", default="apksigner")
    parser.add_argument("--attest-apple", default="false", choices=["true", "false"])
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    artifact_map = json.loads(Path(args.map).read_text(encoding="utf-8"))
    assets = {p.name: p for p in Path(args.assets).iterdir() if p.is_file()}
    results = verify_assets(args.tag, assets, artifact_map, args.attest_apple == "true", args.apksigner)
    Path(args.out).write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    for name, ok in sorted(results.items()):
        print(f"{'signed  ' if ok else 'UNSIGNED'} {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
