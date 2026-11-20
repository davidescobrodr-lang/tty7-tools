import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from helpers import load, run


class Tty7Trust(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.conf = self.home / ".claude-david"
        self.conf.mkdir()
        self.cfg = self.conf / ".claude.json"
        self.other = {"numStartups": 7, "projects": {"/x": {"hasTrustDialogAccepted": True,
                                                             "lastSessionId": "s"}}}
        self.cfg.write_text(json.dumps(self.other))
        os.chmod(self.cfg, 0o600)
        self.wt = self.home / "wt"
        self.wt.mkdir()
        self.env = {"HOME": str(self.home), "CLAUDE_CONFIG_DIR": str(self.home / "otra")}

    def tearDown(self):
        self.tmp.cleanup()

    def data(self):
        return json.loads(self.cfg.read_text())

    def test_trust_adds_entry_and_keeps_rest(self):
        r = run("tty7-trust", str(self.wt), env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        d = self.data()
        entry = d["projects"][os.path.realpath(self.wt)]
        self.assertIs(entry["hasTrustDialogAccepted"], True)
        self.assertEqual(entry["allowedTools"], [])
        self.assertEqual(d["numStartups"], 7)
        self.assertEqual(d["projects"]["/x"], self.other["projects"]["/x"])

    def test_default_is_claude_david_not_env(self):
        run("tty7-trust", str(self.wt), env=self.env)
        self.assertFalse((self.home / "otra").exists())
        self.assertIn(os.path.realpath(self.wt), self.data()["projects"])

    def test_config_dir_option(self):
        other = self.home / "c2"
        other.mkdir()
        (other / ".claude.json").write_text("{}")
        r = run("tty7-trust", str(self.wt), "--config-dir", str(other), env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads((other / ".claude.json").read_text())
        self.assertTrue(d["projects"][os.path.realpath(self.wt)]["hasTrustDialogAccepted"])

    def test_relative_path_and_existing_entry(self):
        key = os.path.realpath(self.wt)
        self.cfg.write_text(json.dumps({"projects": {key: {"hasTrustDialogAccepted": False,
                                                            "allowedTools": ["Bash"]}}}))
        r = run("tty7-trust", "wt", cwd=self.home, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        entry = self.data()["projects"][key]
        self.assertIs(entry["hasTrustDialogAccepted"], True)
        self.assertEqual(entry["allowedTools"], ["Bash"])

    def test_keeps_file_mode(self):
        run("tty7-trust", str(self.wt), env=self.env)
        self.assertEqual(stat.S_IMODE(self.cfg.stat().st_mode), 0o600)

    def test_remove(self):
        run("tty7-trust", str(self.wt), env=self.env)
        self.wt.rmdir()  # el worktree ya no existe al limpiar
        r = run("tty7-trust", "--remove", str(self.wt), env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        d = self.data()
        self.assertNotIn(os.path.realpath(self.wt), d["projects"])
        self.assertIn("/x", d["projects"])

    def test_remove_missing_entry_is_ok(self):
        r = run("tty7-trust", "--remove", str(self.wt), env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.data(), self.other)

    def test_missing_dir_fails(self):
        r = run("tty7-trust", str(self.home / "no"), env=self.env)
        self.assertEqual(r.returncode, 2)
        self.assertIn("no existe", r.stderr)
        self.assertEqual(self.data(), self.other)

    def test_missing_config_fails(self):
        self.cfg.unlink()
        r = run("tty7-trust", str(self.wt), env=self.env)
        self.assertEqual(r.returncode, 2)
        self.assertIn(".claude.json", r.stderr)
        self.assertFalse(self.cfg.exists())

    def test_corrupt_config_untouched(self):
        self.cfg.write_text('{"projects": ')
        r = run("tty7-trust", str(self.wt), env=self.env)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.cfg.read_text(), '{"projects": ')

    def test_retries_if_file_changes_during_update(self):
        m = load("tty7-trust")
        calls = []
        real = m._changed

        def changed(path, before):
            calls.append(1)
            if len(calls) == 1:  # otro proceso escribe entre la lectura y el reemplazo
                data = json.loads(path.read_text())
                data["numStartups"] = 8
                path.write_text(json.dumps(data))
                return True
            return real(path, before)

        m._changed = changed
        m.update(self.cfg, lambda projects: projects.setdefault("/y", {"hasTrustDialogAccepted": True}))
        d = self.data()
        self.assertEqual(d["numStartups"], 8)
        self.assertIn("/y", d["projects"])
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
