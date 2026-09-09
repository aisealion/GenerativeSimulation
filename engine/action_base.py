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
        """Fields to render prompts/actions/{name}.md for one agent this
        round. Only implemented by actions that call the fisher agent."""
        raise NotImplementedError

    def memory_writes(self, state, round_record):
        """Episode specs worth remembering from this round's run of this
        action. Each item is a dict with event_type/text/agent_id/group_id
        keys (round_num is filled in by the caller). Empty by default —
        override only for actions whose mechanisms produce a real event_type."""
        return []
