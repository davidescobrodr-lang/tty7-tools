import json
import os
import tempfile
import unittest
from pathlib import Path

from helpers import load, run

SID = "11111111-2222-3333-4444-555555555555"


def write_session(dirpath, lines, sid=SID):
    proj = Path(dirpath) / "projects" / "-tmp-proj"
    proj.mkdir(parents=True, exist_ok=True)
    path = proj / f"{sid}.jsonl"
    with open(path, "w") as f:
        for line in lines:
            f.write(line if isinstance(line, str) else json.dumps(line))
            f.write("\n")
    return path


def user(content, ts="2026-11-19T10:00:00.000Z", meta=False, cwd="/tmp/proj"):
    d = {"type": "user", "cwd": cwd, "timestamp": ts, "sessionId": SID,
         "message": {"role": "user", "content": content}}
    if meta:
        d["isMeta"] = True
    return d


class ParseSession(unittest.TestCase):
    def setUp(self):
        self.m = load("claude-sesiones")
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_title_from_ai_title(self):
        p = write_session(self.tmp.name, [
            user("hola"),
            {"type": "ai-title", "aiTitle": "Primero", "sessionId": SID},
            {"type": "ai-title", "aiTitle": "Segundo", "sessionId": SID},
        ])
        s = self.m.parse_session(p)
        self.assertEqual(s["title"], "Segundo")
        self.assertEqual(s["id"], SID)

    def test_title_from_first_real_prompt(self):
        p = write_session(self.tmp.name, [
            user("<local-command-caveat>x</local-command-caveat>", meta=True),
            user("<command-name>/theme</command-name>"),
            user([{"type": "tool_result", "content": "salida"}]),
            user([{"type": "text", "text": "arregla el parser"}]),
            user("segundo prompt"),
        ])
        s = self.m.parse_session(p)
        self.assertEqual(s["title"], "arregla el parser")
        self.assertEqual(s["prompt"], "arregla el parser")

    def test_no_prompt(self):
        p = write_session(self.tmp.name, [
            user("<command-name>/theme</command-name>"),
            user("caveat", meta=True),
        ])
        self.assertEqual(self.m.parse_session(p)["title"], "(sin prompt)")

    def test_bad_line_skipped(self):
        p = write_session(self.tmp.name, [
            user("primer prompt"),
            '{"type":"us',
            user("otro", ts="2026-11-19T11:00:00.000Z"),
        ])
        s = self.m.parse_session(p)
        self.assertEqual(s["title"], "primer prompt")
        self.assertEqual(s["end"], "2026-11-19T11:00:00.000Z")

    def test_start_end(self):
        p = write_session(self.tmp.name, [
            user("b", ts="2026-11-19T12:00:00.000Z"),
            user("a", ts="2026-11-19T09:00:00.000Z"),
            user("c", ts="2026-11-19T10:00:00.000Z"),
        ])
        s = self.m.parse_session(p)
        self.assertEqual(s["start"], "2026-11-19T09:00:00.000Z")
        self.assertEqual(s["end"], "2026-11-19T12:00:00.000Z")
        self.assertEqual(s["cwd"], "/tmp/proj")

    def test_resume_command(self):
        s = {"id": SID, "cwd": "/tmp/a b"}
        self.assertEqual(self.m.resume_command("claude-david", s),
                         f"cd '/tmp/a b' && claude-david --resume {SID}")


class Minors(unittest.TestCase):
    def setUp(self):
        self.m = load("claude-sesiones")
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_real_prompt_starting_with_lt(self):
        p = write_session(self.tmp.name, [
            user("<system-reminder>x</system-reminder>"),
            user("<div>arregla este html</div>"),
        ])
        self.assertEqual(self.m.parse_session(p)["title"], "<div>arregla este html</div>")

    def test_known_wrappers_skipped(self):
        for text in ("<command-name>/x</command-name>", "<local-command-stdout>x</local-command-stdout>",
                     "<bash-input>ls</bash-input>", "<task-notification>x</task-notification>"):
            p = write_session(self.tmp.name, [user(text), user("real")])
            self.assertEqual(self.m.parse_session(p)["title"], "real", text)

    def test_clean_removes_control_chars(self):
        self.assertEqual(self.m.clean("a\x1b[31mrojo\x1b[0m\tb\nc\x07"), "a[31mrojo[0m b c")

    def test_limit_reads_most_recent_files(self):
        root = Path(self.tmp.name)
        old = write_session(root, [user("vieja", ts="2026-01-01T00:00:00Z")], sid="a" * 8)
        new = write_session(root, [user("nueva", ts="2026-01-02T00:00:00Z")], sid="b" * 8)
        os.utime(old, (1000, 1000))
        os.utime(new, (2000, 2000))
        calls = []
        real = self.m.parse_session
        self.m.parse_session = lambda p: calls.append(p) or real(p)
        rows = self.m.list_sessions(roots=[("david", root, "claude-david")], limit=1)
        self.assertEqual([r["title"] for r in rows], ["nueva"])
        self.assertEqual(len(calls), 1)

    def test_no_sessions_exit_code(self):
        env = {"HOME": self.tmp.name}
        for args in ([], ["--json"]):
            r = run("claude-sesiones", *args, env=env)
            self.assertEqual(r.returncode, 1, args)
        self.assertEqual(run("claude-sesiones", "--json", env=env).stdout.strip(), "[]")


class Select(unittest.TestCase):
    def setUp(self):
        self.m = load("claude-sesiones")
        self.sessions = [
            {"id": "1", "cwd": "/home/x/api", "title": "Arreglar Login", "prompt": "p1", "end": "2"},
            {"id": "2", "cwd": "/home/x/web", "title": "otra cosa", "prompt": "revisar LOGIN", "end": "3"},
            {"id": "3", "cwd": "/home/x/api", "title": "docs", "prompt": "p3", "end": "1"},
        ]

    def test_text_filter_case_insensitive(self):
        ids = [s["id"] for s in self.m.select(self.sessions, text="login", here=None)]
        self.assertEqual(sorted(ids), ["1", "2"])

    def test_here_filter(self):
        ids = [s["id"] for s in self.m.select(self.sessions, text=None, here="/home/x/api")]
        self.assertEqual(sorted(ids), ["1", "3"])

    def test_sorted_by_end_desc(self):
        ids = [s["id"] for s in self.m.select(self.sessions, text=None, here=None)]
        self.assertEqual(ids, ["2", "1", "3"])


if __name__ == "__main__":
    unittest.main()
