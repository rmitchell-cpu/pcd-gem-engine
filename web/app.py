"""PCD GEM Engine — Web Dashboard (FastAPI + Supabase)."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

# Ensure engine root is on sys.path
ENGINE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ENGINE_ROOT))

from config.settings import JOBS_DIR
from src.orchestrator import run_pipeline
from src.persistence import load_manifest

app = FastAPI(title="PCD GEM Engine", debug=True)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# In-memory tracking for running jobs
_running: dict[str, str] = {}
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Supabase read helpers (fall back to filesystem if unavailable)
# ---------------------------------------------------------------------------

def _sb_read():
    """Get anon client for dashboard reads. Returns None if unavailable."""
    try:
        from src.supabase_client import get_anon_client, supabase_available
        if supabase_available():
            return get_anon_client()
    except Exception:
        pass
    return None


def _list_jobs() -> list[dict]:
    """Return all jobs — from Supabase if available, else filesystem."""
    sb = _sb_read()
    if sb:
        try:
            result = sb.table("gem_jobs").select(
                "job_id, fund_name, deck_filename, state, gatekeeper_score, gatekeeper_class, created_at, updated_at"
            ).order("created_at", desc=True).limit(100).execute()
            jobs = []
            for row in result.data:
                jobs.append({
                    "job_id": row["job_id"],
                    "fund_name": row.get("fund_name") or row.get("deck_filename", "Unknown"),
                    "state": row.get("state", "unknown"),
                    "gatekeeper_score": row.get("gatekeeper_score"),
                    "gatekeeper_class": row.get("gatekeeper_class"),
                    "created_at": _format_ts(row.get("created_at")),
                    "last_updated": _format_ts(row.get("updated_at")),
                })
            return jobs
        except Exception as e:
            print(f"  [supabase] list_jobs fallback to filesystem: {e}")

    # Filesystem fallback
    return _list_jobs_fs()


def _list_jobs_fs() -> list[dict]:
    jobs = []
    if not JOBS_DIR.exists():
        return jobs
    for job_dir in sorted(JOBS_DIR.iterdir(), key=lambda p: p.name, reverse=True):
        manifest_path = job_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = load_manifest(job_dir.name)
            jobs.append({
                "job_id": manifest.job_id,
                "fund_name": manifest.fund_name or manifest.deck_filename,
                "state": manifest.current_state.value,
                "gatekeeper_score": None,
                "gatekeeper_class": None,
                "created_at": manifest.created_at.strftime("%d %b %Y %H:%M UTC"),
                "last_updated": manifest.last_updated.strftime("%d %b %Y %H:%M UTC"),
            })
        except Exception:
            continue
    return jobs


def _get_job_detail(job_id: str) -> Optional[dict]:
    """Return full job detail with artifacts and log."""
    sb = _sb_read()
    if sb:
        try:
            # Job metadata
            job_res = sb.table("gem_jobs").select("*").eq("job_id", job_id).single().execute()
            job_row = job_res.data
            if not job_row:
                return None

            # Artifacts
            art_res = sb.table("gem_artifacts").select("stage_name, data").eq("job_id", job_id).order("created_at").execute()
            artifacts = {row["stage_name"]: row["data"] for row in art_res.data}

            # Log
            log_res = sb.table("gem_status_log").select("*").eq("job_id", job_id).order("created_at").execute()
            log_entries = log_res.data or []

            # GP pipeline info
            gp_info = None
            if job_row.get("gp_id"):
                try:
                    gp_res = sb.table("gp_pipeline").select("*").eq("id", job_row["gp_id"]).single().execute()
                    gp_info = gp_res.data
                except Exception:
                    pass

            return {
                "job_id": job_row["job_id"],
                "fund_name": job_row.get("fund_name") or job_row.get("deck_filename", "Unknown"),
                "deck_filename": job_row.get("deck_filename", ""),
                "state": job_row.get("state", "unknown"),
                "gatekeeper_score": job_row.get("gatekeeper_score"),
                "gatekeeper_class": job_row.get("gatekeeper_class"),
                "created_at": _format_ts(job_row.get("created_at")),
                "last_updated": _format_ts(job_row.get("updated_at")),
                "artifacts": artifacts,
                "log": log_entries,
                "gp_info": gp_info,
            }
        except Exception as e:
            print(f"  [supabase] get_job_detail fallback to filesystem: {e}")

    # Filesystem fallback
    return _get_job_detail_fs(job_id)


def _get_job_detail_fs(job_id: str) -> Optional[dict]:
    try:
        manifest = load_manifest(job_id)
    except Exception:
        return None

    artifacts = {}
    artifact_dir = JOBS_DIR / job_id / "artifacts"
    if artifact_dir.exists():
        for f in sorted(artifact_dir.glob("*.json")):
            try:
                artifacts[f.stem] = json.loads(f.read_text())
            except Exception:
                artifacts[f.stem] = {"error": "Could not parse artifact"}

    log_entries = []
    log_path = JOBS_DIR / job_id / "logs" / "status_log.jsonl"
    if log_path.exists():
        for line in log_path.read_text().strip().splitlines():
            try:
                log_entries.append(json.loads(line))
            except Exception:
                continue

    return {
        "job_id": manifest.job_id,
        "fund_name": manifest.fund_name or manifest.deck_filename,
        "deck_filename": manifest.deck_filename,
        "state": manifest.current_state.value,
        "gatekeeper_score": None,
        "gatekeeper_class": None,
        "created_at": manifest.created_at.strftime("%d %b %Y %H:%M UTC"),
        "last_updated": manifest.last_updated.strftime("%d %b %Y %H:%M UTC"),
        "artifacts": artifacts,
        "log": log_entries,
        "gp_info": None,
    }


def _list_gp_records() -> list[dict]:
    """List all GP records from gp_pipeline table."""
    sb = _sb_read()
    if not sb:
        return []
    try:
        result = sb.table("gp_pipeline").select("*").order("created_at", desc=True).limit(200).execute()
        return result.data or []
    except Exception:
        return []


def _format_ts(ts_str: Optional[str]) -> str:
    """Format an ISO timestamp string for display."""
    if not ts_str:
        return "—"
    try:
        from datetime import datetime
        if "T" in ts_str:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(ts_str)
        return dt.strftime("%d %b %Y %H:%M UTC")
    except Exception:
        return ts_str[:19]


# ---------------------------------------------------------------------------
# Background pipeline runner
# ---------------------------------------------------------------------------

def _run_pipeline_background(job_temp_path: str, original_filename: str, tracking_id: str):
    with _lock:
        _running[tracking_id] = "running"
    try:
        result = run_pipeline(job_temp_path, verbose=False)
        with _lock:
            _running[tracking_id] = result if result else "complete"
    except Exception as e:
        with _lock:
            _running[tracking_id] = f"error: {e}"
    finally:
        try:
            Path(job_temp_path).unlink(missing_ok=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Routes — Pages
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    try:
        jobs = _list_jobs()
        gp_records = _list_gp_records()
        return templates.TemplateResponse("index.html", context={
            "request": request,
            "jobs": jobs,
            "gp_records": gp_records,
        }, request=request)
    except Exception as e:
        import traceback
        return HTMLResponse(f"<pre>{traceback.format_exc()}</pre>", status_code=500)


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_detail(request: Request, job_id: str):
    detail = _get_job_detail(job_id)
    if detail is None:
        return HTMLResponse("<h1>Job not found</h1>", status_code=404)
    return templates.TemplateResponse("job.html", context={"request": request, "job": detail}, request=request)


# ---------------------------------------------------------------------------
# Routes — API
# ---------------------------------------------------------------------------

@app.post("/upload")
async def upload_deck(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        return JSONResponse({"error": "Only PDF files are accepted."}, status_code=400)

    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    import uuid
    tracking_id = uuid.uuid4().hex[:8]

    thread = threading.Thread(
        target=_run_pipeline_background,
        args=(tmp_path, file.filename, tracking_id),
        daemon=True,
    )
    thread.start()

    return JSONResponse({"tracking_id": tracking_id, "status": "running"})


@app.get("/api/jobs")
async def api_jobs():
    return JSONResponse(_list_jobs())


@app.get("/api/jobs/{job_id}")
async def api_job(job_id: str):
    detail = _get_job_detail(job_id)
    if detail is None:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return JSONResponse(detail)


@app.get("/api/gp-records")
async def api_gp_records():
    return JSONResponse(_list_gp_records())


@app.get("/api/tracking/{tracking_id}")
async def api_tracking(tracking_id: str):
    with _lock:
        status = _running.get(tracking_id, "unknown")
    jobs = _list_jobs()
    latest = jobs[0] if jobs else None
    return JSONResponse({
        "tracking_id": tracking_id,
        "status": status,
        "latest_job": latest,
    })


# ---------------------------------------------------------------------------
# Supabase write helper
# ---------------------------------------------------------------------------

def _sb_write():
    """Get service-role client for writes."""
    try:
        from src.supabase_client import get_service_client, supabase_available
        if supabase_available():
            return get_service_client()
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Routes — GP Management
# ---------------------------------------------------------------------------

@app.get("/gp/new", response_class=HTMLResponse)
async def gp_new_form(request: Request):
    try:
        return templates.TemplateResponse("gp_form.html", context={"request": request, "gp": None, "mode": "create"}, request=request)
    except Exception as e:
        import traceback
        return HTMLResponse(f"<pre>{traceback.format_exc()}</pre>", status_code=500)


@app.get("/gp/{gp_id}/edit", response_class=HTMLResponse)
async def gp_edit_form(request: Request, gp_id: str):
    sb = _sb_read()
    if not sb:
        return HTMLResponse("<h1>Supabase unavailable</h1>", status_code=500)
    try:
        result = sb.table("gp_pipeline").select("*").eq("id", gp_id).single().execute()
        gp = result.data
    except Exception:
        return HTMLResponse("<h1>GP record not found</h1>", status_code=404)
    return templates.TemplateResponse("gp_form.html", context={"request": request, "gp": gp, "mode": "edit"}, request=request)


@app.get("/gp/{gp_id}", response_class=HTMLResponse)
async def gp_detail(request: Request, gp_id: str):
    sb = _sb_read()
    if not sb:
        return HTMLResponse("<h1>Supabase unavailable</h1>", status_code=500)
    try:
        gp_res = sb.table("gp_pipeline").select("*").eq("id", gp_id).single().execute()
        gp = gp_res.data
    except Exception:
        return HTMLResponse("<h1>GP record not found</h1>", status_code=404)

    # Get associated pipeline jobs
    jobs = []
    try:
        jobs_res = sb.table("gem_jobs").select("*").eq("gp_id", gp_id).order("created_at", desc=True).execute()
        jobs = jobs_res.data or []
    except Exception:
        pass

    return templates.TemplateResponse("gp_detail.html", context={"request": request, "gp": gp, "jobs": jobs}, request=request)


@app.post("/gp/save")
async def gp_save(
    request: Request,
    gp_id: str = Form(None),
    gp_name: str = Form(...),
    contact_first_name: str = Form(""),
    contact_last_name: str = Form(""),
    contact_email: str = Form(""),
    contact_phone: str = Form(""),
    account_owner: str = Form("Randy Mitchell"),
    start_date: str = Form(""),
    sub_price_usd: str = Form(""),
    fund_ii_net_irr: str = Form(""),
    payment_status: str = Form("Pending"),
    travel_city: list = Form([]),
    travel_start: list = Form([]),
    travel_end: list = Form([]),
):
    sb = _sb_write()
    if not sb:
        return HTMLResponse("<h1>Supabase unavailable</h1>", status_code=500)

    # Build travel_dates JSON from parallel arrays
    travel_dates = []
    for city, start, end in zip(travel_city, travel_start, travel_end):
        if city.strip():
            travel_dates.append({
                "city": city.strip(),
                "start_date": start.strip() or None,
                "end_date": end.strip() or None,
            })

    data = {
        "gp_name": gp_name.strip(),
        "contact_first_name": contact_first_name.strip() or None,
        "contact_last_name": contact_last_name.strip() or None,
        "contact_email": contact_email.strip() or None,
        "contact_phone": contact_phone.strip() or None,
        "account_owner": account_owner.strip() or "Randy Mitchell",
        "start_date": start_date.strip() or None,
        "sub_price_usd": float(sub_price_usd) if sub_price_usd.strip() else None,
        "fund_ii_net_irr": float(fund_ii_net_irr) if fund_ii_net_irr.strip() else None,
        "payment_status": payment_status,
        "travel_dates": travel_dates if travel_dates else [],
    }

    try:
        if gp_id and gp_id.strip():
            # Update existing
            sb.table("gp_pipeline").update(data).eq("id", gp_id.strip()).execute()
            return RedirectResponse(f"/gp/{gp_id.strip()}", status_code=303)
        else:
            # Create new
            result = sb.table("gp_pipeline").insert(data).execute()
            new_id = result.data[0]["id"] if result.data else None
            if new_id:
                return RedirectResponse(f"/gp/{new_id}", status_code=303)
            return RedirectResponse("/", status_code=303)
    except Exception as e:
        return HTMLResponse(f"<h1>Save failed</h1><p>{e}</p>", status_code=500)


@app.post("/gp/{gp_id}/run-pipeline")
async def gp_run_pipeline(gp_id: str, file: UploadFile = File(...)):
    """Upload a deck and run the pipeline, linked to a GP record."""
    if not file.filename.lower().endswith(".pdf"):
        return JSONResponse({"error": "Only PDF files are accepted."}, status_code=400)

    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    import uuid
    tracking_id = uuid.uuid4().hex[:8]

    def _run_linked(temp_path, gp_id, tracking_id):
        with _lock:
            _running[tracking_id] = "running"
        try:
            result = run_pipeline(temp_path, verbose=False)
            # Link the new job to the GP record
            sb = _sb_write()
            if sb:
                try:
                    jobs = sb.table("gem_jobs").select("job_id").order("created_at", desc=True).limit(1).execute()
                    if jobs.data:
                        sb.table("gem_jobs").update({"gp_id": gp_id}).eq("job_id", jobs.data[0]["job_id"]).execute()
                except Exception:
                    pass
            with _lock:
                _running[tracking_id] = result if result else "complete"
        except Exception as e:
            with _lock:
                _running[tracking_id] = f"error: {e}"
        finally:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception:
                pass

    thread = threading.Thread(target=_run_linked, args=(tmp_path, gp_id, tracking_id), daemon=True)
    thread.start()

    return JSONResponse({"tracking_id": tracking_id, "status": "running", "gp_id": gp_id})
