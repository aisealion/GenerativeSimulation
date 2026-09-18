from engine.institution.rules import Rule

class CouncilMeetingRule(Rule):
    """Placeholder rule for council meeting action.
    Currently does not enforce any additional constraints.
    """
    type_name = "council_meeting_rule"
    # No custom behavior needed; rely on default hooks.
    pass
