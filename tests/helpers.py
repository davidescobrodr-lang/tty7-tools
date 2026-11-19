"""Utilidades de test: cargar un script de bin/ como módulo y ejecutarlo."""
import importlib.machinery
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin"


def load(name):
    """Carga bin/<name> (sin extensión .py) como módulo."""
    path = BIN / name
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_"), str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def run(name, *args, cwd=None, env=None):
    """Ejecuta bin/<name> con argumentos. Devuelve CompletedProcess."""
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    return subprocess.run(
        [sys.executable, str(BIN / name), *args],
        cwd=cwd, env=full_env, capture_output=True, text=True,
    )
