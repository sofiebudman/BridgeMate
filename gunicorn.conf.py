"""
Gunicorn configuration for BridgeMate.
https://docs.gunicorn.org/en/stable/settings.html
"""

import multiprocessing
import os

# ── Server socket ──────────────────────────────────────────────
bind = "127.0.0.1:4000"

# ── Worker processes ───────────────────────────────────────────
# Use 'gevent' for SSE (Server-Sent Events) streaming support.
# Flask's /api/chat endpoint uses SSE, which requires async workers.
worker_class = "gevent"
workers = int(os.environ.get("WEB_CONCURRENCY", multiprocessing.cpu_count() * 2 + 1))
worker_connections = 1000
timeout = 120  # LLM responses can be slow

# ── Logging ────────────────────────────────────────────────────
accesslog = "-"  # stdout
errorlog = "-"  # stderr
loglevel = "info"

# ── Process naming ─────────────────────────────────────────────
proc_name = "bridgemate"

# ── Security ───────────────────────────────────────────────────
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190
