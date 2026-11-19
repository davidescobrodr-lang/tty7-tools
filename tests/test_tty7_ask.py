import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import run


class Tty7Ask(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.q = self.dir / ".tty7-tareas" / "pregunta.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_ask_writes_file(self):
        r = run("tty7-ask", "¿Cambio el componente compartido?", "--options", "compartido, solo-pagina",
                cwd=self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(self.q.read_text())
        self.assertEqual(d["question"], "¿Cambio el componente compartido?")
        self.assertEqual(d["options"], ["compartido", "solo-pagina"])
        self.assertEqual(d["cwd"], str(self.dir.resolve()))
        self.assertIn("time", d)
        self.assertIn("Termina tu turno", r.stdout)

    def test_ask_from_subdirectory_uses_repo_root(self):
        subprocess.run(["git", "init", "-q"], cwd=self.dir, check=True)
        sub = self.dir / "sub"
        sub.mkdir()
        r = run("tty7-ask", "¿Sigo?", cwd=sub)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.q.exists())
        self.assertFalse((sub / ".tty7-tareas").exists())
        self.assertEqual(run("tty7-ask", "--show", str(self.dir)).returncode, 0)

    def test_ask_without_options(self):
        run("tty7-ask", "¿Sigo?", cwd=self.dir)
        self.assertEqual(json.loads(self.q.read_text())["options"], [])

    def test_second_ask_refused(self):
        run("tty7-ask", "primera", cwd=self.dir)
        r = run("tty7-ask", "segunda", cwd=self.dir)
        self.assertEqual(r.returncode, 2)
        self.assertIn("pregunta abierta", r.stderr)
        self.assertEqual(json.loads(self.q.read_text())["question"], "primera")

    def test_close_moves_and_records_answer(self):
        run("tty7-ask", "¿A o B?", cwd=self.dir)
        r = run("tty7-ask", "--close", str(self.dir), "--answer", "A")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.q.exists())
        done = list((self.dir / ".tty7-tareas" / "preguntas").glob("*.json"))
        self.assertEqual(len(done), 1)
        self.assertNotIn(":", done[0].name)
        d = json.loads(done[0].read_text())
        self.assertEqual(d["question"], "¿A o B?")
        self.assertEqual(d["answer"], "A")
        self.assertEqual(r.stdout.strip(), str(done[0]))

    def test_close_requires_answer(self):
        run("tty7-ask", "¿A o B?", cwd=self.dir)
        r = run("tty7-ask", "--close", str(self.dir))
        self.assertEqual(r.returncode, 2)
        self.assertTrue(self.q.exists())

    def test_close_without_question(self):
        r = run("tty7-ask", "--close", str(self.dir), "--answer", "A")
        self.assertEqual(r.returncode, 2)
        self.assertIn("Sin pregunta abierta", r.stderr)

    def test_show(self):
        run("tty7-ask", "¿A o B?", "--options", "A,B", cwd=self.dir)
        r = run("tty7-ask", "--show", str(self.dir))
        self.assertEqual(r.returncode, 0)
        self.assertIn("¿A o B?", r.stdout)
        self.assertIn("A, B", r.stdout)

    def test_show_none(self):
        r = run("tty7-ask", "--show", str(self.dir))
        self.assertEqual(r.returncode, 1)
        self.assertIn("Sin pregunta abierta.", r.stdout)


if __name__ == "__main__":
    unittest.main()
