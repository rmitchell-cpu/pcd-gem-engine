---
description: Rerun a single pipeline stage on an existing job
argument-hint: <stage> <job_id>
---

Rerun one stage of an existing pipeline job. Arguments: `$ARGUMENTS` (first token is the stage, second is the job ID).

```bash
./.venv/bin/python run.py --stage <stage> --job <job_id>
```

Valid stage names (see `src/stages/`):
- `prescreen`
- `01_fund_extract`
- `02_deck_analysis`
- `03_angle_brief`
- `04_preqin_taxonomy`
- `05_deal_card`
- `06_lp_emails`

If the user gave an ambiguous or invalid stage name, list the valid stages instead of guessing. If no job ID was given, run `./.venv/bin/python run.py --list-jobs` first and ask which job to target. On success report the artifact path; on failure report the error from the command output.
