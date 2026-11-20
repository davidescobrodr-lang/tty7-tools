# tty7-tools

Herramientas pequeñas para delegar trabajo a agentes en panes de [tty7](https://github.com/l0ng-ai/tty7).
Copian ideas de Orca (historial de sesiones, entrega estructurada, preguntas, registro de corridas)
sin otra aplicación en memoria. Solo Python 3 (biblioteca estándar).

## Instalar

```bash
./install.sh          # symlinks en ~/.local/bin; no cambia archivos reales con el mismo nombre
```

## Comandos

| Comando | Quién lo usa | Qué hace |
|---|---|---|
| `claude-sesiones [texto] [--aqui] [--cuenta david\|trabajo] [-n N] [-v] [--todas] [--json]` | tú | Lista las sesiones de `~/.claude-david` y `~/.claude`. Oculta las de `/tmp` (workers y pruebas); `--todas` las muestra. Con `-v`, muestra el comando de resume con la cuenta correcta. |
| `tty7-done --outcome succeeded\|failed --summary "..." [--base REF]` | worker | Escribe `.tty7-tareas/resultado.json`: resultado, rama, commit, archivos cambiados, `dirty`, `CLAUDE_CONFIG_DIR`. |
| `tty7-ask "<pregunta>" [--options "a,b"]` | worker | Escribe `.tty7-tareas/pregunta.json`. El worker termina su turno después. |
| `tty7-ask --show DIR` / `--close DIR --answer "..."` | coordinador | Muestra la pregunta abierta / la archiva en `.tty7-tareas/preguntas/` con la respuesta. |
| `tty7-trust DIR` / `tty7-trust --remove DIR` | coordinador | Marca DIR como confiable en `~/.claude-david/.claude.json` (`--config-dir` cambia la cuenta). Así `claude-david` no muestra el diálogo de confianza. Usa la raíz de cada worktree. |
| `tty7-run new\|add\|set\|show\|ls` | coordinador | Registro de corridas en `~/.local/state/tty7-runs/` (o `$TTY7_RUNS_DIR`). Estados: `pendiente`, `trabajando`, `pregunta`, `terminada`, `fallida`, `cerrada`. |

## Flujo

1. El coordinador crea la corrida (`tty7-run new`), el worktree y `.tty7-tareas/base`. Después confía en el worktree (`tty7-trust`).
2. Abre una pane, registra el worker (`tty7-run add`) y lanza `claude-david`.
3. Espera con `tty7 wait` en segundo plano.
4. El worker pregunta con `tty7-ask` o entrega con `tty7-done`.
5. El coordinador lee `resultado.json`, verifica la cuenta y el commit, y cierra (`tty7-trust --remove`, `tty7-run set ... cerrada`).

La regla completa está en `~/.claude-david/CLAUDE.md` ("Subagentes de superpowers en panes de tty7").

## Tests

```bash
python3 -m unittest discover -s tests
```

## Licencia

MIT. Ver `LICENSE`.
