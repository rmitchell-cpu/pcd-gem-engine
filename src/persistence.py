"""Job lifecycle, artifact persistence, and status logging.

Dual-write architecture:
  - Filesystem: always written (local cache, fast reads during pipeline run)
  - Supabase:   written if credentials are configured (central truth)
"""

from __future__ import annotations

import json
import shutil
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Type

from pydantic import BaseModel

from config.settings import JOBS_DIR
from src.models import JobManifest, StatusLogEntry, WorkflowState


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Supabase helpers (fail-safe — never crashes the pipeline)
# ---------------------------------------------------------------------------

def _sb():
    """Return the Supabase service client, or None if unavailable."""
    try:
        from src.supabase_client import get_service_client, supabase_available
        if supabase_available():
            return get_service_client()
    except Exception:
        pass
    return None


def _sb_upsert_job(job_id: str, data: dict):
    """Upsert a row in gem_jobs. Silent on failure."""
    try:
        client = _sb()
        if client is None:
            return
        data["job_id"] = job_id
        data["updated_at"] = datetime.utcnow().isoformat()
        client.table("gem_jobs").upsert(data, on_conflict="job_id").execute()
    except Exception as e:
        print(f"  [supabase] gem_jobs upsert warning: {e}")


def _sb_insert_artifact(job_id: str, stage_name: str, artifact_data: dict):
    """Insert or update an artifact row. Silent on failure."""
    try:
        client = _sb()
        if client is None:
            return
        client.table("gem_artifacts").upsert(
            {
                "job_id": job_id,
                "stage_name": stage_name,
                "data": artifact_data,
                "created_at": datetime.utcnow().isoformat(),
            },
            on_conflict="job_id,stage_name",
        ).execute()
    except Exception as e:
        print(f"  [supabase] gem_artifacts upsert warning: {e}")


def _sb_insert_log(job_id: str, entry_dict: dict):
    """Insert a status log row. Silent on failure."""
    try:
        client = _sb()
        if client is None:
            return
        row = {
            "job_id": job_id,
            "stage_name": entry_dict.get("stage_name"),
            "from_state": entry_dict.get("from_state"),
            "to_state": entry_dict.get("to_state"),
            "result": entry_dict.get("result"),
            "notes": entry_dict.get("notes"),
            "model_version": entry_dict.get("model_version"),
            "prompt_version": entry_dict.get("prompt_version"),
            "token_usage": entry_dict.get("token_usage"),
        }
        client.table("gem_status_log").insert(row).execute()
    except Exception as e:
        print(f"  [supabase] gem_status_log insert warning: {e}")


def _sb_upload_deck(job_id: str, deck_path: str):
    """Upload the deck PDF to the gp_decks storage bucket. Silent on failure."""
    try:
        client = _sb()
        if client is None:
            return None
        src = Path(deck_path)
        storage_path = f"{job_id}/{src.name}"
        with open(src, "rb") as f:
            client.storage.from_("gp_decks").upload(
                storage_path,
                f,
                file_options={"content-type": "application/pdf", "upsert": "true"},
            )
        return storage_path
    except Exception as e:
        print(f"  [supabase] deck upload warning: {e}")
        return None


def _sb_update_gp_pipeline(job_id: str, fund_name: str, score: Optional[int], classification: Optional[str], state: str):
    """Upsert the denormalized gp_pipeline central record. Silent on failure."""
    try:
        client = _sb()
        if client is None:
            return
        # Find or create a gp_pipeline row for this fund
        result = client.table("gp_pipeline").select("id").eq("gp_name", fund_name).limit(1).execute()
        gp_data = {
            "gp_name": fund_name,
            "gatekeeper_score": score,
            "gatekeeper_class": classification,
            "pipeline_state": state,
            "latest_job_id": job_id,
        }
        if result.data:
            gp_id = result.data[0]["id"]
            client.table("gp_pipeline").update(gp_data).eq("id", gp_id).execute()
        else:
            resp = client.table("gp_pipeline").insert(gp_data).execute()
            gp_id = resp.data[0]["id"] if resp.data else None

        # Link gem_jobs row to gp_pipeline
        if gp_id:
            client.table("gem_jobs").update({"gp_id": gp_id}).eq("job_id", job_id).execute()
    except Exception as e:
        print(f"  [supabase] gp_pipeline upsert warning: {e}")


# ---------------------------------------------------------------------------
# Job creation
# ---------------------------------------------------------------------------

def create_job(deck_path: str) -> JobManifest:
    """Create a new pipeline job, copy the deck, and return the manifest."""
    job_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    job_dir = JOBS_DIR / job_id

    _ensure_dir(job_dir / "artifacts")
    _ensure_dir(job_dir / "logs")
    _ensure_dir(job_dir / "deck")

    # Copy the source deck into the job directory
    src = Path(deck_path)
    dst = job_dir / "deck" / src.name
    shutil.copy2(src, dst)

    now = datetime.utcnow()
    manifest = JobManifest(
        job_id=job_id,
        deck_filename=src.name,
        deck_path=str(dst),
        created_at=now,
        current_state=WorkflowState.UPLOADED,
        last_updated=now,
    )
    _write_manifest(job_dir, manifest)

    # --- Supabase: create gem_jobs row + upload deck ---
    _sb_upsert_job(job_id, {
        "fund_name": None,
        "deck_filename": src.name,
        "state": WorkflowState.UPLOADED.value,
        "created_at": now.isoformat(),
    })
    storage_path = _sb_upload_deck(job_id, deck_path)
    if storage_path:
        _sb_upsert_job(job_id, {"deck_storage_path": storage_path})

    log_transition(
        job_id,
        stage_name="intake",
        from_state=WorkflowState.UPLOADED,
        to_state=WorkflowState.UPLOADED,
        result="success",
        notes=f"Deck ingested: {src.name}",
    )
    return manifest


# ---------------------------------------------------------------------------
# Manifest read / write
# ---------------------------------------------------------------------------

def _write_manifest(job_dir: Path, manifest: JobManifest) -> None:
    path = job_dir / "manifest.json"
    path.write_text(manifest.model_dump_json(indent=2))


def load_manifest(job_id: str) -> JobManifest:
    path = JOBS_DIR / job_id / "manifest.json"
    return JobManifest.model_validate_json(path.read_text())


def update_state(job_id: str, new_state: WorkflowState, fund_name: Optional[str] = None) -> JobManifest:
    manifest = load_manifest(job_id)
    manifest.current_state = new_state
    manifest.last_updated = datetime.utcnow()
    if fund_name:
        manifest.fund_name = fund_name
    _write_manifest(JOBS_DIR / job_id, manifest)

    # --- Supabase: update state ---
    sb_data: dict = {"state": new_state.value}
    if fund_name:
        sb_data["fund_name"] = fund_name
    _sb_upsert_job(job_id, sb_data)

    return manifest


# ---------------------------------------------------------------------------
# Status log (append-only JSONL + Supabase)
# ---------------------------------------------------------------------------

def log_transition(
    job_id: str,
    stage_name: str,
    from_state: WorkflowState,
    to_state: WorkflowState,
    result: str,
    notes: Optional[str] = None,
    model_version: Optional[str] = None,
    prompt_version: Optional[str] = None,
    token_usage: Optional[dict] = None,
) -> None:
    entry = StatusLogEntry(
        timestamp=datetime.utcnow(),
        from_state=from_state,
        to_state=to_state,
        stage_name=stage_name,
        result=result,
        notes=notes,
        model_version=model_version,
        prompt_version=prompt_version,
        token_usage=token_usage,
    )

    # Filesystem
    log_path = JOBS_DIR / job_id / "logs" / "status_log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as f:
        f.write(entry.model_dump_json() + "\n")

    # Supabase
    _sb_insert_log(job_id, entry.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# Artifact persistence
# ---------------------------------------------------------------------------

def save_artifact(job_id: str, stage_name: str, data: BaseModel) -> str:
    """Persist a stage artifact as JSON. Returns the relative path."""
    # Filesystem
    artifact_dir = JOBS_DIR / job_id / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{stage_name}.json"
    path = artifact_dir / filename
    path.write_text(data.model_dump_json(indent=2))

    # Supabase
    _sb_insert_artifact(job_id, stage_name, data.model_dump(mode="json"))

    return f"artifacts/{filename}"


def load_artifact(job_id: str, stage_name: str, model_class: Type[BaseModel]) -> BaseModel:
    """Load a previously persisted stage artifact."""
    path = JOBS_DIR / job_id / "artifacts" / f"{stage_name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Artifact not found: {path}")
    return model_class.model_validate_json(path.read_text())


def artifact_exists(job_id: str, stage_name: str) -> bool:
    return (JOBS_DIR / job_id / "artifacts" / f"{stage_name}.json").exists()


# ---------------------------------------------------------------------------
# Parsed text persistence (ingestion output)
# ---------------------------------------------------------------------------

def save_parsed_text(job_id: str, text: str, page_texts: Optional[list[str]] = None) -> str:
    """Save the parsed deck text. Returns relative path."""
    artifact_dir = JOBS_DIR / job_id / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    parsed = {
        "full_text": text,
        "page_texts": page_texts or [],
        "page_count": len(page_texts) if page_texts else 0,
    }
    path = artifact_dir / "parsed_deck.json"
    path.write_text(json.dumps(parsed, indent=2))
    return "artifacts/parsed_deck.json"


def load_parsed_text(job_id: str) -> dict:
    path = JOBS_DIR / job_id / "artifacts" / "parsed_deck.json"
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------
# Review bundle
# ---------------------------------------------------------------------------

def save_bundle(job_id: str, bundle: BaseModel) -> str:
    """Save the final review bundle manifest."""
    path = JOBS_DIR / job_id / "review_bundle.json"
    path.write_text(bundle.model_dump_json(indent=2))
    return str(path)


def list_jobs() -> list[JobManifest]:
    """List all jobs sorted by creation time (newest first)."""
    manifests = []
    if not JOBS_DIR.exists():
        return manifests
    for job_dir in sorted(JOBS_DIR.iterdir(), reverse=True):
        manifest_path = job_dir / "manifest.json"
        if manifest_path.exists():
            manifests.append(JobManifest.model_validate_json(manifest_path.read_text()))
    return manifests
