"""Compile the versioned examples and run every root test_v*.py independently."""
from __future__ import annotations

import argparse
import importlib
import os
from pathlib import Path
import py_compile
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def summary(message):
    print(message, flush=True)
    destination = os.environ.get("GITHUB_STEP_SUMMARY")
    if destination:
        with open(destination, "a", encoding="utf-8") as stream:
            stream.write(message + "\n")


def compile_project():
    files = sorted(set(ROOT.glob("study_guide_v*.py")) | set(ROOT.glob("test_v*.py"))
                   | set((ROOT / "scripts").glob("*.py")))
    if not files:
        raise RuntimeError("No project Python files were found")
    for path in files:
        py_compile.compile(str(path), doraise=True)
    summary(f"Python syntax: {len(files)} files compiled with Python {sys.version.split()[0]}.")


def run_regressions():
    # Import clients/checkpointers only; no model request is made here.
    for name in ("pydantic", "langchain_ollama", "langgraph.graph", "langgraph.checkpoint.sqlite"):
        importlib.import_module(name)
    scripts = sorted(ROOT.glob("test_v*.py"))
    if not scripts:
        raise RuntimeError("No offline regression scripts were found")
    environment = {**os.environ, "PYTHONUTF8": "1", "PYTHONOPTIMIZE": "0"}
    started = time.perf_counter()
    for path in scripts:
        print(f"\nRunning {path.name}", flush=True)
        # V10 uses module-level assertions. A fresh process also isolates its
        # deliberate reviewer patch from the V11-V17 unittest suites.
        subprocess.run([sys.executable, "-B", str(path)], cwd=ROOT, env=environment,
                       check=True, timeout=180)
    summary(f"Offline regressions: all {len(scripts)} scripts passed "
            f"in {time.perf_counter() - started:.2f} seconds; no Ollama service required.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--compile-only", action="store_true")
    group.add_argument("--tests-only", action="store_true")
    args = parser.parse_args()
    if not args.tests_only:
        compile_project()
    if not args.compile_only:
        run_regressions()


if __name__ == "__main__":
    main()
