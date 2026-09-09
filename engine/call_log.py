import json
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "model_calls.jsonl"


def log_call(also_log_to=None, **fields):
    """Appends one record to the shared logs/model_calls.jsonl, and
    optionally also to a second, dedicated file (also_log_to) — added
    2026-09-09, by request, for the norm-implementer/norm-evaluator's own
    logs/norm_implementer.jsonl / logs/norm_evaluator.jsonl (see
    engine/simulate.py's run_norm_implementer()/run_norm_evaluator()),
    which carry an extra tool_call_trace field the shared log doesn't.
    Kept as an *additional* write, not a replacement, so
    engine/monitoring.py's existing plots (which filter the shared log by
    call=="norm_implementer"/"norm_evaluator") keep working unchanged."""
    LOG_PATH.parent.mkdir(exist_ok=True)
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), **fields}
    line = json.dumps(record) + "\n"
    with LOG_PATH.open("a") as f:
        f.write(line)
    if also_log_to is not None:
        also_log_to.parent.mkdir(exist_ok=True)
        with also_log_to.open("a") as f:
            f.write(line)
