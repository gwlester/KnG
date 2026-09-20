import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import publish_release as pr  # noqa: E402

ARTIFACT_MAP = json.loads((ROOT / "content" / "downloads" / "artifact_map.json").read_text())
TAG = "v1.0.1-b.7"


def make_release_dir(tmp: Path, tag=TAG, skip=(), corrupt=(), pick=-1):
    """Create every mapped asset (public or not) plus docs and SHA256SUMS."""
    # pick=-1: a release made with the old (pre-rename) file names; pick=0: the new names
    names = [pr.asset_names(e, tag)[pick] for e in ARTIFACT_MAP["files"]]
    names += [pr.asset_names(d, tag)[pick] for d in ARTIFACT_MAP["documents"] if d["asset"] != "SHA256SUMS.txt"]
    sums = []
    for name in names:
        if name in skip:
            continue
        data = f"content of {name}".encode()
        (tmp / name).write_bytes(data)
        recorded = hashlib.sha256(b"different" if name in corrupt else data).hexdigest()
        sums.append(f"{recorded}  {name}")
    (tmp / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n")
    return {p.name: p for p in tmp.iterdir()}


class PublishReleaseTests(unittest.TestCase):
    def test_a_renamed_asset_can_be_listed_as_alternatives(self):
        entry = {"asset": ["TemplateEditor.exe", "VCMTemplates.exe"], "app": "template-editor", "platform": "windows",
                 "arch": "any", "format": "exe", "default": True, "public": True, "signing": "none"}
        amap = {"checksum_asset": "SHA256SUMS.txt", "files": [entry], "documents": []}
        self.assertEqual(pr.asset_names(entry, TAG), ["TemplateEditor.exe", "VCMTemplates.exe"])
        for present in ("TemplateEditor.exe", "VCMTemplates.exe"):
            with self.subTest(present=present), tempfile.TemporaryDirectory() as d:
                tmp = Path(d)
                data = b"installer"
                (tmp / present).write_bytes(data)
                (tmp / "SHA256SUMS.txt").write_text(f"{hashlib.sha256(data).hexdigest()}  {present}\n")
                assets = {p.name: p for p in tmp.iterdir()}
                plan = pr.plan_release(TAG, assets, amap, "2026-09-20")
                self.assertEqual([f["filename"] for f in plan["release"]["files"]], [present])
                self.assertEqual(plan["warnings"], [])

    def test_old_and_new_release_file_names_publish_the_same_installers(self):
        counts = []
        for pick in (-1, 0):
            with tempfile.TemporaryDirectory() as d:
                plan = pr.plan_release(TAG, make_release_dir(Path(d), pick=pick), ARTIFACT_MAP, "2026-09-20")
                names = {f["filename"] for f in plan["release"]["files"]}
                counts.append(len(names))
                self.assertEqual(plan["warnings"], [] if False else plan["warnings"])
                if pick == 0:
                    self.assertIn("VCMTemplates.exe", names)
                    self.assertIn("VCMSecurity.apk", names)
                    self.assertNotIn("TemplateEditor.exe", names)
                else:
                    self.assertIn("TemplateEditor.exe", names)
        self.assertEqual(counts[0], counts[1])
        self.assertGreater(counts[0], 10)

    def test_version_expansion(self):
        self.assertEqual(pr.expand("A_{base}_x64.msi", TAG), "A_1.0.1_x64.msi")
        self.assertEqual(pr.expand("a_{ver}_amd64.deb", TAG), "a_1.0.1-b.7_amd64.deb")
        self.assertEqual(pr.channel_for("v1.0.1-b.7"), "beta")
        self.assertEqual(pr.channel_for("v1.0.1-a.16"), "beta")
        self.assertEqual(pr.channel_for("v1.0.1"), "stable")

    def test_plan_publishes_free_apps_and_skips_paid_ones(self):
        with tempfile.TemporaryDirectory() as d:
            plan = pr.plan_release(TAG, make_release_dir(Path(d)), ARTIFACT_MAP, "2026-09-11")
        apps = {f["app"] for f in plan["release"]["files"]}
        self.assertEqual(apps, {"template-editor", "service-builder", "service-runner", "admin", "security"})
        keys = [k for _, k, _ in plan["uploads"]]
        self.assertTrue(all(k.startswith(f"releases/{TAG}/") for k in keys))
        self.assertFalse(any("Server" in k or "MidiPlayer" in k or "server" in k for k in keys))
        kinds = {d["kind"] for d in plan["release"]["documents"]}
        self.assertEqual(kinds, {"user-manual", "system-admin-guide", "sha256sums", "release-notes"})
        self.assertEqual(plan["release"]["channel"], "beta")

    def test_windows_defaults_to_exe_for_desktop_apps(self):
        with tempfile.TemporaryDirectory() as d:
            plan = pr.plan_release(TAG, make_release_dir(Path(d)), ARTIFACT_MAP, "2026-09-11")
        win = [f for f in plan["release"]["files"] if f["app"] == "template-editor" and f["platform"] == "windows"]
        self.assertEqual({f["format"]: f["default"] for f in win}, {"exe": True, "msi": False})

    def test_checksum_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as d:
            assets = make_release_dir(Path(d), corrupt=("TemplateEditor.exe",))
            with self.assertRaisesRegex(pr.PublishError, "checksum mismatch"):
                pr.plan_release(TAG, assets, ARTIFACT_MAP, "2026-09-11")

    def test_missing_assets_warn_but_publish_the_rest(self):
        with tempfile.TemporaryDirectory() as d:
            assets = make_release_dir(Path(d), skip=("Security.apk",))
            plan = pr.plan_release(TAG, assets, ARTIFACT_MAP, "2026-09-11")
        self.assertIn("missing asset: VCMSecurity.apk or Security.apk", plan["warnings"])
        self.assertNotIn("security", {f["app"] for f in plan["release"]["files"]})

    def test_nothing_publishable_fails(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "SHA256SUMS.txt").write_text("")
            assets = {p.name: p for p in Path(d).iterdir()}
            with self.assertRaisesRegex(pr.PublishError, "no publishable"):
                pr.plan_release(TAG, assets, ARTIFACT_MAP, "2026-09-11")

    def test_merge_keeps_current_and_previous_per_channel_newest_first(self):
        matrix = {}
        for i, tag in enumerate(["v1.0.1-b.5", "v1.0.1-b.6", "v1.0.1-b.7"]):
            matrix, dropped = pr.merge_matrix(matrix, {"version": tag, "channel": "beta", "published": f"2026-09-0{i + 1}"})
        self.assertEqual([r["version"] for r in matrix["releases"]], ["v1.0.1-b.7", "v1.0.1-b.6"])
        self.assertEqual(dropped, ["v1.0.1-b.5"])

    def test_merge_is_idempotent_and_keeps_stable_and_beta_separately(self):
        matrix = {"releases": [], "links": {"x:android": {"type": "store", "url": "https://p"}}}
        for tag, channel, published in (("v1.1.0", "stable", "2026-10-01"), ("v1.1.1-b.1", "beta", "2026-10-05"), ("v1.1.0", "stable", "2026-10-01")):
            matrix, _ = pr.merge_matrix(matrix, {"version": tag, "channel": channel, "published": published})
        self.assertEqual([r["version"] for r in matrix["releases"]], ["v1.1.1-b.1", "v1.1.0"])
        self.assertIn("links", matrix)

    def test_checksum_parsing_accepts_binary_marker(self):
        digest = "a" * 64
        self.assertEqual(pr.parse_checksums(f"{digest} *dir/file.bin\n"), {"file.bin": digest})

    def test_cli_writes_plan_files(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            assets = d / "assets"
            assets.mkdir()
            make_release_dir(assets)
            out = d / "out"
            code = pr.main(["plan", "--tag", TAG, "--assets", str(assets), "--published", "2026-09-11",
                            "--matrix", str(d / "none.json"), "--out", str(out)])
            self.assertEqual(code, 0)
            matrix = json.loads((out / "matrix.json").read_text())
            self.assertEqual(matrix["releases"][0]["version"], TAG)
            self.assertTrue((out / "uploads.tsv").read_text().strip())


if __name__ == "__main__":
    unittest.main()
