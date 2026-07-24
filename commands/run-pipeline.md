---
description: Run the full PCD Concierge pipeline on a GP deck PDF
argument-hint: <path/to/deck.pdf>
---

Run the full pipeline on the deck at `$ARGUMENTS`:

```bash
./.venv/bin/python run.py $ARGUMENTS
```

Requirements before running:
- The deck path must exist and be a PDF.
- `.env` must provide the Anthropic and Supabase credentials listed in `.env.example`.

On success the command prints a human-readable review-bundle summary and exits 0. On failure it prints `PIPELINE FAILED` and exits non-zero — inspect `jobs/<job_id>/manifest.json` and `jobs/<job_id>/logs/status_log.jsonl`, report the failing stage and error to the user, and suggest `/pcd-gem-engine:rerun-stage` for a single-stage retry.
