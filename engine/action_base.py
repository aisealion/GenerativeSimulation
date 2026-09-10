from engine.physics import alive_agent_ids
from roles.grants import apply_role_grant, apply_institutional_fact


class Action:
    """Base class for one entry in state/schedule.json. A module under actions/
    defines exactly one subclass and exposes a module-level `ACTION` instance
    of it — that's what engine/simulate.py imports and calls."""

    name = None  # must match the filename stem and the state/schedule.json key

    def run(self, state):
        """Execute this action's mechanism logic (and any agent calls this
        round). Returns the round_record dict engine/simulate.py appends to
        runtime['rounds']."""
        raise NotImplementedError

    def prompt_fields(self, state, agent_id):
        """Fields to render actions/prompts/{name}.md for one agent this
        round. Only implemented by actions that call the fisher agent."""
        raise NotImplementedError

    def memory_writes(self, state, round_record):
        """Episode specs worth remembering from this round's run of this
        action. Each item is a dict with event_type/text/agent_id/group_id
        keys (round_num is filled in by the caller). Empty by default —
        override only for actions whose mechanisms produce a real event_type."""
        return []


class SimpleAgentAction(Action):
    """Base class for the common action shape: one fisher-agent call per
    participating agent, each response optionally granting a role
    (`role_grant()`) and/or recording a visible institutional fact
    (`institutional_fact()`). Subclass this instead of Action directly
    unless your action's orchestration is genuinely different — a bounded
    multi-turn dialogue, multiple different model roles per participant, a
    step that isn't per-agent at all (see actions/critique.py, which stays
    a direct Action subclass for exactly this reason).

    Required overrides (no default — raise NotImplementedError here):

    - build_fields(self, state, setup_ctx, agent_id): this agent's prompt
      fields for this round.
    - call_agent(self, agent_id, round_number, fields): perform the actual
      model call and return its parsed response dict. Deliberately not
      given a default implementation here: existing tests
      (tests/norms/test_harvest_action_baseline.py) and
      engine/simulate.py's own orchestrator smoke-check both patch
      `call_fisher_agent` as a name inside the ACTING MODULE's own
      namespace (`monkeypatch.setattr(harvest_module, "call_fisher_agent", ...)`)
      — a base-class-owned call site would silently stop being
      interceptable by either. Each subclass's own call_agent() must call
      the module-level `call_fisher_agent(...)` name textually within its
      own file, typically just:
          def call_agent(self, agent_id, round_number, fields):
              return call_fisher_agent(agent_id, round_number, self.name, **fields)
    - record_result(self, state, setup_ctx, agent_id, response): turn one
      agent's raw response into that agent's round_record entry, applying
      any mechanism-specific state mutation (a payoff update, say) as a
      side effect here.

    Overrides with a sensible default — override only when different:

    - setup(self, state) -> None: computed once per real run(); the public
      prompt_fields(state, agent_id) contract (2 args, for external/preview
      use) calls this fresh on demand rather than reusing a stashed value.
    - participants(self, state, setup_ctx) -> every alive fisher.
    - is_eligible(self, state, setup_ctx, agent_id) -> True.
    - ineligible_result(self, state, setup_ctx, agent_id): only ever
      called if is_eligible() is also overridden to return False for
      someone — raises NotImplementedError by default since an action
      that never rejects anyone never needs this.
    - per_agent_key(self) -> "agents": the round_record key the per-agent
      dict is stored under. Override (e.g. to "proposals"/"votes") rather
      than renaming an existing action's own historical key — a rename
      ripples into render_history(), other actions reading this one's
      round record, and already-written runtime.json history for zero
      behavioral benefit.
    - after_participants(self, state, setup_ctx, agent_records) -> {}:
      extra top-level round_record fields, and any cross-agent
      aggregation or end-of-round mechanism step that needs every agent's
      result at once (a vote tally, a stock/regrowth calculation).
    - role_grant(self, state, setup_ctx, agent_id, response) -> None:
      return a roles.grants.RoleGrant to have this response grant/update a
      role fluent.
    - institutional_fact(self, state, setup_ctx, agent_id, response) -> None:
      return a roles.grants.InstitutionalFact to have this response record
      a visible, non-role fact.
    """

    def setup(self, state):
        return None

    def participants(self, state, setup_ctx):
        return alive_agent_ids(state["agents"], state["runtime"])

    def is_eligible(self, state, setup_ctx, agent_id):
        return True

    def ineligible_result(self, state, setup_ctx, agent_id):
        raise NotImplementedError

    def build_fields(self, state, setup_ctx, agent_id):
        raise NotImplementedError

    def call_agent(self, agent_id, round_number, fields):
        raise NotImplementedError

    def record_result(self, state, setup_ctx, agent_id, response):
        raise NotImplementedError

    def per_agent_key(self):
        return "agents"

    def after_participants(self, state, setup_ctx, agent_records):
        return {}

    def role_grant(self, state, setup_ctx, agent_id, response):
        return None

    def institutional_fact(self, state, setup_ctx, agent_id, response):
        return None

    # ---- fixed — not meant to be overridden ----

    def prompt_fields(self, state, agent_id):
        return self.build_fields(state, self.setup(state), agent_id)

    def run(self, state):
        runtime, round_number, fluents = state["runtime"], state["round_number"], state["fluents"]
        setup_ctx = self.setup(state)
        agent_records = {}
        for agent_id in self.participants(state, setup_ctx):
            if not self.is_eligible(state, setup_ctx, agent_id):
                agent_records[agent_id] = self.ineligible_result(state, setup_ctx, agent_id)
                continue
            fields = self.build_fields(state, setup_ctx, agent_id)
            response = self.call_agent(agent_id, round_number, fields)
            agent_records[agent_id] = self.record_result(state, setup_ctx, agent_id, response)

            grant = self.role_grant(state, setup_ctx, agent_id, response)
            if grant is not None:
                apply_role_grant(fluents, round_number, agent_id, grant)

            fact = self.institutional_fact(state, setup_ctx, agent_id, response)
            if fact is not None:
                apply_institutional_fact(fluents, round_number, fact)

        extra = self.after_participants(state, setup_ctx, agent_records)
        round_record = {
            "round": round_number,
            "action": self.name,
            self.per_agent_key(): agent_records,
            **extra,
        }
        runtime["round"] = round_number
        runtime["rounds"].append(round_record)
        return round_record
