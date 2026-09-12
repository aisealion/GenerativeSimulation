# The one per-agent decision loop every action's own handler needs:
# skip an ineligible agent, otherwise call the fisher, turn the response
# into a record, run it through the chained rule hooks. harvest/propose/
# vote and the generic zero-code builtin_handlers.generic_agent_decision
# all did this by hand, near-identically — pulled out here so every one
# of them shares the exact same rule semantics automatically, the same
# reason RuleSet itself is one class every action's handler shares
# instead of five almost-identical rewrites.

def default_ineligible_record(ctx, agent_id):
    return {"participated": False, "note": ctx.rules.ineligibility_note(ctx, agent_id)}


def per_agent_decision(ctx, build_fields, build_record, ineligible_record=None, after_settle=None):
    """For each of ctx.participants, in order:

    - If the agent is ineligible this round (ctx.rules.is_eligible() is
      False), record ineligible_record(agent_id) instead of calling the
      agent at all — defaults to default_ineligible_record(ctx, agent_id).
    - Otherwise: call ctx.agents.call(agent_id, **build_fields(agent_id)),
      turn the raw response into a record via build_record(agent_id,
      response), default "participated" to True, then run
      ctx.rules.apply_after_agent()/settle_agent() in that order — the
      same chained-patch-then-settle sequence every handler already
      needs, in the same order every hand-written loop already used.
    - If given, after_settle(agent_id, record_entry) runs immediately
      after settle_agent() for that one agent, before moving to the next
      participant — for a side effect that needs the rule-settled record
      (a payoff update, a death check) and needs to see each agent
      resolved one at a time in participant order, not the whole batch
      afterward.

    Returns {agent_id: record_entry}, in ctx.participants order (a plain
    dict — insertion-ordered) — the same shape every existing handler
    already built by hand.
    """
    ineligible_record = ineligible_record or (lambda agent_id: default_ineligible_record(ctx, agent_id))
    records = {}
    for agent_id in ctx.participants:
        if not ctx.rules.is_eligible(ctx, agent_id):
            records[agent_id] = ineligible_record(agent_id)
            continue

        response = ctx.agents.call(agent_id, **build_fields(agent_id))
        record_entry = build_record(agent_id, response)
        record_entry.setdefault("participated", True)
        ctx.rules.apply_after_agent(ctx, agent_id, record_entry)
        ctx.rules.settle_agent(ctx, agent_id, record_entry)
        if after_settle is not None:
            after_settle(agent_id, record_entry)
        records[agent_id] = record_entry
    return records
