# GenerativeSimulation

A two-fisher common-pool-resource simulation. The lake starts at 300kg,
regrows 100kg/round up to a 300kg carrying capacity
(`state/config.json`). Kai (selfish) and Mara (altruistic) — roster in
`state/agents.json` — harvest, then propose and vote on a shared norm,
which the `norm-implementer` agent then implements in code and commits.

Run with `python3 simulate.py`. Two separate model call paths, each with
its own config: the `norm-implementer` still runs as an `opencode` agent
(needs `opencode` configured with a working model — see `opencode.jsonc`,
`litellm/*` for the Otago proxy, `ollama/gpt-oss:120b` for local Ollama);
the fisher agent calls the model directly via `litellm` from
`llm_agents.py` (needs `FISHER_MODEL` set, same `provider/name` convention,
e.g. `litellm/Kimi-K2.5` or `ollama/gpt-oss:120b` — defaults to
`litellm/Kimi-K2.5` if unset — plus `LITELLM_API_KEY` for the `litellm/*`
path). On Aoraki (Otago's HPC), submit
`run_simulation.slurm` instead of running directly. It runs
`apptainer run --nv .../ollama_shellenv.sif "<one command string>"`
directly (matching Otago's own `ollama-batch-example.slurm`), rather than
via the `ollama-env.sh` wrapper — that wrapper doesn't export anything
back to the calling shell, it just execs the same apptainer invocation,
so there's nothing gained by depending on it here. The container's
`OLLAMA_HOST` (a random per-instance port) only exists inside that
container process, so the single command string is
`hpc_ollama_entrypoint.sh`: it writes a job-specific
`.opencode/opencode.json` (gitignored) pointing the `ollama` provider at
the actual `$OLLAMA_HOST`, then runs `simulate.py` from inside that same
context — none of this can happen in the outer SLURM script itself.
Every round renegotiates:
harvest, then propose + vote + implement, then next round's harvest picks
up whatever the norm-implementer just changed. Resumes from
`state/runtime.json`'s current round, not from round 1 — safe to re-run
after a norm-implementer change. Stops when the lake collapses
(`stock_kg_after_regrowth <= 0`) or after `--max-rounds` (default 50,
override with `python3 simulate.py --max-rounds N`).

Regrowth is a flat `regrowth_kg_per_round` add, not proportional to
current stock (this was the original spec) — so under the stock config
alone, `stock_kg_after_regrowth` can hit exactly 0 but bounces back next
round; it can't go negative or stay at 0. True permanent collapse only
happens if some adopted norm's Operationalization leads the
norm-implementer to make regrowth conditional on stock (a structural
mechanism change) — until/unless that happens, expect most runs to end
via the `--max-rounds` safety cap, not collapse.

## Non-obvious file ownership (not covered by the norm-implementer's own
## repo-shape notes, since these were added after that agent was defined)

- `state/agents.json` — static roster (name, personality_traits) for the
  two fishers. Simulation setup data, not policy — the norm-implementer
  must never write here, only `phases/*.py` reads it.
- `llm_agents.py` — renders `prompts/persona_template.md` +
  `prompts/role_directives/*.md` + `prompts/phases/*.md` into a prompt and
  calls the fisher model directly via `litellm.completion()` (not through
  opencode) — the system prompt is read from `.opencode/agent/fisher.md`'s
  body, which is no longer invoked as an opencode agent but is kept as the
  single source of that text. Imported by `phases/harvest.py`, `propose.py`,
  `vote.py`.
- `simulate.py` — the round orchestrator. Schedule-driven, not hardcoded:
  each round it reads `schedule.json`, runs whatever phase is gated on (in
  file order), and dynamically imports `phases.<name>` and calls its
  module-level `PHASE.run(state)` — adding a phase to `phases/` and
  registering it in `schedule.json` is enough to wire it in, no
  `simulate.py` edit needed. Owns writing `state/runtime.json` and
  `state/fluents.json` between phases, and invokes the `norm-implementer`
  opencode agent whenever any phase sets `state["adopted_norm"]`
  (currently only `vote` does).
- `phases/base.py` — the `Phase` base class every phase module subclasses
  (`run`, `prompt_fields`, `memory_writes`). Human-owned scaffolding, not
  something a norm round edits.
- `.opencode/agent/fisher.md` — one generic system prompt for both
  fishers (its frontmatter is vestigial; only the body text is read now,
  by `llm_agents.py`, not opencode); personality comes from the per-round
  rendered prompt (`state/agents.json`), not from separate files per
  persona.
- `.opencode/agent/norm-implementer.md` / `.claude/agents/norm-implementer.md`
  — two copies of the same agent definition, kept in sync by hand. The
  opencode copy is the one `simulate.py` actually invokes.
- `memory/` — the Graphiti/Neo4j temporal memory layer (`client.py` the
  shared connection, `write.py` episode writes + `IMPORTANCE_BY_EVENT_TYPE`,
  `query.py` retrieval + `PHASE_QUERY_TEMPLATES`). Local-only infra for now
  (never deployed on Aoraki) — `simulate.py`'s `write_memory_episodes()` and
  `llm_agents.py`'s `render_relevant_memories()` both no-op gracefully
  whenever `NEO4J_URI` isn't set or the DB isn't reachable, so its absence
  never blocks a round. Human-owned scaffolding, like `llm_agents.py` —
  the norm-implementer only ever touches it indirectly, by adding a
  `memory_writes()` override to a phase it's already editing for another
  reason.

## Prompt layer rules

The `prompts/` tree is the only place agent-facing text lives. It stays
fourth-wall clean: no internal state key names, code identifiers, or the
words "mechanism," "norm," "fluent," "penalty function" ever appear in
rendered prompt text.

- `prompts/persona_template.md` — static skeleton per agent. Slots are
  filled at render time from current state; never edited per-round or
  per-agent.
- `prompts/role_directives/` — one file per `role_name`, in-world
  phrasing only. The only place role-specific instruction text lives.
- `prompts/phases/` — one instruction template per phase, filled from
  `state/runtime.json` + `state/config.json` at render time.
- `prompts/phrasing_map.json` — maps internal state keys to in-world
  phrases. This is the fourth-wall boundary: internal names and numeric
  mechanics never appear in rendered text directly, only their mapped
  phrasing.
- `prompts/memory_phrasing.py` — same fourth-wall boundary, for the one
  case a static JSON map can't handle: turning a memory record's
  `event_type` into an in-world frame sentence around already-phrased
  text. Every `event_type` in `memory/write.py`'s `IMPORTANCE_BY_EVENT_TYPE`
  needs a case here, or it raises rather than leaking unphrased.

### Routing a rule change

- **role_fluent, role_name already has a file in `prompts/role_directives/`**:
  fully parametric — no prompt files touched.
- **role_fluent, role_name is new**: write the config/fluent schema as
  usual, AND add exactly one new file
  `prompts/role_directives/{role_name}.md` with in-world instruction
  phrasing. This is the only prompt edit a role change should ever
  require.
- **new_phase**: same rule — add `prompts/phases/{phase_name}.md`
  alongside the phase's `.py` file.
- **Any other rule**: never touch `prompts/`. If you're tempted to edit
  an individual agent's rendered prompt directly, or hand-write text like
  "this round you are the monitor, your task is X" inline in
  mechanism/phase code, stop — that instruction belongs in
  `prompts/role_directives/monitor.md`, filled generically.

### Validating a prompt-layer change

- Grep any new file under `prompts/` for internal state key names, code
  identifiers, or "mechanism," "norm," "fluent," "penalty function" — any
  hit is a fourth-wall violation and must be rephrased.
- Confirm no diff touches a rendered/output prompt directly — only
  `prompts/persona_template.md`, `prompts/role_directives/*.md`, or
  `prompts/phases/*.md` are legitimate prompt-layer diffs.
