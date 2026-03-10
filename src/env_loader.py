import os
from pathlib import Path


def load_env_file(filename: str = ".env") -> None:
    """Load simple KEY=VALUE pairs from the nearest project .env into os.environ."""
    candidates = [
        Path(__file__).resolve().parent.parent / filename,
        Path.cwd() / filename,
    ]

    env_path = next((p for p in candidates if p.exists()), None)
    if env_path is None:
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)
