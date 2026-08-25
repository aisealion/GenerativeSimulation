#!/usr/bin/env python3
"""One-time roster generator — run manually, never called by engine/simulate.py.

Assigns personalities the same way Gupta et al.'s CPRModel does
(ostrom3/Model.py on origin/hiromu/llm-norm in the Gupta/CPRG_fishing
repo): agent i is altruistic iff i < agent_count * altruism_ratio (a
deterministic index threshold, not a per-agent coin flip), then a
specific norm sentence is picked at random from the matching pool in
prompts/personality_norms.json. Overwrites state/agents.json and
state/fluents.json, and resets state/runtime.json to a fresh round 0 —
switching agent count/mechanics makes the previous run's history not
meaningfully continuable.
"""
import json
import random
from pathlib import Path

from engine.physics import CARRYING_CAPACITY_KG

ROOT = Path(__file__).resolve().parent

NAMES = ["Kai", "Mara", "Toa", "Rina", "Beti", "Solo", "Lani", "Miro", "Nadia", "Tevita"]


def generate():
    config = json.loads((ROOT / "state" / "config.json").read_text())
    norms = json.loads((ROOT / "prompts" / "personality_norms.json").read_text())
    agent_count = config["agent_count"]
    altruism_ratio = config["altruism_ratio"]

    if agent_count > len(NAMES):
        raise ValueError(f"only {len(NAMES)} names available in NAMES, need {agent_count}")

    agents = {}
    fluents = []
    for i in range(agent_count):
        agent_id = f"agent_{i}"
        is_altruistic = i < agent_count * altruism_ratio
        pool = norms["altruistic"] if is_altruistic else norms["selfish"]
        agents[agent_id] = {
            "name": NAMES[i],
            "personality_traits": random.choice(pool),
            "is_altruistic": is_altruistic,
        }
        fluents.append(
            {
                "fluent": "fisher",
                "args": [agent_id],
                "holder": agent_id,
                "initiated_round": 0,
                "terminated_round": None,
            }
        )

    (ROOT / "state" / "agents.json").write_text(json.dumps(agents, indent=2) + "\n")
    (ROOT / "state" / "fluents.json").write_text(json.dumps(fluents, indent=2) + "\n")

    runtime = {"round": 0, "stock_kg": CARRYING_CAPACITY_KG, "rounds": []}
    (ROOT / "state" / "runtime.json").write_text(json.dumps(runtime, indent=2) + "\n")

    altruistic_count = sum(1 for a in agents.values() if a["is_altruistic"])
    print(f"Generated {agent_count} agents ({altruistic_count} altruistic, {agent_count - altruistic_count} selfish):")
    for agent_id, agent in agents.items():
        label = "altruistic" if agent["is_altruistic"] else "selfish"
        print(f"  {agent_id} ({agent['name']}, {label}): {agent['personality_traits']}")
    print("Reset state/runtime.json to a fresh round 0.")


if __name__ == "__main__":
    generate()
