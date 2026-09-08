# `uv run` rather than a bare `gunicorn`: the console script is only on PATH
# if the installer put it there, and uv installs into a .venv it does not
# activate. `uv run` resolves the environment itself.
web: uv run --frozen --no-dev gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 60
