---
description: Start the PCD GEM Engine web dashboard
argument-hint: [--port 8080]
---

Start the FastAPI dashboard in the background:

```bash
./.venv/bin/./.venv/bin/python web_server.py $ARGUMENTS
```

Defaults to `http://127.0.0.1:8000`. Requires the `web` extras (`pip install -e ".[web]"`). Run it as a background task, confirm it came up by fetching the root URL, and tell the user the address. Pass through any `--host`/`--port`/`--reload` flags the user supplied.
