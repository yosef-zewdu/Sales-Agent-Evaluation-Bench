#!/usr/bin/env python3
"""
Bridge script: runs Conversion-Engine's three-stage chain on benchmark tasks that have
placeholder candidate_outputs, populating them with real agent-generated emails.

The chain uses the LLM fallback if langchain_core is not installed — this still produces
a valid (though generic) baseline email, which is exactly what we need as the "rejected"
side of preference pairs (scores 0.0: missing CTA, no signal refs, generic phrasing).

Usage:
    python generation_scripts/bridge_agent_run.py
    # Then: cp tenacious_bench_v0.1/train/tasks_populated.jsonl tenacious_bench_v0.1/train/tasks.jsonl
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add Conversion-Engine to path
ENGINE_PATH = "/home/yosef/Desktop/intensive/Conversion-Engine"
sys.path.insert(0, ENGINE_PATH)

from dotenv import load_dotenv
load_dotenv(Path(ENGINE_PATH) / ".env")

try:
    from tqdm import tqdm
    _TQDM = True
except ImportError:
    _TQDM = False

from config.models import Prospect, ProspectState
from signal_pipeline.models import HiringSignalBrief
from mechanism.three_stage_chain import compose_outbound_chain

BENCH_FILE  = Path("tenacious_bench_v0.1/train/tasks.jsonl")
OUTPUT_FILE = Path("tenacious_bench_v0.1/train/tasks_populated.jsonl")
PLACEHOLDER = "[TO BE GENERATED OR PULLED FROM AGENT RUN]"

# Map bench task segment labels to valid HiringSignalBrief icp_segment values
SEGMENT_MAP = {
    "engineering": "segment_2",
    "product":     "segment_2",
    "data":        "segment_3",
    "design":      "segment_2",
    "S1":          "segment_1",
    "S2":          "segment_2",
    "S3":          "segment_3",
    "S4":          "segment_4",
    "unqualified": "unqualified",
}


def _build_brief(task: dict) -> HiringSignalBrief:
    """
    Construct a HiringSignalBrief from the task's prospect_metadata.
    The hiring_signal_brief field in the task is a human-readable string (not JSON),
    so we extract structured fields from prospect_metadata instead.
    """
    meta    = task["input"].get("prospect_metadata", {})
    icp_seg = SEGMENT_MAP.get(str(meta.get("segment", "")), "segment_2")

    return HiringSignalBrief(
        schema_version="1.0",
        company_id=str(meta.get("company", task["task_id"])),
        company_name=str(meta.get("company", "Unknown Company")),
        last_enriched_at=datetime.now(timezone.utc).isoformat(),
        icp_segment=icp_seg,
        icp_confidence=float(meta.get("signal_confidence", 0.5)),
        job_post_count=int(meta["job_post_count"]) if meta.get("job_post_count") else None,
        ai_maturity_score=min(int(meta["ai_maturity_score"]), 3) if meta.get("ai_maturity_score") else None,
    )


def _build_prospect(task: dict) -> Prospect:
    meta = task["input"].get("prospect_metadata", {})
    return Prospect(
        prospect_id=task["task_id"],
        company_id=str(meta.get("company", task["task_id"])),
        contact_name="Alex Smith",
        email="prospect@example.com",
        phone=None,
        timezone="UTC",
        preferred_channel="email",
        current_state=ProspectState.COLD,
        outbound_attempt_count=0,
    )


def run_agent_on_task(task: dict) -> str:
    """Run the three-stage chain on a task and return the email body."""
    brief    = _build_brief(task)
    prospect = _build_prospect(task)
    result   = compose_outbound_chain(
        prospect=prospect,
        brief=brief,
        gap_brief=None,
        channel="email",
    )
    return result.content


def main():
    if not BENCH_FILE.exists():
        print(f"Error: {BENCH_FILE} not found.")
        sys.exit(1)

    tasks = [json.loads(l) for l in BENCH_FILE.read_text().splitlines() if l.strip()]
    placeholder_count = sum(1 for t in tasks if PLACEHOLDER in t.get("candidate_output", ""))
    print(f"Total tasks: {len(tasks)}")
    print(f"Placeholder tasks to populate: {placeholder_count}")

    success = 0
    failed  = 0
    skipped = 0

    iterator = tqdm(tasks, desc="Running agent") if _TQDM else tasks
    for task in iterator:
        if PLACEHOLDER not in task.get("candidate_output", ""):
            skipped += 1
            continue
        try:
            task["candidate_output"] = run_agent_on_task(task)
            success += 1
        except Exception as e:
            print(f"  [ERROR] {task['task_id']}: {e}")
            failed += 1

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text("\n".join(json.dumps(t) for t in tasks) + "\n")

    print(f"\nDone: {success} populated, {failed} failed, {skipped} skipped (already had output)")
    print(f"Output: {OUTPUT_FILE}")
    print(f"\nNext step:")
    print(f"  cp {OUTPUT_FILE} {BENCH_FILE}")
    print(f"  python training_data/prepare_training_data.py")


if __name__ == "__main__":
    main()
