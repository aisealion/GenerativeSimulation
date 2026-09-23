import pytest

@pytest.mark.usefixtures("setup_fishery")
class TestFisheryNorm:
    def test_record_keeping_and_reduction(self):
        # Setup: 10 fishers each plan to catch 6kg, stock is 100kg (50% = 50kg)
        state = {
            "community": {"stock_kg": 100},
            "fisher": [
                {"agent_id": f"fisher_{i}", "planned_catch": 6} for i in range(10)
            ]
        }
        
        # Test proportional reduction calculation
        total_planned = sum(f["planned_catch"] for f in state["fisher"])
        reduction_factor = 0.5 * 100 / total_planned
        expected_reduced = {f"fisher_{i}": 6 * reduction_factor for i in range(10)}
        
        # Apply and verify reduction
        reduced_catches = apply_reduction(state)
        assert all(v == expected_reduced[agent] for agent, v in reduced_catches.items())
    
    def test_12kg_enforcement(self):
        # Test case where one fisher exceeds 12kg
        state = {
            "community": {"stock_kg": 200},
            "fisher": [
                {"agent_id": "fisher_1", "catch": 15},  # Over limit
                {"agent_id": "fisher_2", "catch": 10}   # Under limit
            ]
        }
        
        enforcement_outcome = enforce_catch_limits(state)
        assert enforcement_outcome["fisher_1"]["excess"] == 3
        assert enforcement_outcome["fisher_1"].get("ban") is True
        assert "ban" not in enforcement_outcome["fisher_2"]
    
    def test_stock_critical_meeting(self):
        # Test stock below 200kg triggers meeting and cap adjustment
        state = {
            "community": {"stock_kg": 150},
            "fisher": [{"agent_id": f"fisher_{i}"} for i in range(10)]
        }
        
        meeting_triggered, new_cap = handle_low_stock(state)
        assert meeting_triggered is True
        
        # Test quorum check with 75% required
        state["community"]["stock_kg"] = 180
        quorum_met = check_quorum(state, 8)  # 10 fishers * 0.75 = 7.5 → 8 required
        assert quorum_met is True
        
        # Test cap voting with multiple options
        vote_results = conduct_cap_vote(state, [
            {"option": "fixed", "value": 10},
            {"option": "percent", "value": 40}
        ])
        assert isinstance(vote_results, dict)
