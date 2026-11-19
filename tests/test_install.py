import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT


class Install(unittest.TestCase):
    def run_install(self, home):
        return subprocess.run(["bash", str(ROOT / "install.sh")], capture_output=True, text=True,
                              env={**os.environ, "HOME": home})

    def test_links_only_executable_files(self):
        with tempfile.TemporaryDirectory() as home:
            cache = ROOT / "bin" / "__pycache__"
            cache.mkdir(exist_ok=True)
            self.addCleanup(cache.rmdir)
            self.run_install(home)
            names = sorted(os.listdir(Path(home) / ".local/bin"))
            self.assertNotIn("__pycache__", names)
            self.assertIn("claude-sesiones", names)

    def test_does_not_replace_real_file(self):
        with tempfile.TemporaryDirectory() as home:
            real = Path(home) / ".local/bin/claude-sesiones"
            real.parent.mkdir(parents=True)
            real.write_text("mío")
            r = self.run_install(home)
            self.assertEqual(real.read_text(), "mío")
            self.assertIn("aviso", r.stderr)


if __name__ == "__main__":
    unittest.main()
