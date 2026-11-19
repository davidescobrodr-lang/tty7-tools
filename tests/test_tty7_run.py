import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from helpers import run


class Tty7Run(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = {"TTY7_RUNS_DIR": self.tmp.name}

    def tearDown(self):
        self.tmp.cleanup()

    def r(self, *args):
        return run("tty7-run", *args, env=self.env)

    def data(self, run_id):
        return json.loads((Path(self.tmp.name) / f"{run_id}.json").read_text())

    def test_new_prints_id(self):
        r = self.r("new", "Revisar el parser y los Tests!")
        self.assertEqual(r.returncode, 0, r.stderr)
        rid = r.stdout.strip()
        self.assertRegex(rid, r"^\d{8}-\d{6}-revisar-el-parser-y-los-tests$")
        d = self.data(rid)
        self.assertEqual(d["id"], rid)
        self.assertEqual(d["objective"], "Revisar el parser y los Tests!")
        self.assertEqual(d["tasks"], {})

    def test_slug_max_30(self):
        rid = self.r("new", "a" * 80).stdout.strip()
        self.assertEqual(len(rid.split("-", 2)[2]), 30)

    def test_add_and_set(self):
        rid = self.r("new", "x").stdout.strip()
        r = self.r("add", rid, "t1", "--pane", "%12", "--worktree", "/w/t1", "--branch", "w/t1")
        self.assertEqual(r.returncode, 0, r.stderr)
        t = self.data(rid)["tasks"]["t1"]
        self.assertEqual((t["pane"], t["worktree"], t["branch"], t["status"]),
                         ("%12", "/w/t1", "w/t1", "pendiente"))
        self.assertEqual(self.r("set", rid, "t1", "--status", "terminada", "--note", "ok").returncode, 0)
        t = self.data(rid)["tasks"]["t1"]
        self.assertEqual((t["status"], t["note"]), ("terminada", "ok"))
        self.assertIn("updated", t)

    def test_set_unknown_task(self):
        rid = self.r("new", "x").stdout.strip()
        r = self.r("set", rid, "nope", "--status", "terminada")
        self.assertEqual(r.returncode, 2)
        self.assertIn("nope", r.stderr)

    def test_invalid_status(self):
        rid = self.r("new", "x").stdout.strip()
        self.r("add", rid, "t1")
        r = self.r("set", rid, "t1", "--status", "lista")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.data(rid)["tasks"]["t1"]["status"], "pendiente")

    def test_prefix_lookup(self):
        rid = self.r("new", "unico").stdout.strip()
        self.assertEqual(self.r("add", rid[:10], "t1").returncode, 0)
        self.assertIn("t1", self.data(rid)["tasks"])

    def test_ambiguous_prefix(self):
        a = self.r("new", "uno").stdout.strip()
        time.sleep(1.1)
        self.r("new", "dos")
        r = self.r("show", a[:4])
        self.assertEqual(r.returncode, 2)
        self.assertIn("ambiguo", r.stderr)

    def test_show_latest(self):
        self.r("new", "vieja")
        time.sleep(1.1)
        rid = self.r("new", "nueva").stdout.strip()
        self.r("add", rid, "t1", "--pane", "%5")
        r = self.r("show")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("nueva", r.stdout)
        self.assertIn("t1", r.stdout)
        self.assertIn("%5", r.stdout)
        self.assertEqual(json.loads(self.r("show", "--json").stdout)["id"], rid)

    def test_ls(self):
        rid = self.r("new", "x").stdout.strip()
        self.r("add", rid, "t1")
        self.r("add", rid, "t2")
        self.r("set", rid, "t2", "--status", "terminada")
        out = self.r("ls").stdout
        self.assertIn(rid, out)
        self.assertRegex(out, r"pendiente: 1")
        self.assertRegex(out, r"terminada: 1")

    def test_atomic_write(self):
        rid = self.r("new", "x").stdout.strip()
        self.r("add", rid, "t1")
        self.r("set", rid, "t1", "--status", "trabajando")
        leftovers = [n for n in os.listdir(self.tmp.name) if n.endswith(".tmp")]
        self.assertEqual(leftovers, [])
        self.assertEqual(self.data(rid)["tasks"]["t1"]["status"], "trabajando")

    def test_no_runs(self):
        r = self.r("show")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Sin corridas", r.stdout)


if __name__ == "__main__":
    unittest.main()
