class QuorumRule:
    """
    Rule to check quorum for council decisions.
    Quorum requires all active fishers, elder, and scribe present.
    """
    type_name = "quorum_rule"
    
    def __init__(self, params):
        pass
    
    def check(self, ctx):
        # Get current participants
        participants = ctx.get_fact("vote_disbursements.participants") or []
        
        # Get role holders
        current_elder = ctx.get_fact("community.current_elder") or None
        current_scribe = ctx.get_fact("community.current_scribe") or None
        
        # Get active fishers 
        active_fishers = ctx.get_fact("community.active_fishers") or []
        
        # Check if quorum is met
        required_participants = len(active_fishers) + 1  # all fishers + elder + scribe
        if current_elder:
            required_participants += 1
        if current_scribe:
            required_participants += 1
        
        quorum_met = len(participants) >= required_participants
        
        # Set fact that quorum is met for this vote
        ctx.set_fact("vote_disbursements.quorum_met", quorum_met)
        return True  # This is a deterministic rule