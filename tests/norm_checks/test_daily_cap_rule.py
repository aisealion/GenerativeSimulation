import json
import copy
from engine.institution.rules import RuleSet
from actions.rules.harvest.daily_cap import DailyCapRule

def test_daily_cap_enforces_25_percent_limit():
    # Setup state with a lake stock of 100 kg
    state = {
        "runtime": {"stock_kg": 100},
        "config": {"rules": {"harvest": []}},
        "fluents": [],
    }
    # Create a mock ActionContext with necessary attributes
    class MockCtx:
        def __init__(self, state):
            self.state = state
            self.round_number = 1
    ctx = MockCtx(state)
    # Instantiate rule via RuleSet to use after_action hook
    # Manually add the rule spec
    rule_spec = {"type": "daily_cap"}
    state["config"]["rules"]["harvest"].append(rule_spec)
    rule_set = RuleSet.for_action(state["config"], "harvest", ctx.round_number)
    # Simulate round_record with agents harvesting 30 kg total (exceeds 25% of 100 = 25)
    round_record = {"agents": {"agent1": {"harvested_kg": 15}, "agent2": {"harvested_kg": 15}}}
    # Run after_action of the rule (should reduce stock by surplus 5)
    for rule in rule_set.rules:
        if isinstance(rule, DailyCapRule):
            rule.after_action(ctx, round_record)
    assert ctx.state["runtime"]["stock_kg"] == 95
