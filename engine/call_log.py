import json
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "model_calls.jsonl"


def log_call(**fields):
    LOG_PATH.parent.mkdir(exist_ok=True)
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), **fields}
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(record) + "\n")
