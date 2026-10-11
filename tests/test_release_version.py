import importlib.util
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("check_release_version", ROOT / "scripts" / "check_release_version.py")
crv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(crv)


class ReleaseVersionTests(unittest.TestCase):
    def test_current_package_matches_its_tag(self):
        import hprc
        self.assertEqual(crv.check(f"v{hprc.__version__}", ROOT), hprc.__version__)

    def test_pep440_prereleases_and_finals_accepted(self):
        for tag, version in [("v0.5.0", "0.5.0"), ("v0.5.0b1", "0.5.0b1"), ("v1.2.3a4", "1.2.3a4"), ("v0.5.0rc2", "0.5.0rc2")]:
            self.assertEqual(crv.tag_version(tag), version)

    def test_malformed_tags_rejected(self):
        for tag in ["0.5.0b1", "v0.5", "v0.5.0-beta1", "v0.5.0.b1", "v0.5.0b", "v0.5.0.dev1", "v0.5.0+local", "v0.5.0b1 "]:
            with self.assertRaises(ValueError, msg=tag):
                crv.tag_version(tag)

    def test_mismatch_names_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "hprc").mkdir()
            (root / "pyproject.toml").write_text('[project]\nversion = "0.5.0b1"\n', encoding="utf-8")
            (root / "hprc" / "__init__.py").write_text('__version__ = "0.5.0b1"\n', encoding="utf-8")
            (root / "CITATION.cff").write_text("version: 0.5.0\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "CITATION.cff version 0.5.0"):
                crv.check("v0.5.0b1", root)

    def test_release_workflow_uses_checker(self):
        text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn('python scripts/check_release_version.py "$RELEASE_TAG"', text)
        self.assertNotIn(r"v([0-9]+\.[0-9]+\.[0-9]+)\"", text)


if __name__ == "__main__":
    unittest.main()
