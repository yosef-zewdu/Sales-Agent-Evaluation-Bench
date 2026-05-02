#!/usr/bin/env python3
"""
Shared observability layer for all generation scripts.

Every OpenRouter call goes through `traced_completion()`, which:
  1. Executes the chat completion
  2. Logs a Langfuse generation span with exact token counts and cost
  3. Appends an exact row to cost_log.csv

Usage:
    from observability import traced_completion, flush_langfuse
    resp = traced_completion(client, model, messages, max_tokens, run_name, purpose)
    flush_langfuse()  # call once at end of script
"""

import csv
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from langfuse import Langfuse

COST_LOG_PATH = Path(__file__).parent.parent / "cost_log.csv"
COST_LOG_COLUMNS = ["timestamp", "bucket", "model_or_service", "purpose", "tokens_or_units", "cost_usd"]

_langfuse = Langfuse(
    secret_key=os.environ.get("LANGFUSE_SECRET_KEY", ""),
    public_key=os.environ.get("LANGFUSE_PUBLIC_KEY", ""),
    host=os.environ.get("LANGFUSE_BASE_URL", "https://cloud.langfuse.com"),
    flush_interval=60,   # batch every 60s — don't block per-call
    flush_at=50,         # batch at 50 events
    timeout=5,           # 5s per upload attempt, not indefinite
)


def _append_cost_log(bucket: str, model: str, purpose: str, tokens: int, cost_usd: float) -> None:
    write_header = not COST_LOG_PATH.exists() or COST_LOG_PATH.stat().st_size == 0
    with open(COST_LOG_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COST_LOG_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow({
            "timestamp":        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "bucket":           bucket,
            "model_or_service": model,
            "purpose":          purpose,
            "tokens_or_units":  tokens,
            "cost_usd":         f"{cost_usd:.6f}",
        })


def traced_completion(
    client,
    model: str,
    messages: list[dict],
    max_tokens: int,
    run_name: str,
    purpose: str,
    bucket: str = "dataset_authoring",
    trace_id: str | None = None,
) -> object:
    """
    Wraps client.chat.completions.create() with Langfuse tracing and exact cost logging.
    Returns the raw completion response.
    """
    observation = _langfuse.start_observation(
        name=run_name,
        as_type="generation",
        model=model,
        metadata={"purpose": purpose, "bucket": bucket},
        input=messages,
    )

    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
    )

    usage = resp.usage
    prompt_tokens    = usage.prompt_tokens
    completion_tokens = usage.completion_tokens
    total_tokens     = usage.total_tokens

    # OpenRouter returns exact cost in usage attributes
    exact_cost = getattr(usage, "cost", None)
    if exact_cost is None:
        cd = getattr(usage, "cost_details", {}) or {}
        exact_cost = cd.get("upstream_inference_cost", 0.0)
    if exact_cost is None:
        exact_cost = 0.0

    observation.update(
        output=resp.choices[0].message.content,
        usage_details={
            "input":  prompt_tokens,
            "output": completion_tokens,
            "total":  total_tokens,
        },
        cost_details={"total": exact_cost},
        metadata={"exact_cost_usd": exact_cost, "response_id": resp.id},
    )
    observation.end()

    _append_cost_log(
        bucket=bucket,
        model=model,
        purpose=purpose,
        tokens=total_tokens,
        cost_usd=exact_cost,
    )

    return resp


def flush_langfuse() -> None:
    """Best-effort Langfuse flush. Costs are already in cost_log.csv regardless."""
    try:
        _langfuse.flush()
    except Exception:
        pass
