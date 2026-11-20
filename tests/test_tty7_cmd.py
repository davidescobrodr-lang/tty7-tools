import json
import os
import shlex
import tempfile
import unittest
from pathlib import Path

from helpers import run

# tty7 falso: registra cada llamada y simula pane ls / split / exec / pane close.
FAKE = r'''#!/usr/bin/env python3
import json, os, sys
st_path = os.environ["FAKE_STATE"]
st = json.load(open(st_path))
args = sys.argv[1:]
st["calls"].append(args)
out, rc = "", 0
if args[:2] == ["pane", "ls"]:
    out = json.dumps({"panes": [{"pane": p, "live": True} for p in st["panes"]]})
elif args[0] == "split":
    p = st["next"]; st["next"] += 1; st["panes"].append(p); out = "%" + str(p)
elif args[0] == "exec":
    line = " ".join(args[args.index("--") + 1:])
    if st["warmup_fails"] > 0 and line == "true":
        st["warmup_fails"] -= 1; rc = 1
    elif line == "true":
        rc = 0
    else:
        out = "salida: " + line; rc = st["rc"]
elif args[:2] == ["pane", "close"]:
    for a in args[2:]:
        st["panes"] = [p for p in st["panes"] if "%" + str(p) != a]
json.dump(st, open(st_path, "w"))
if out:
    print(out)
sys.exit(rc)
'''


class Tty7Cmd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        (t / "bin").mkdir()
        fake = t / "bin" / "tty7"
        fake.write_text(FAKE)
        fake.chmod(0o755)
        self.state = t / "fake.json"
        self.save({"calls": [], "panes": [101], "next": 200, "warmup_fails": 0, "rc": 0})
        self.env = {"PATH": f"{t / 'bin'}:{os.environ['PATH']}", "FAKE_STATE": str(self.state),
                    "TTY7_PANE": "101", "TTY7_CMD_STATE_DIR": str(t / "st"),
                    "TTY7_CMD_SLEEP": "0"}
        self.work = t / "work dir"
        self.work.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def save(self, d):
        self.state.write_text(json.dumps(d))

    def fake(self):
        return json.loads(self.state.read_text())

    def cmd(self, *args, cwd=None):
        return run("tty7-cmd", *args, env=self.env, cwd=cwd or self.work)

    def execs(self):
        return [c for c in self.fake()["calls"] if c[0] == "exec"]

    def test_opens_pane_below_and_warms_up(self):
        r = self.cmd("git", "status")
        self.assertEqual(r.returncode, 0, r.stderr)
        calls = self.fake()["calls"]
        self.assertIn(["split", "%101", "--h"], calls)
        ex = self.execs()
        self.assertEqual(ex[0][-1], "true")  # calentamiento
        self.assertEqual(ex[-1][1], "%200")
        self.assertEqual(ex[-1][ex[-1].index("--") + 1:],
                         [f"cd {shlex.quote(str(self.work))} && git status"])
        self.assertIn("salida:", r.stdout)

    def test_reuses_live_pane(self):
        self.cmd("ls")
        self.cmd("pwd")
        splits = [c for c in self.fake()["calls"] if c[0] == "split"]
        self.assertEqual(len(splits), 1)
        self.assertEqual(self.execs()[-1][1], "%200")
        self.assertEqual(len([e for e in self.execs() if e[-1] == "true"]), 1)

    def test_reopens_if_pane_gone(self):
        self.cmd("ls")
        d = self.fake()
        d["panes"] = [101]
        self.save(d)
        self.cmd("ls")
        self.assertEqual(len([c for c in self.fake()["calls"] if c[0] == "split"]), 2)
        self.assertEqual(self.execs()[-1][1], "%201")

    def test_state_is_per_coordinator_pane(self):
        self.cmd("ls")
        d = self.fake()
        d["panes"].append(102)
        self.save(d)
        self.env["TTY7_PANE"] = "%102"
        self.cmd("ls")
        self.assertIn(["split", "%102", "--h"], self.fake()["calls"])

    def test_warmup_retries_until_ready(self):
        d = self.fake()
        d["warmup_fails"] = 2
        self.save(d)
        r = self.cmd("ls")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len([e for e in self.execs() if e[-1] == "true"]), 3)

    def test_warmup_gives_up(self):
        d = self.fake()
        d["warmup_fails"] = 99
        self.save(d)
        r = self.cmd("ls")
        self.assertEqual(r.returncode, 2)
        self.assertIn("no respondió", r.stderr)
        self.assertFalse(any(e[-1].endswith("&& ls") for e in self.execs()))

    def test_exit_code_passes_through(self):
        d = self.fake()
        d["rc"] = 3
        self.save(d)
        self.assertEqual(self.cmd("false").returncode, 3)

    def test_timeout_and_cwd_options(self):
        self.cmd("--timeout", "42", "--cwd", "/opt", "--", "make", "-j2")
        ex = self.execs()[-1]
        self.assertEqual(ex[ex.index("--timeout") + 1], "42")
        self.assertEqual(ex[-1], "cd /opt && make -j2")

    def test_close(self):
        self.cmd("ls")
        r = self.cmd("--close")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(["pane", "close", "%200"], self.fake()["calls"])
        self.cmd("ls")
        self.assertEqual(self.execs()[-1][1], "%201")

    def test_close_without_pane_is_ok(self):
        r = self.cmd("--close")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(any(c[:2] == ["pane", "close"] for c in self.fake()["calls"]))

    def test_needs_tty7_pane(self):
        del self.env["TTY7_PANE"]
        r = run("tty7-cmd", "ls", env={**self.env, "TTY7_PANE": ""}, cwd=self.work)
        self.assertEqual(r.returncode, 2)
        self.assertIn("TTY7_PANE", r.stderr)

    def test_needs_command(self):
        r = self.cmd()
        self.assertEqual(r.returncode, 2)
        self.assertIn("falta el comando", r.stderr)


if __name__ == "__main__":
    unittest.main()
