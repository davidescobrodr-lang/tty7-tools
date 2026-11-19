import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import run


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def make_repo(path):
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.name", "t")
    git(path, "config", "user.email", "t@t")
    (Path(path) / "base.txt").write_text("base")
    git(path, "add", "-A")
    git(path, "commit", "-qm", "base")
    base = git(path, "rev-parse", "HEAD")
    git(path, "checkout", "-qb", "worker")
    (Path(path) / "a.txt").write_text("trabajo")
    git(path, "add", "a.txt")
    git(path, "commit", "-qm", "trabajo")
    return base


def result(path):
    return json.loads((Path(path) / ".tty7-tareas" / "resultado.json").read_text())


class Tty7Done(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_writes_result_in_git_repo(self):
        base = make_repo(self.dir)
        (Path(self.dir) / ".tty7-tareas").mkdir()
        (Path(self.dir) / ".tty7-tareas" / "base").write_text(base + "\n")
        r = run("tty7-done", "--outcome", "succeeded", "--summary", "hecho", cwd=self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        d = result(self.dir)
        self.assertEqual(d["outcome"], "succeeded")
        self.assertEqual(d["summary"], "hecho")
        self.assertEqual(d["branch"], "worker")
        self.assertEqual(d["commit"], git(self.dir, "rev-parse", "HEAD"))
        self.assertEqual(d["base"], base)
        self.assertEqual(d["files_changed"], ["a.txt"])
        self.assertFalse(d["dirty"])

    def test_without_base_uses_last_commit(self):
        make_repo(self.dir)
        run("tty7-done", "--outcome", "succeeded", "--summary", "x", cwd=self.dir)
        d = result(self.dir)
        self.assertIsNone(d["base"])
        self.assertEqual(d["files_changed"], ["a.txt"])

    def test_not_a_repo(self):
        r = run("tty7-done", "--outcome", "failed", "--summary", "solo lectura", cwd=self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        d = result(self.dir)
        self.assertIsNone(d["branch"])
        self.assertIsNone(d["commit"])
        self.assertIsNone(d["files_changed"])

    def test_dirty_flag(self):
        make_repo(self.dir)
        (Path(self.dir) / "a.txt").write_text("cambio sin commit")
        r = run("tty7-done", "--outcome", "succeeded", "--summary", "x", cwd=self.dir)
        self.assertTrue(result(self.dir)["dirty"])
        self.assertIn("aviso", r.stderr)

    def test_tareas_dir_not_dirty(self):
        make_repo(self.dir)
        (Path(self.dir) / ".git" / "info" / "exclude").write_text(".tty7-tareas/\n")
        run("tty7-done", "--outcome", "succeeded", "--summary", "x", cwd=self.dir)
        self.assertFalse(result(self.dir)["dirty"])

    def test_config_dir_recorded(self):
        run("tty7-done", "--outcome", "succeeded", "--summary", "x", cwd=self.dir,
            env={"CLAUDE_CONFIG_DIR": "/x"})
        self.assertEqual(result(self.dir)["claude_config_dir"], "/x")

    def test_outcome_required(self):
        r = run("tty7-done", "--summary", "x", cwd=self.dir)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--outcome", r.stderr)

    def test_bad_outcome(self):
        r = run("tty7-done", "--outcome", "ok", "--summary", "x", cwd=self.dir)
        self.assertEqual(r.returncode, 2)
        self.assertIn("'ok'", r.stderr)


if __name__ == "__main__":
    unittest.main()
