import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import publish_release as pr  # noqa: E402
import verify_signatures as vs  # noqa: E402

ARTIFACT_MAP = json.loads((ROOT / "content" / "downloads" / "artifact_map.json").read_text())
TAG = "v1.0.1-b.7"

DEBUG_OUTPUT = """Signer #1 certificate DN: CN=Android Debug, OU=Android, O=Unknown, L=Unknown, ST=Unknown, C=US
Signer #1 certificate SHA-256 digest: fac61745dc0903786fb9ede62a962b399f7348f0bb6f899b8332667591033b9c
WARNING: META-INF/version-control-info.textproto not protected by signature.
"""
RELEASE_OUTPUT = "Signer #1 certificate DN: CN=KnG Consulting LLC, O=KnG, C=US\nSigner #1 certificate SHA-256 digest: abcd\n"


def make_assets(tmp: Path):
    names = [pr.expand(e["asset"], TAG) for e in ARTIFACT_MAP["files"]]
    names += [pr.expand(d["asset"], TAG) for d in ARTIFACT_MAP["documents"] if d["asset"] != "SHA256SUMS.txt"]
    import hashlib

    sums = []
    for n in names:
        data = f"content of {n}".encode()
        (tmp / n).write_bytes(data)
        sums.append(f"{hashlib.sha256(data).hexdigest()}  {n}")
    (tmp / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n")
    return {p.name: p for p in tmp.iterdir()}


class ApkDetectionTests(unittest.TestCase):
    def test_debug_key_is_unsigned(self):
        self.assertFalse(vs.apk_signed(DEBUG_OUTPUT))

    def test_other_certificate_is_signed(self):
        self.assertTrue(vs.apk_signed(RELEASE_OUTPUT))

    def test_failed_verification_and_unparsable_output(self):
        self.assertFalse(vs.apk_signed("DOES NOT VERIFY\nERROR: bad"))
        self.assertIsNone(vs.apk_signed("nothing useful"))

    def test_the_real_release_apk_is_reported_unsigned(self):
        apk = Path(__file__).resolve().parent / "fixtures" / "debug-signed-output.txt"
        self.assertFalse(vs.apk_signed(apk.read_text()))


class AuthenticodeTests(unittest.TestCase):
    def test_signature_presence(self):
        self.assertTrue(vs.check_authenticode("x.exe", runner=lambda cmd: (0, "ok")))
        self.assertFalse(vs.check_authenticode("x.exe", runner=lambda cmd: (1, "Failed: No signature found")))
        self.assertIsNone(vs.check_authenticode("x.exe", runner=lambda cmd: (2, "tool crashed")))


class VerifyAssetsTests(unittest.TestCase):
    def runner_for(self, apk_output, exe_result):
        def runner(cmd):
            return (0, apk_output) if "apksigner" in cmd[0] else exe_result
        return runner

    def test_results_cover_only_files_that_need_signatures(self):
        with tempfile.TemporaryDirectory() as d:
            assets = make_assets(Path(d))
            results = vs.verify_assets(TAG, assets, ARTIFACT_MAP, False, "apksigner", self.runner_for(DEBUG_OUTPUT, (1, "No signature found")))
        self.assertIn("TemplateEditor.apk", results)
        self.assertIn("TemplateEditor.exe", results)
        self.assertIn("TemplateEditor.dmg", results)
        self.assertNotIn("virtual-church-musician-template-desktop_1.0.1-b.7_amd64.deb", results)
        self.assertNotIn("ChurchMusicServer.exe", results, "paid apps are not published")
        self.assertTrue(all(v is False for v in results.values()))

    def test_signed_installers_and_attested_apple(self):
        with tempfile.TemporaryDirectory() as d:
            assets = make_assets(Path(d))
            results = vs.verify_assets(TAG, assets, ARTIFACT_MAP, True, "apksigner", self.runner_for(RELEASE_OUTPUT, (0, "ok")))
        self.assertTrue(all(results.values()))


class SignedFlagTests(unittest.TestCase):
    def plan(self, signatures):
        with tempfile.TemporaryDirectory() as d:
            return pr.plan_release(TAG, make_assets(Path(d)), ARTIFACT_MAP, "2026-09-11", signatures)["release"]

    def test_release_is_unsigned_without_verification(self):
        release = self.plan(None)
        self.assertFalse(release["signed"])
        self.assertIn("TemplateEditor.apk", release["unsigned_files"])
        deb = [f for f in release["files"] if f["format"] == "deb"][0]
        self.assertNotIn("signed", deb)

    def test_release_is_signed_only_when_every_required_file_is(self):
        with tempfile.TemporaryDirectory() as d:
            assets = make_assets(Path(d))
            names = {pr.expand(e["asset"], TAG) for e in ARTIFACT_MAP["files"] if e.get("public", True) and e.get("signing", "none") != "none"}
            everything = {n: True for n in names}
            release = pr.plan_release(TAG, assets, ARTIFACT_MAP, "2026-09-11", everything)["release"]
            self.assertTrue(release["signed"])
            self.assertEqual(release["unsigned_files"], [])
            one_bad = dict(everything, **{"Security.apk": False})
            release = pr.plan_release(TAG, assets, ARTIFACT_MAP, "2026-09-11", one_bad)["release"]
            self.assertFalse(release["signed"])
            self.assertEqual(release["unsigned_files"], ["Security.apk"])


class CheckLiveTests(unittest.TestCase):
    def matrix_file(self, tmp, releases):
        path = Path(tmp) / "matrix.json"
        path.write_text(json.dumps({"releases": releases}))
        return str(path)

    def test_no_matrix_or_no_releases_passes(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(pr.main(["check-live", "--matrix", str(Path(d) / "missing.json")]), 0)
            self.assertEqual(pr.main(["check-live", "--matrix", self.matrix_file(d, [])]), 0)

    def test_fully_signed_releases_pass(self):
        with tempfile.TemporaryDirectory() as d:
            releases = [{"version": "v1.1.0", "signed": True}, {"version": "v1.0.9", "signed": True}]
            self.assertEqual(pr.main(["check-live", "--matrix", self.matrix_file(d, releases)]), 0)

    def test_an_unsigned_previous_release_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            releases = [{"version": "v1.1.0", "signed": True}, {"version": "v1.0.1-b.6", "signed": False, "unsigned_files": ["Security.apk"]}]
            self.assertEqual(pr.main(["check-live", "--matrix", self.matrix_file(d, releases)]), 1)

    def test_a_release_without_a_signed_flag_counts_as_unsigned(self):
        self.assertEqual(pr.unsigned_releases({"releases": [{"version": "v1"}]}), [("v1", ["(signing status unknown)"])])


if __name__ == "__main__":
    unittest.main()
