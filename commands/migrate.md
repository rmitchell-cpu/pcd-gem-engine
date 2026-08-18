---
description: Run the Supabase schema migration (dry-run by default)
argument-hint: [--apply]
---

Run the database migration for the engine schema (`migrations/`).

Default to a dry run so the user can review the SQL first:

```bash
./.venv/bin/python migrate.py --dry-run
```

Only execute the migration for real if the user passed `--apply` or explicitly confirmed:

```bash
./.venv/bin/python migrate.py
```

The live run reads `DATABASE_URL` from `.env` (or accepts `--db-url`). Never echo the connection string back into the conversation. Applying a migration changes the live Supabase schema — treat it as irreversible and confirm with the user before running without `--dry-run`.
