import json
import tempfile
import unittest
from pathlib import Path

from helpers import load

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
