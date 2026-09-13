import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hprc import cli


class InstallSkillTests(unittest.TestCase):
    def test_source_and_resource_are_identical(self):
        self.assertEqual(cli.SKILL_SRC.read_bytes(), cli.SKILL_RESOURCE.read_bytes())

    def test_yes_copies_to_isolated_home_without_real_home(self):
        with tempfile.TemporaryDirectory(prefix="hpr-skill-home-") as home, \
             mock.patch.dict(os.environ, {"HOME": home}), \
             mock.patch.object(sys, "argv", ["hpr", "install-skill", "--yes"]):
            self.assertEqual(0, cli.main())
            installed = Path(home) / ".codex" / "skills" / "hyperresearch-codex" / "SKILL.md"
            self.assertEqual(cli.SKILL_SRC.read_bytes(), installed.read_bytes())

    def test_resource_fallback_copies_without_checkout(self):
        with tempfile.TemporaryDirectory(prefix="hpr-skill-home-") as home, \
             mock.patch.dict(os.environ, {"HOME": home}), \
             mock.patch.object(cli, "SKILL_SRC", Path(home) / "missing"), \
             mock.patch.object(sys, "argv", ["hpr", "install-skill", "--yes"]):
            self.assertEqual(0, cli.main())
            installed = Path(home) / ".codex" / "skills" / "hyperresearch-codex" / "SKILL.md"
            self.assertEqual(cli.SKILL_RESOURCE.read_bytes(), installed.read_bytes())


if __name__ == "__main__":
    unittest.main()
