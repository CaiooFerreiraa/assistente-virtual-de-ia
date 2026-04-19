from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import time

WATCH_EXTENSIONS = {".py"}
IGNORED_DIRS = {".git", "__pycache__", ".venv", "venv"}


def iter_watched_files(root: Path):
  for path in root.rglob("*"):
    if any(part in IGNORED_DIRS for part in path.parts):
      continue

    if path.is_file() and path.suffix in WATCH_EXTENSIONS:
      yield path


def snapshot_files(root: Path) -> dict[Path, float]:
  return {
    path: path.stat().st_mtime
    for path in iter_watched_files(root)
  }


def changed_files(previous: dict[Path, float], current: dict[Path, float]) -> list[Path]:
  paths = set(previous) | set(current)
  return sorted(
    path
    for path in paths
    if previous.get(path) != current.get(path)
  )


def stop_process(process: subprocess.Popen) -> None:
  if process.poll() is not None:
    return

  process.terminate()

  try:
    process.wait(timeout=5)
  except subprocess.TimeoutExpired:
    process.kill()
    process.wait()


def start_agent(args: list[str]) -> subprocess.Popen:
  command = [sys.executable, "agent.py", *args]
  print(f"\n[watch] iniciando: {' '.join(command)}\n")
  return subprocess.Popen(command)


def main():
  root = Path.cwd()
  agent_args = sys.argv[1:]

  if agent_args and agent_args[0] == "--":
    agent_args = agent_args[1:]

  process = start_agent(agent_args)
  previous_snapshot = snapshot_files(root)

  try:
    while True:
      time.sleep(1)
      current_snapshot = snapshot_files(root)

      changes = changed_files(previous_snapshot, current_snapshot)
      if changes:
        changed_names = ", ".join(str(path.relative_to(root)) for path in changes[:5])
        print(f"\n[watch] alteracao detectada em {changed_names}. reiniciando agente...\n")
        stop_process(process)
        process = start_agent(agent_args)
        previous_snapshot = current_snapshot

      if process.poll() is not None:
        print(f"\n[watch] agente finalizou com codigo {process.returncode}. reiniciando...\n")
        process = start_agent(agent_args)
        previous_snapshot = snapshot_files(root)
  except KeyboardInterrupt:
    print("\n[watch] encerrando...")
    stop_process(process)


if __name__ == "__main__":
  main()
