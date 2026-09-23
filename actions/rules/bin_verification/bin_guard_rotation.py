from engine.institution.rules import Rule


class BinGuardRotation(Rule):
    """
    Rule to rotate the bin guard role among fishers alphabetically.
    """
    type_name = "bin_guard_rotation"

    def is_eligible(self, ctx, agent_id):
        """
        Any fisher is eligible to be assigned as a bin guard.
        """
        return True

    def describe(self, ctx, agent_id):
        """
        Return a description of the rule's constraint for this agent.
        """
        return "The bin guard role is rotated alphabetically among fishers."

    def before_action(self, ctx):
        """
        Before processing the bin_verification action, rotate the guard if needed.
        """
        # Get the current roster from the state
        all_agents = ctx.state["runtime"]["agents"]
        roster = sorted([agent["name"] for agent in all_agents])
        
        # Get current guard state
        current_guard = ctx.state["runtime"].get("bin_guard", {}).get("current_guard", None) 
        
        # Get guard history - if not exists, initialize
        guard_history = ctx.state["runtime"].get("bin_guard", {}).get("guard_history", [])
        
        # If current guard is not set, assign the first in roster
        if current_guard is None:
            new_guard = roster[0]
            ctx.state["runtime"]["bin_guard"] = {
                "current_guard": new_guard,
                "guard_history": [new_guard]
            }
            # Set the guard
            ctx.events.emit(
                f"The bin guard for this round is {new_guard} (assigned alphabetically).",
                visibility="public"
            )
        else:
            # If we have a current guard, we need to check if we should rotate
            # In this simple implementation, we rotate every round
            current_guard_index = roster.index(current_guard)
            next_guard_index = (current_guard_index + 1) % len(roster)
            new_guard = roster[next_guard_index]
            
            # Update the guard record
            ctx.state["runtime"]["bin_guard"] = {
                "current_guard": new_guard,
                "guard_history": guard_history + [new_guard]
            }
            
            ctx.events.emit(
                f"The bin guard for this round is {new_guard} (rotated from {current_guard}).",
                visibility="public"
            )
    
    def after_agent(self, ctx, agent_id, record_entry):
        """
        After agent processing: record the verification result.
        """
        return None

    def on_agent_settled(self, ctx, agent_id, record_entry):
        """
        When an agent's record is fully settled.
        """
        pass