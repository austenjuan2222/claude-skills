"""Tests for tools/skill_links.py. Run: python -m unittest discover -s tools/tests"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import skill_links as sl  # noqa: E402


def write(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


class LinkSkillsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.repo_skills = base / "repo" / "skills"
        self.home_skills = base / "home" / ".claude" / "skills"
        self.backup_root = base / "home" / ".claude" / "skills-backup"
        write(self.repo_skills / "alpha" / "SKILL.md", "alpha v2\n")
        write(self.repo_skills / "beta" / "SKILL.md", "beta\n")
        write(self.repo_skills / "_jutsu" / "mod" / "SKILL.md", "jutsu\n")
        write(self.repo_skills / "_sources" / "x.json", "{}\n")
        self.home_skills.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def run_link(self, dry=False):
        return sl.link_skills(self.repo_skills, self.home_skills, self.backup_root, dry=dry, stamp="T")

    def test_creates_links_for_every_repo_skill_except_sources(self):
        rep = self.run_link()
        for name in ("alpha", "beta", "_jutsu"):
            self.assertTrue(sl.is_link(self.home_skills / name), name)
            self.assertTrue(sl.same_target(self.home_skills / name, self.repo_skills / name), name)
        self.assertEqual((self.home_skills / "_jutsu" / "mod" / "SKILL.md").read_text(encoding="utf-8"), "jutsu\n")
        self.assertFalse((self.home_skills / "_sources").exists())
        self.assertEqual(sorted(rep["linked"]), ["_jutsu", "alpha", "beta"])

    def test_identical_copy_is_replaced_and_backed_up(self):
        write(self.home_skills / "beta" / "SKILL.md", "beta\r\n")  # CRLF-only difference counts as identical
        rep = self.run_link()
        self.assertTrue(sl.is_link(self.home_skills / "beta"))
        self.assertIn("beta", rep["replaced_identical"])
        self.assertTrue((self.backup_root / "T" / "beta" / "SKILL.md").exists())

    def test_different_copy_is_backed_up_not_deleted(self):
        write(self.home_skills / "alpha" / "SKILL.md", "alpha LOCAL EDIT\n")
        rep = self.run_link()
        self.assertTrue(sl.is_link(self.home_skills / "alpha"))
        self.assertIn("alpha", rep["replaced_different"])
        self.assertEqual((self.backup_root / "T" / "alpha" / "SKILL.md").read_text(encoding="utf-8"),
                         "alpha LOCAL EDIT\n")
        self.assertEqual((self.repo_skills / "alpha" / "SKILL.md").read_text(encoding="utf-8"), "alpha v2\n")

    def test_skills_not_in_repo_are_left_alone(self):
        write(self.home_skills / "docx" / "SKILL.md", "builtin\n")
        rep = self.run_link()
        self.assertFalse(sl.is_link(self.home_skills / "docx"))
        self.assertEqual((self.home_skills / "docx" / "SKILL.md").read_text(encoding="utf-8"), "builtin\n")
        self.assertIn("docx", rep["not_in_repo"])

    def test_second_run_is_noop(self):
        self.run_link()
        rep = self.run_link()
        self.assertEqual(rep["linked"], [])
        self.assertEqual(sorted(rep["ok"]), ["_jutsu", "alpha", "beta"])

    def test_stale_link_to_deleted_repo_skill_is_removed_without_touching_repo(self):
        self.run_link()
        (self.repo_skills / "beta" / "SKILL.md").unlink()
        (self.repo_skills / "beta").rmdir()
        rep = self.run_link()
        self.assertFalse(os.path.lexists(self.home_skills / "beta"))
        self.assertIn("beta", rep["removed_stale"])
        self.assertTrue((self.repo_skills / "alpha" / "SKILL.md").exists())

    def test_dry_run_changes_nothing(self):
        write(self.home_skills / "alpha" / "SKILL.md", "alpha LOCAL EDIT\n")
        rep = self.run_link(dry=True)
        self.assertFalse(sl.is_link(self.home_skills / "alpha"))
        self.assertFalse(os.path.lexists(self.home_skills / "beta"))
        self.assertFalse(self.backup_root.exists())
        self.assertIn("alpha", rep["replaced_different"])
        self.assertIn("beta", rep["linked"])

    def test_whole_folder_already_pointing_at_repo_is_skipped(self):
        self.home_skills.rmdir()
        sl.make_link(self.home_skills, self.repo_skills)
        rep = self.run_link()
        self.assertTrue(rep["whole_dir_linked"])
        self.assertEqual(rep["linked"], [])


class JunctionDetectionTest(unittest.TestCase):
    """Python 3.11 沒有 os.path.isjunction / Path.is_junction，要靠 lstat 的 reparse-point 屬性判斷。"""

    def test_reparse_point_counts_as_link_without_isjunction(self):
        from unittest import mock
        fake = mock.Mock(st_file_attributes=0x400)
        with mock.patch.object(sl.os.path, "islink", return_value=False), \
                mock.patch.object(sl.os.path, "isjunction", None, create=True), \
                mock.patch.object(sl.os, "lstat", return_value=fake):
            self.assertTrue(sl.is_link(Path("C:/x")))

    def test_plain_dir_is_not_link_without_isjunction(self):
        from unittest import mock
        fake = mock.Mock(st_file_attributes=0x10)  # FILE_ATTRIBUTE_DIRECTORY only
        with mock.patch.object(sl.os.path, "islink", return_value=False), \
                mock.patch.object(sl.os.path, "isjunction", None, create=True), \
                mock.patch.object(sl.os, "lstat", return_value=fake):
            self.assertFalse(sl.is_link(Path("C:/x")))


if __name__ == "__main__":
    unittest.main()
