"""Tests de los menores de la revisión final en tty7-done, tty7-ask y tty7-run."""
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path

from helpers import load, run
from test_tty7_done import make_repo, result


class WriteJsonCleanup(unittest.TestCase):
    def test_no_tmp_left_when_dump_fails(self):
        for name in ("tty7-done", "tty7-ask", "tty7-run"):
            m = load(name)
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(TypeError):
                    m.write_json(Path(d) / "x.json", {"bad": object()})
                self.assertEqual(os.listdir(d), [], name)


class DoneInvalidBase(unittest.TestCase):
    def test_invalid_base_gives_null_and_warning(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d)
            r = run("tty7-done", "--outcome", "succeeded", "--summary", "x", "--base", "deadbeef", cwd=d)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIsNone(result(d)["files_changed"])
            self.assertIn("deadbeef", r.stderr)


class CorruptJson(unittest.TestCase):
    def test_run_ls_with_corrupt_file(self):
        with tempfile.TemporaryDirectory() as d:
            env = {"TTY7_RUNS_DIR": d}
            rid = run("tty7-run", "new", "buena", env=env).stdout.strip()
            (Path(d) / "20200101-000000-rota.json").write_text("{rota")
            r = run("tty7-run", "ls", env=env)
            self.assertNotIn("Traceback", r.stderr)
            self.assertIn(rid, r.stdout)
            self.assertIn("20200101-000000-rota", r.stderr)

    def test_run_show_corrupt_file(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "20200101-000000-rota.json").write_text("{rota")
            r = run("tty7-run", "show", "20200101", env={"TTY7_RUNS_DIR": d})
            self.assertEqual(r.returncode, 2)
            self.assertNotIn("Traceback", r.stderr)
            self.assertIn("JSON", r.stderr)

    def test_ask_show_corrupt_file(self):
        with tempfile.TemporaryDirectory() as d:
            q = Path(d) / ".tty7-tareas" / "pregunta.json"
            q.parent.mkdir()
            q.write_text("{rota")
            for args in (["--show", d], ["--close", d, "--answer", "a"]):
                r = run("tty7-ask", *args)
                self.assertEqual(r.returncode, 2, args)
                self.assertNotIn("Traceback", r.stderr)
                self.assertTrue(q.exists())


class RunSlug(unittest.TestCase):
    def test_accents_kept_as_ascii(self):
        m = load("tty7-run")
        self.assertEqual(m.slug("Revisión única ñandú"), "revision-unica-nandu")


class RunLock(unittest.TestCase):
    def test_parallel_sets_keep_every_update(self):
        with tempfile.TemporaryDirectory() as d:
            env = {"TTY7_RUNS_DIR": d}
            rid = run("tty7-run", "new", "x", env=env).stdout.strip()
            tasks = [f"t{i}" for i in range(8)]
            for t in tasks:
                run("tty7-run", "add", rid, t, env=env)
            threads = [threading.Thread(target=run, args=("tty7-run", "set", rid, t, "--status", "terminada"),
                                        kwargs={"env": env}) for t in tasks]
            for th in threads:
                th.start()
            for th in threads:
                th.join()
            data = json.loads((Path(d) / f"{rid}.json").read_text())
            self.assertEqual({t["status"] for t in data["tasks"].values()}, {"terminada"})


if __name__ == "__main__":
    unittest.main()
