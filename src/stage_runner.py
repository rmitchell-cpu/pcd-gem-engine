"""Base stage execution engine.

Every GEM stage follows the same protocol:
1. Load prompt from prompts/<stage>.md
2. Inject upstream artifacts as structured context
3. Call Claude API
4. Parse JSON from response
5. Validate output against Pydantic schema
6. Persist artifact
7. Log execution metadata
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic
from pydantic import BaseModel, ValidationError

from config.settings import (
    ENGINE_ROOT,
    MAX_STAGE_RETRIES,
    MAX_TOKENS,
    MODEL,
    PROMPTS_DIR,
    TEMPERATURE,
)
from src.models import StageResult
from src.persistence import log_transition, save_artifact
from src.validator import STAGE_SCHEMA_MAP, validate_stage_output, validation_error_summary


_client: Optional[anthropic.Anthropic] = None


def _load_env():
    """Load .env file from engine root if it exists."""
    try:
        from dotenv import load_dotenv
        env_path = ENGINE_ROOT / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=True)
    except ImportError:
        pass  # python-dotenv not installed; rely on environment


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _load_env()
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. Either:\n"
                "  1. Create pcd-gem-engine/.env with ANTHROPIC_API_KEY=sk-ant-...\n"
                "  2. Or: export ANTHROPIC_API_KEY=sk-ant-... in your shell"
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def load_prompt(stage_name: str) -> str:
    """Load the prompt template for a stage."""
    path = PROMPTS_DIR / f"{stage_name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text()


def prompt_hash(text: str) -> str:
    """SHA-256 hash of prompt content for versioning."""
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response text.

    Handles responses that wrap JSON in ```json ... ``` fences
    or return raw JSON.
    """
    # Try to find JSON in code fences first
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # Try to find the first { ... } block
    brace_start = text.find("{")
    if brace_start == -1:
        raise ValueError("No JSON object found in response")

    # Find the matching closing brace
    depth = 0
    for i in range(brace_start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                json_str = text[brace_start : i + 1]
                return json.loads(json_str)

    raise ValueError("Incomplete JSON object in response")


def run_stage(
    stage_name: str,
    job_id: str,
    context: dict[str, str],
    system_suffix: str = "",
) -> StageResult:
    """Execute a single pipeline stage.

    Args:
        stage_name: The stage identifier (e.g. "gem1_gatekeeper").
        job_id: The job being processed.
        context: A dict of context items to inject. Keys are labels,
                 values are the text/JSON content. Common keys:
                 "deck_text", "gatekeeper_report", "analyst_extraction", etc.
        system_suffix: Optional additional system instructions.

    Returns:
        StageResult with the outcome.
    """
    prompt_text = load_prompt(stage_name)
    p_hash = prompt_hash(prompt_text)

    # Build the user message: prompt + context injections
    user_parts = []
    for label, content in context.items():
        user_parts.append(f"<{label}>\n{content}\n</{label}>")

    user_message = "\n\n".join(user_parts)

    # System message = prompt template + any suffix
    system_message = prompt_text
    if system_suffix:
        system_message += "\n\n" + system_suffix

    # Determine if this stage should output JSON
    needs_json = stage_name in STAGE_SCHEMA_MAP

    if needs_json:
        system_message += (
            "\n\n--- OUTPUT INSTRUCTION ---\n"
            "You MUST respond with a single valid JSON object matching the required schema. "
            "Do not include any text before or after the JSON. "
            "Do not wrap the JSON in markdown code fences."
        )

    client = _get_client()
    last_error = None

    for attempt in range(MAX_STAGE_RETRIES + 1):
        try:
            retry_note = ""
            if attempt > 0 and last_error:
                retry_note = (
                    f"\n\n--- RETRY NOTE (attempt {attempt + 1}) ---\n"
                    f"Your previous response failed validation:\n{last_error}\n"
                    "Please fix these issues and respond with corrected JSON only."
                )

            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                system=system_message,
                messages=[
                    {"role": "user", "content": user_message + retry_note},
                ],
            )

            raw_text = response.content[0].text
            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }

            if needs_json:
                raw_json = _extract_json(raw_text)
                validated = validate_stage_output(stage_name, raw_json)
                artifact_path = save_artifact(job_id, stage_name, validated)
            else:
                # For non-schema stages, save raw text
                artifact_dir = Path(f"jobs/{job_id}/artifacts")
                artifact_dir.mkdir(parents=True, exist_ok=True)
                artifact_path = f"artifacts/{stage_name}.txt"
                (artifact_dir.parent.parent / artifact_path.replace("artifacts/", f"jobs/{job_id}/artifacts/")).write_text(raw_text)

            return StageResult(
                stage_name=stage_name,
                success=True,
                artifact_path=artifact_path,
                model_version=MODEL,
                prompt_hash=p_hash,
                timestamp=datetime.utcnow(),
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                retry_count=attempt,
            )

        except ValidationError as e:
            last_error = validation_error_summary(e)
            if attempt == MAX_STAGE_RETRIES:
                return StageResult(
                    stage_name=stage_name,
                    success=False,
                    error=f"Schema validation failed after {MAX_STAGE_RETRIES + 1} attempts: {last_error}",
                    model_version=MODEL,
                    prompt_hash=p_hash,
                    timestamp=datetime.utcnow(),
                    retry_count=attempt,
                )

        except (json.JSONDecodeError, ValueError) as e:
            last_error = f"JSON parse error: {str(e)}"
            if attempt == MAX_STAGE_RETRIES:
                return StageResult(
                    stage_name=stage_name,
                    success=False,
                    error=f"JSON extraction failed after {MAX_STAGE_RETRIES + 1} attempts: {last_error}",
                    model_version=MODEL,
                    prompt_hash=p_hash,
                    timestamp=datetime.utcnow(),
                    retry_count=attempt,
                )

        except anthropic.RateLimitError as e:
            # Rate limited — wait and retry (up to 3 times)
            import time
            rate_retries = getattr(run_stage, '_rate_retries', 0)
            if rate_retries < 3:
                run_stage._rate_retries = rate_retries + 1
                wait = 30 * (rate_retries + 1)  # 30s, 60s, 90s
                print(f"  [rate-limit] Waiting {wait}s before retry ({rate_retries + 1}/3)...")
                time.sleep(wait)
                continue  # Retry the same attempt
            return StageResult(
                stage_name=stage_name,
                success=False,
                error=f"Rate limit exceeded after retries: {str(e)}",
                model_version=MODEL,
                prompt_hash=p_hash,
                timestamp=datetime.utcnow(),
                retry_count=attempt,
            )

        except anthropic.APIError as e:
            return StageResult(
                stage_name=stage_name,
                success=False,
                error=f"API error: {str(e)}",
                model_version=MODEL,
                prompt_hash=p_hash,
                timestamp=datetime.utcnow(),
                retry_count=attempt,
            )

    # Should not reach here, but safety net
    return StageResult(
        stage_name=stage_name,
        success=False,
        error="Unexpected: exhausted retries",
        model_version=MODEL,
        prompt_hash=p_hash,
        timestamp=datetime.utcnow(),
    )
