from engine.institution.rules import Rule

class CatchLimitRule(Rule):
    type_name = "catch_limit"

    def __init__(self, key: str, params: dict) -> None:
        super().__init__(key, params)
        self.limit_kg_per_day = params.get("limit_kg_per_day", 1.5)

    def after_agent(self, ctx, agent_id, record_entry):
        if record_entry.get("harvested_kg", 0) > self.limit_kg_per_day:
            # Cap the catch at the limit
            record_entry["harvested_kg"] = self.limit_kg_per_day
            # Add a note explaining what happened
            record_entry["note"] = (
                f"Caught {record_entry['harvested_kg']} kg, "
                f"limited from {record_entry.get('harvested_kg', 0)} kg due to daily limit."
            )
        return record_entry