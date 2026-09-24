def rule_handler(action_params, agent_id, fluents, round_number, rule_params):
    """
    Rule for transferring 10% of monthly catch sum to communal reserve
    """
    # This rule runs at the end of a round to process all catches from that round
    # We need to aggregate the catch for all fishers and apply 10% transfer
    
    # Check if we're processing the right round's data
    if not hasattr(rule_handler, 'processed_round') or rule_handler.processed_round != round_number:
        rule_handler.processed_round = round_number
    
    # Get all catches for this round
    round_catches = []
    for fact in fluents:
        if (fact.get("fluent") == "catch_log" and 
            fact.get("args") and fact.get("args")[1] == round_number):
            round_catches.append(fact)
    
    if not round_catches:
        return {"applied": False}
        
    # Sum up all the catches for the round  
    total_catch = sum(catch.get("args", [0, 0, 0])[-1] if len(catch.get("args", [])) > 2 else 0 
                      for catch in round_catches)
    
    if total_catch > 0:
        transfer_amount = 0.1 * total_catch
        
        narration = f"Automatic 10% transfer of monthly catch sum ({total_catch}kg): {transfer_amount}kg to reserve"
        
        # Create a reserve transfer fact record
        set_fact(
            fluents, "reserve_transfer",
            [round_number, "monthly"], "community", round_number,
            narration=narration,
            visibility="public", 
            event_type="monthly_catch_transferred"
        )
        
        return {
            "applied": True,
            "narration": narration,
            "amount_transferred": transfer_amount
        }
    
    return {
        "applied": False
    }