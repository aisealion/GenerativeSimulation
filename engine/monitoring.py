"""Live-updating monitoring plots for a run, regenerated at the end of
every round by engine/simulate.py's run_cycle(). Headless by construction
(matplotlib.use("Agg") below) — this has to render on Aoraki, which has no
display. Human/Claude-owned tooling, nothing here is in the
norm-implementer's permission.edit allowlist or relevant to its job.

Fixed filenames, overwritten every round rather than one-per-round
snapshots — that's what makes them "live": open the PNG once and it keeps
updating in place for the life of the run.

One outer try/except in update_plots() around everything below: a
plotting failure must never block a round, the same resilience contract
write_memory_episodes() already has for the optional memory layer.
"""
import json
import re
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from engine.physics import (
    GROWTH_RATE,
    HARVEST_PRODUCTIVITY,
    CARRYING_CAPACITY_KG,
    CONSUMPTION_KG,
)

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "logs" / "model_calls.jsonl"


def _current_branch():
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=ROOT, capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _plot_dir():
    safe_branch = re.sub(r"[^A-Za-z0-9_.-]", "_", _current_branch())
    plot_dir = ROOT / "plots" / safe_branch
    plot_dir.mkdir(parents=True, exist_ok=True)
    return plot_dir


def _read_call_log():
    """Tolerant JSONL reader — skips any line that fails to parse rather
    than raising, matching the "telemetry degrades, doesn't block" contract
    the rest of this module follows."""
    if not LOG_PATH.is_file():
        return []
    rows = []
    for line in LOG_PATH.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _harvest_rounds(runtime):
    return [r for r in runtime["rounds"] if r["phase"] == "harvest"]


def _config_footer(config):
    return (
        f"growth_rate={GROWTH_RATE}  harvest_productivity={HARVEST_PRODUCTIVITY}  "
        f"carrying_capacity={CARRYING_CAPACITY_KG}kg  consumption={CONSUMPTION_KG}kg/round  "
        f"altruism_ratio={config.get('altruism_ratio')}  agent_count={config.get('agent_count')}"
    )


def _new_figure(title, config):
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.set_title(title)
    ax.set_xlabel("round")
    fig.text(0.01, 0.01, _config_footer(config), fontsize=7, color="dimgray")
    fig.subplots_adjust(bottom=0.18)
    return fig, ax


def _save(fig, path):
    fig.savefig(path, dpi=110)
    plt.close(fig)


def _plot_effort(harvest_rounds, agents, config, plot_dir):
    fig, ax = _new_figure("Effort by agent", config)
    for agent_id, name in ((aid, a["name"]) for aid, a in agents.items()):
        points = [(r["round"], r["agents"][agent_id]["effort"]) for r in harvest_rounds if agent_id in r["agents"]]
        if points:
            xs, ys = zip(*points)
            ax.plot(xs, ys, marker="o", markersize=3, label=name)
    ax.set_ylabel("effort [0.0-1.0]")
    ax.legend(fontsize=7, ncol=2)
    _save(fig, plot_dir / "effort.png")


def _plot_harvest(harvest_rounds, agents, config, plot_dir):
    fig, ax = _new_figure("Harvest by agent", config)
    for agent_id, name in ((aid, a["name"]) for aid, a in agents.items()):
        points = [(r["round"], r["agents"][agent_id]["harvested_kg"]) for r in harvest_rounds if agent_id in r["agents"]]
        if points:
            xs, ys = zip(*points)
            ax.plot(xs, ys, marker="o", markersize=3, label=name)
    ax.set_ylabel("harvested kg")
    ax.legend(fontsize=7, ncol=2)
    _save(fig, plot_dir / "harvest.png")


def _plot_stock(harvest_rounds, config, plot_dir):
    fig, ax = _new_figure("Lake stock: before harvest / after harvest / after regrowth", config)
    xs = [r["round"] for r in harvest_rounds]
    ax.plot(xs, [r["stock_kg_before"] for r in harvest_rounds], marker="o", markersize=3, label="before harvest")
    ax.plot(xs, [r["stock_kg_after_harvest"] for r in harvest_rounds], marker="o", markersize=3, label="after harvest")
    ax.plot(xs, [r["stock_kg_after_regrowth"] for r in harvest_rounds], marker="o", markersize=3, label="after regrowth")
    ax.set_ylabel("stock kg")
    ax.legend(fontsize=8)
    _save(fig, plot_dir / "stock.png")


def _plot_active_agents(harvest_rounds, config, plot_dir):
    fig, ax = _new_figure("Active (alive) agents", config)
    xs = [r["round"] for r in harvest_rounds]
    ys = [len(r["agents"]) for r in harvest_rounds]
    ax.plot(xs, ys, marker="o", markersize=3, drawstyle="steps-post")
    ax.set_ylabel("alive agent count")
    _save(fig, plot_dir / "active_agents.png")


def _plot_tool_calls(implementer_rows, plot_dir):
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.set_title("Norm-implementer tool calls per round")
    ax.set_xlabel("round")
    ax.set_ylabel("tool calls")
    rounds = [row["round"] for row in implementer_rows]
    counts = [row.get("tool_call_count") or 0 for row in implementer_rows]
    ax.bar(rounds, counts)
    _save(fig, plot_dir / "tool_calls.png")


def _plot_commits(call_log, plot_dir):
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.set_title("Norm-implementer outcome per round")
    ax.set_xlabel("round")
    colors = {"norm_implementer_committed": "tab:green", "norm_implementer_discarded": "tab:red",
              "norm_implementer_no_changes": "tab:gray"}
    outcome_rows = [row for row in call_log if row.get("call") in colors]
    for outcome, color in colors.items():
        rounds = [row["round"] for row in outcome_rows if row["call"] == outcome]
        if rounds:
            ax.bar(rounds, [1] * len(rounds), color=color, label=outcome.replace("norm_implementer_", ""))
    ax.set_yticks([])
    ax.legend(fontsize=8)
    _save(fig, plot_dir / "commits.png")


def _plot_tests(implementer_rows, plot_dir):
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.set_title("norm_checks/ tests written per round (color = pass/fail)")
    ax.set_xlabel("round")
    ax.set_ylabel("tests written")
    for row in implementer_rows:
        report = row.get("report") or {}
        written = report.get("norm_check_tests_written") or []
        if not written:
            continue
        passed = report.get("norm_check_tests_pass")
        ax.bar(row["round"], len(written), color="tab:green" if passed else "tab:red")
    _save(fig, plot_dir / "tests.png")


def update_plots(state):
    try:
        runtime = state["runtime"]
        agents = state["agents"]
        config = state["config"]
        plot_dir = _plot_dir()

        harvest_rounds = _harvest_rounds(runtime)
        if harvest_rounds:
            _plot_effort(harvest_rounds, agents, config, plot_dir)
            _plot_harvest(harvest_rounds, agents, config, plot_dir)
            _plot_stock(harvest_rounds, config, plot_dir)
            _plot_active_agents(harvest_rounds, config, plot_dir)

        call_log = _read_call_log()
        implementer_rows = [row for row in call_log if row.get("call") == "norm_implementer"]
        if implementer_rows:
            _plot_tool_calls(implementer_rows, plot_dir)
            _plot_tests(implementer_rows, plot_dir)
        _plot_commits(call_log, plot_dir)
    except Exception as exc:
        print(f"  [monitoring plots skipped: {exc}]")
