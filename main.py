#!/usr/bin/env python3
"""Repository root entrypoint so `uv run main.py` works."""

from pathlib import Path
import sys


def _bootstrap_import_path() -> None:
    """Ensure modules living under `src/` are importable from repo root."""
    root = Path(__file__).resolve().parent
    src_dir = root / "src"
    src_path = str(src_dir)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


def main() -> None:
    _bootstrap_import_path()
    from src.main import main as run_app

    run_app()


if __name__ == "__main__":
    main()
