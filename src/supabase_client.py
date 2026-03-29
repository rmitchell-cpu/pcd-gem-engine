"""Supabase client singleton for the GEM Engine.

Provides both a service-role client (for writes from the pipeline)
and an anon client (for dashboard reads respecting RLS).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from supabase import Client, create_client

from config.settings import ENGINE_ROOT

_service_client: Optional[Client] = None
_anon_client: Optional[Client] = None


def _load_env():
    """Load .env from engine root if python-dotenv is available."""
    try:
        from dotenv import load_dotenv
        env_path = ENGINE_ROOT / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=True)
    except ImportError:
        pass


def get_service_client() -> Client:
    """Return a Supabase client using the service_role key (bypasses RLS).

    Use this for pipeline writes — inserting jobs, artifacts, and logs.
    """
    global _service_client
    if _service_client is None:
        _load_env()
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.\n"
                "  Add them to pcd-gem-engine/.env or export in your shell."
            )
        _service_client = create_client(url, key)
    return _service_client


def get_anon_client() -> Client:
    """Return a Supabase client using the anon key (respects RLS).

    Use this for dashboard reads.
    """
    global _anon_client
    if _anon_client is None:
        _load_env()
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_ANON_KEY")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_ANON_KEY must be set.\n"
                "  Add them to pcd-gem-engine/.env or export in your shell."
            )
        _anon_client = create_client(url, key)
    return _anon_client


def supabase_available() -> bool:
    """Check if Supabase credentials are configured."""
    _load_env()
    return bool(
        os.environ.get("SUPABASE_URL")
        and os.environ.get("SUPABASE_SERVICE_KEY")
    )
