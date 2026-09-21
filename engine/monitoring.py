"""Live-updating monitoring plots for a run, regenerated at the end of
every round by engine/simulate.py's run_cycle(). Headless by construction
(matplotlib.use("Agg") below) — this has to render on Aoraki, which has no
display. Human/Claude-owned tooling, nothing here is in the
norm pipeline agents' permission.edit allowlists or relevant to their job.

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
LOG_PATH = ROOT / "ops" / "logs" / "model_calls.jsonl"


def _current_branch():
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=ROOT, capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _plot_dir():
    safe_branch = re.sub(r"[^A-Za-z0-9_.-]", "_", _current_branch())
    plot_dir = ROOT / "ops" / "plots" / safe_branch
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
    return [r for r in runtime["rounds"] if r["action"] == "harvest"]


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


def _plot_tool_calls(engineer_rows, plot_dir):
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.set_title("Norm-engineer tool calls per round")
    ax.set_xlabel("round")
    ax.set_ylabel("tool calls")
    rounds = [row["round"] for row in engineer_rows]
    counts = [row.get("tool_call_count") or 0 for row in engineer_rows]
    ax.bar(rounds, counts)
    _save(fig, plot_dir / "tool_calls.png")


def _agent_step_budget(agent_name, default):
    """Reads the real `steps:` cap straight from the opencode agent's own
    frontmatter (`.opencode/agent/{agent_name}.md` — the copy
    engine/simulate.py actually invokes, per CLAUDE.md) rather than
    hardcoding a number here that could silently drift from it. A plain
    regex, not a YAML parse — PyYAML isn't a project dependency (checked
    directly: not in pyproject.toml), and this module has to keep working
    in the minimal HPC venv, so pulling one in just to read a single
    top-level integer field isn't worth the new dependency. Falls back to
    `default` on any read/parse failure, same "telemetry degrades, doesn't
    block" contract as the rest of this module."""
    try:
        text = (ROOT / ".opencode" / "agent" / f"{agent_name}.md").read_text()
        match = re.search(r"^steps:\s*(\d+)", text, re.MULTILINE)
        return int(match.group(1)) if match else default
    except OSError:
        return default


def _plot_steps(call_log, plot_dir):
    """Step count (one full model turn — see parse_opencode_jsonl()'s own
    docstring for how this differs from tool-call count) per invocation,
    for all three norm pipeline agents on one chart, each against its own
    steps: budget as a reference line — added 2026-09-09, by request,
    specifically so it's visible how close a real round is running to
    actually exhausting its budget (the failure mode PHASE/Section 16's
    own "ran out of budget" handling exists for), rather than only ever
    inferring that after the fact from a truncated response. Extended
    2026-09-21 from two series (norm-implementer/norm-evaluator) to three
    (norm-architect/norm-engineer/norm-auditor) for the dual-model/TDD/
    auditor split."""
    series = [
        ("norm_architect", "norm-architect", "tab:blue", -0.25),
        ("norm_engineer", "norm-engineer", "tab:orange", 0.0),
        ("norm_auditor", "norm-auditor", "tab:green", 0.25),
    ]
    rows_by_call = {tag: [row for row in call_log if row.get("call") == tag] for tag, _, _, _ in series}
    if not any(rows_by_call.values()):
        return

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.set_title("Agent step count per invocation (vs. each agent's own steps: budget)")
    ax.set_xlabel("round")
    ax.set_ylabel("steps used")

    for tag, label, color, offset in series:
        rows = rows_by_call[tag]
        if not rows:
            continue
        rounds = [row["round"] for row in rows]
        counts = [row.get("step_count") or 0 for row in rows]
        ax.bar([r + offset for r in rounds], counts, width=0.25, color=color, label=label)
        budget = _agent_step_budget(label, 500)
        ax.axhline(budget, color=color, linestyle="--", linewidth=1, label=f"{label} budget ({budget})")
    ax.legend(fontsize=7)
    _save(fig, plot_dir / "steps.png")


def _plot_commits(call_log, plot_dir):
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.set_title("Norm round outcome per round")
    ax.set_xlabel("round")
    colors = {"norm_round_committed": "tab:green", "norm_round_discarded": "tab:red",
              "norm_round_no_changes": "tab:gray"}
    outcome_rows = [row for row in call_log if row.get("call") in colors]
    for outcome, color in colors.items():
        rounds = [row["round"] for row in outcome_rows if row["call"] == outcome]
        if rounds:
            ax.bar(rounds, [1] * len(rounds), color=color, label=outcome.replace("norm_round_", ""))
    ax.set_yticks([])
    ax.legend(fontsize=8)
    _save(fig, plot_dir / "commits.png")


def _plot_tests(architect_rows, plot_dir):
    """Tests norm-architect wrote per round, before any implementation
    existed — color reflects tests_confirmed_red (its own self-check that
    every test it wrote actually collects and fails for the right reason),
    not pass/fail against a finished implementation (that's
    tests/norm_evaluation/'s job, tracked separately by norm-auditor)."""
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.set_title("norm_checks/round_N/ tests written per round (color = confirmed red)")
    ax.set_xlabel("round")
    ax.set_ylabel("tests written")
    for row in architect_rows:
        report = row.get("report") or {}
        written = report.get("test_files_written") or []
        if not written:
            continue
        confirmed_red = report.get("tests_confirmed_red")
        ax.bar(row["round"], len(written), color="tab:green" if confirmed_red else "tab:red")
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
        architect_rows = [row for row in call_log if row.get("call") == "norm_architect"]
        engineer_rows = [row for row in call_log if row.get("call") == "norm_engineer"]
        if engineer_rows:
            _plot_tool_calls(engineer_rows, plot_dir)
        if architect_rows:
            _plot_tests(architect_rows, plot_dir)
        _plot_commits(call_log, plot_dir)
        _plot_steps(call_log, plot_dir)
    except Exception as exc:
        print(f"  [monitoring plots skipped: {exc}]")
