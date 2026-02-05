"""Parse markdown body into structured walkthrough data for the frontend.

Converts a flat markdown document with ## and ### headers into the
structured format expected by the WalkthroughPanel component:

    {
        "title": "...",
        "phases": [
            {
                "id": "phase-1",
                "name": "Phase Name",
                "steps": [
                    {"id": "phase-1-step-1", "title": "Step", "content": "..."}
                ]
            }
        ]
    }
"""

import re
from typing import Optional


def parse_markdown_to_walkthrough(title: str, body_markdown: str) -> dict:
    """Parse markdown into structured walkthrough phases and steps.

    Splits on ``## `` headers for phases, ``### `` headers for steps within
    each phase.  If a phase has no ``### `` sub-headers the entire phase body
    becomes a single step.
    """
    lines = body_markdown.split("\n")

    phases: list[dict] = []
    current_phase: Optional[dict] = None
    current_step: Optional[dict] = None
    preamble_lines: list[str] = []
    phase_counter = 0
    step_counter = 0

    def _flush_step():
        nonlocal current_step
        if current_step is not None:
            current_step["content"] = "\n".join(current_step["_lines"]).strip()
            del current_step["_lines"]
            if current_phase is not None:
                current_phase["steps"].append(current_step)
            current_step = None

    def _flush_phase():
        nonlocal current_phase
        _flush_step()
        if current_phase is not None:
            # If phase has no steps, create one from any accumulated content
            if not current_phase["steps"] and current_phase.get("_body"):
                current_phase["steps"].append({
                    "id": f"{current_phase['id']}-step-1",
                    "title": current_phase["name"],
                    "content": "\n".join(current_phase["_body"]).strip(),
                })
            current_phase.pop("_body", None)
            if current_phase["steps"]:
                phases.append(current_phase)
            current_phase = None

    for line in lines:
        # Detect ## phase header
        if re.match(r"^## ", line):
            _flush_phase()
            phase_counter += 1
            step_counter = 0
            phase_name = line[3:].strip()
            phase_id = f"phase-{phase_counter}"
            current_phase = {
                "id": phase_id,
                "name": phase_name,
                "steps": [],
                "_body": [],
            }
            continue

        # Detect ### step header (only within a phase)
        if re.match(r"^### ", line) and current_phase is not None:
            _flush_step()
            step_counter += 1
            step_title = line[4:].strip()
            step_id = f"{current_phase['id']}-step-{step_counter}"
            current_step = {
                "id": step_id,
                "title": step_title,
                "_lines": [],
            }
            continue

        # Accumulate content
        if current_step is not None:
            current_step["_lines"].append(line)
        elif current_phase is not None:
            current_phase["_body"].append(line)
        else:
            preamble_lines.append(line)

    # Flush remaining
    _flush_phase()

    # If there's preamble content before the first ## header, prepend as phase
    preamble = "\n".join(preamble_lines).strip()
    if preamble and phases:
        # Insert preamble as the intro content of the first phase's first step
        # or as a separate "Introduction" phase
        phases.insert(0, {
            "id": "phase-0",
            "name": "Introduction",
            "steps": [{
                "id": "phase-0-step-1",
                "title": "Introduction",
                "content": preamble,
            }],
        })
    elif preamble and not phases:
        # No ## headers at all — single phase with full content
        phases.append({
            "id": "phase-1",
            "name": title,
            "steps": [{
                "id": "phase-1-step-1",
                "title": title,
                "content": body_markdown.strip(),
            }],
        })

    return {
        "title": title,
        "phases": phases,
    }
