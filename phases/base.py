class Phase:
    """Base class for one entry in schedule.json. A module under phases/
    defines exactly one subclass and exposes a module-level `PHASE` instance
    of it — that's what simulate.py imports and calls."""

    name = None  # must match the filename stem and the schedule.json key

    def run(self, state):
        """Execute this phase's mechanism logic (and any agent calls this
        round). Returns the round_record dict simulate.py appends to
        runtime['rounds']."""
        raise NotImplementedError

    def prompt_fields(self, state, agent_id):
        """Fields to render prompts/phases/{name}.md for one agent this
        round. Only implemented by phases that call the fisher agent."""
        raise NotImplementedError

    def memory_writes(self, state, round_record):
        """Episode specs worth remembering from this round's run of this
        phase. Each item is a dict with event_type/text/agent_id/group_id
        keys (round_num is filled in by the caller). Empty by default —
        override only for phases whose mechanisms produce a real event_type."""
        return []
