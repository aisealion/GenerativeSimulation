"""Handler for verifying ledger entries at sunset.

For now this simply records a fact that verification was performed.
"""

def run(ctx):
    # Assume verification passes; record a public fact.
    from roles.roles import set_fact
    fluents = ctx.state["fluents"]
    round_number = ctx.round_number
    set_fact(
        fluents,
        "ledger_verified",
        [],
        "community",
        round_number,
        narration="Ledger entries verified at sunset.",
        visibility="public",
    )
    return {}
