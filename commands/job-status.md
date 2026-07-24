---
description: Show the manifest and review-bundle summary for a job
argument-hint: <job_id>
---

Show status for job `$ARGUMENTS`:

```bash
./.venv/bin/python run.py --status --job $ARGUMENTS
```

The output is the job manifest as JSON, followed by a human-readable review-bundle summary if `jobs/<job_id>/review_bundle.json` exists. Summarize the current workflow state, completed stages, and any errors for the user rather than dumping the raw JSON. If the job is stuck or failed, point at `jobs/<job_id>/logs/status_log.jsonl` and suggest `/pcd-gem-engine:rerun-stage`.
