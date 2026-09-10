# Independent evaluator tests for Round 5 norm implementation
# Tests ALL requirements from the norm specification independently

import sys
sys.path.insert(0, '.')

from norms.catch_limit_with_penalty_trips import CatchLimitWithPenaltyTripsNorm
from engine.norms.context import HarvestContext


def create_test_context(stock_kg=100.0, round_number=1):
    """Create a test context with the given parameters."""
    return HarvestContext.from_state({
        'config': {
            'norms': [{
                'type': 'catch_limit_with_penalty_trips',
                'id': 'round_5_limit',
                'max_kg_per_trip': 5.0,
                'reserve_deposit_percent': 0.12,
                'min_stock_percent_remaining': 0.15,
                'penalty_trip_kg': 1.0
            }]
        },
        'fluents': [],
        'runtime': {'stock_kg': stock_kg},
        'agents': {
            'agent_0': {'name': 'Test0', 'personality_traits': ''},
            'agent_1': {'name': 'Test1', 'personality_traits': ''},
            'agent_2': {'name': 'Test2', 'personality_traits': ''},
        },
        'round_number': round_number,
    })


def create_test_norm():
    """Create a test instance of the norm."""
    return CatchLimitWithPenaltyTripsNorm(
        key='round_5_limit',
        params={
            'max_kg_per_trip': 5.0,
            'reserve_deposit_percent': 0.12,
            'min_stock_percent_remaining': 0.15,
            'penalty_trip_kg': 1.0
        }
    )


# =============================================================================
# REQUIREMENT 1: Fixed 5kg per-trip catch limit
# =============================================================================

def test_requirement_1_5kg_limit_exact():
    """REQ 1: Fisher catching exactly 5kg keeps it (minus 12% deposit)."""
    context = create_test_context()
    norm = create_test_norm()
    norm.on_round_start(context)

    decision = norm.evaluate(context, 'agent_0', raw_kg=5.0, proposed_kg=5.0)

    # Should keep 5kg minus 12% deposit = 4.4kg
    assert abs(decision.kept_kg - 4.4) < 0.001, f"Expected 4.4kg, got {decision.kept_kg}kg"
    assert decision.sanction is None, "Should not have sanction at exactly 5kg"
    print("✓ REQ 1: 5kg limit - exact limit respected")


def test_requirement_1_5kg_limit_exceeded():
    """REQ 1: Fisher catching over 5kg forfeits excess and gets penalty."""
    context = create_test_context()
    norm = create_test_norm()
    norm.on_round_start(context)

    decision = norm.evaluate(context, 'agent_0', raw_kg=7.0, proposed_kg=7.0)
    state = context.norm_state('round_5_limit')

    # Should keep only 5kg minus 12% = 4.4kg
    assert abs(decision.kept_kg - 4.4) < 0.001, f"Expected 4.4kg, got {decision.kept_kg}kg"
    # Should record violation
    assert decision.sanction == 'catch_limit_exceeded', "Should record sanction for exceeding limit"
    # 2kg excess forfeited to reserve + 0.6kg deposit = 2.6kg in reserve
    assert abs(state['shared_reserve'] - 2.6) < 0.001, f"Expected 2.6kg in reserve, got {state['shared_reserve']}kg"
    print("✓ REQ 1: 5kg limit - excess forfeited, violation recorded")


def test_requirement_1_5kg_limit_below():
    """REQ 1: Fisher catching below 5kg keeps full allowed amount."""
    context = create_test_context()
    norm = create_test_norm()
    norm.on_round_start(context)

    decision = norm.evaluate(context, 'agent_0', raw_kg=3.5, proposed_kg=3.5)

    # Should keep 3.5kg minus 12% = 3.08kg
    assert abs(decision.kept_kg - 3.08) < 0.001, f"Expected 3.08kg, got {decision.kept_kg}kg"
    assert decision.sanction is None, "Should not have sanction below limit"
    print("✓ REQ 1: 5kg limit - below limit catches allowed")


# =============================================================================
# REQUIREMENT 2: Leave 15% untouched (85% collective rule)
# =============================================================================

def test_requirement_2_collective_cap_calculation():
    """REQ 2: Collective cap is correctly calculated as 85% of stock."""
    context = create_test_context(stock_kg=200.0)
    norm = create_test_norm()
    norm.on_round_start(context)

    scratch = context.round_scratch('round_5_limit')
    # 85% of 200kg = 170kg max allowed
    expected_cap = 200.0 * 0.85
    assert scratch['max_allowed_this_round'] == expected_cap, \
        f"Expected cap {expected_cap}, got {scratch['max_allowed_this_round']}"
    print("✓ REQ 2: 85% collective cap calculated correctly")


def test_requirement_2_collective_cap_enforced():
    """REQ 2: Cannot exceed 85% collective cap."""
    context = create_test_context(stock_kg=100.0)
    norm = create_test_norm()
    norm.on_round_start(context)

    # First, have agent_0 take 80kg worth of trips (at 5kg each = 16 trips)
    # But limited by 5kg per trip, so let's fill up the cap
    scratch = context.round_scratch('round_5_limit')
    scratch['round_cumulative_harvest'] = 85.0  # At the 85kg cap

    # Try to fish - should be ineligible
    eligible = norm.is_eligible(context, 'agent_1')
    assert eligible == False, "Should not be eligible when collective cap reached"
    print("✓ REQ 2: Collective cap prevents fishing when reached")


def test_requirement_2_collective_cap_violation():
    """REQ 2: Trying to exceed collective cap triggers violation and penalty."""
    context = create_test_context(stock_kg=20.0)
    norm = create_test_norm()
    norm.on_round_start(context)

    # Cap is 17kg (85% of 20kg)
    # Have agent_0 take 15kg (3 trips at 5kg each)
    for _ in range(3):
        norm.evaluate(context, 'agent_0', raw_kg=5.0, proposed_kg=5.0)

    # Now only 2kg remaining in collective allowance
    # Agent_1 tries to take 5kg - should be limited to 2kg
    decision = norm.evaluate(context, 'agent_1', raw_kg=5.0, proposed_kg=5.0)
    state = context.norm_state('round_5_limit')

    # Should be limited to 2kg (remaining collective allowance) - 12%
    assert abs(decision.kept_kg - 1.76) < 0.001, f"Expected 1.76kg, got {decision.kept_kg}kg"
    assert decision.sanction == 'catch_limit_exceeded', "Should record sanction for exceeding collective cap"
    # Should have penalty trip
    assert state['penalty_trips_pending']['agent_1'] == 1, "Should assign penalty trip"
    print("✓ REQ 2: Violating collective cap triggers penalty")


# =============================================================================
# REQUIREMENT 3 & 4: Penalty trips assigned and enforced
# =============================================================================

def test_requirement_3_penalty_assigned_on_individual_limit_violation():
    """REQ 3: Penalty trip assigned when exceeding 5kg individual limit."""
    context = create_test_context()
    norm = create_test_norm()
    norm.on_round_start(context)

    # Exceed 5kg limit
    norm.evaluate(context, 'agent_0', raw_kg=6.0, proposed_kg=6.0)
    state = context.norm_state('round_5_limit')

    assert state['penalty_trips_pending']['agent_0'] == 1, "Should have 1 penalty trip pending"
    assert state['penalty_trip_kg_owed']['agent_0'] == 1.0, "Should owe 1kg in penalty trips"
    print("✓ REQ 3: Penalty trip assigned for individual limit violation")


def test_requirement_3_penalty_assigned_on_collective_limit_violation():
    """REQ 3: Penalty trip assigned when exceeding collective limit."""
    context = create_test_context(stock_kg=20.0)
    norm = create_test_norm()
    norm.on_round_start(context)

    # Fill up collective allowance
    scratch = context.round_scratch('round_5_limit')
    scratch['round_cumulative_harvest'] = 16.0  # Close to 17kg cap

    # Try to take more than remaining
    norm.evaluate(context, 'agent_0', raw_kg=5.0, proposed_kg=5.0)
    state = context.norm_state('round_5_limit')

    assert state['penalty_trips_pending']['agent_0'] == 1, "Should have 1 penalty trip pending"
    print("✓ REQ 3: Penalty trip assigned for collective limit violation")


def test_requirement_4_penalty_limits_to_1kg():
    """REQ 4: When serving penalty trip, fisher limited to exactly 1kg."""
    context = create_test_context()
    norm = create_test_norm()
    norm.on_round_start(context)

    # Get a penalty
    norm.evaluate(context, 'agent_0', raw_kg=6.0, proposed_kg=6.0)
    state = context.norm_state('round_5_limit')
    assert state['penalty_trips_pending']['agent_0'] == 1

    # Try to catch 5kg with penalty pending
    decision = norm.evaluate(context, 'agent_0', raw_kg=5.0, proposed_kg=5.0)

    # Should only get 1kg minus 12% = 0.88kg
    assert abs(decision.kept_kg - 0.88) < 0.001, f"Expected 0.88kg, got {decision.kept_kg}kg"
    # Penalty should be marked as served
    assert state['penalty_trips_pending']['agent_0'] == 0, "Penalty should be served"
    print("✓ REQ 4: Penalty trip limits catch to 1kg")


def test_requirement_4_multiple_penalties_served_sequentially():
    """REQ 4: Multiple penalties must be served one at a time."""
    context = create_test_context()
    norm = create_test_norm()
    norm.on_round_start(context)

    # Get 2 penalties through two violations
    norm.evaluate(context, 'agent_0', raw_kg=6.0, proposed_kg=6.0)  # First violation
    state = context.norm_state('round_5_limit')
    
    # Serve first penalty
    norm.evaluate(context, 'agent_0', raw_kg=5.0, proposed_kg=5.0)
    assert state['penalty_trips_pending']['agent_0'] == 0
    
    # Second violation
    norm.evaluate(context, 'agent_0', raw_kg=7.0, proposed_kg=7.0)
    assert state['penalty_trips_pending']['agent_0'] == 1
    
    # Serve second penalty
    decision = norm.evaluate(context, 'agent_0', raw_kg=5.0, proposed_kg=5.0)
    assert abs(decision.kept_kg - 0.88) < 0.001, f"Second penalty: Expected 0.88kg, got {decision.kept_kg}kg"
    assert state['penalty_trips_pending']['agent_0'] == 0
    
    # Now normal fishing resumes
    decision = norm.evaluate(context, 'agent_0', raw_kg=4.0, proposed_kg=4.0)
    assert abs(decision.kept_kg - 3.52) < 0.001, f"Normal fishing: Expected 3.52kg, got {decision.kept_kg}kg"
    print("✓ REQ 4: Multiple penalties served sequentially, normal fishing resumes")


def test_requirement_4_penalty_trip_includes_deposit():
    """REQ 4: Even penalty trips require 12% deposit to reserve."""
    context = create_test_context()
    norm = create_test_norm()
    norm.on_round_start(context)

    # Get a penalty
    norm.evaluate(context, 'agent_0', raw_kg=6.0, proposed_kg=6.0)
    initial_reserve = context.norm_state('round_5_limit')['shared_reserve']

    # Serve penalty
    decision = norm.evaluate(context, 'agent_0', raw_kg=5.0, proposed_kg=5.0)
    final_reserve = context.norm_state('round_5_limit')['shared_reserve']

    # Reserve should increase by 12% of 1kg = 0.12kg from penalty trip
    reserve_increase = final_reserve - initial_reserve
    assert abs(reserve_increase - 0.12) < 0.001, f"Expected 0.12kg deposit from penalty, got {reserve_increase}kg"
    print("✓ REQ 4: Penalty trips include 12% reserve deposit")


# =============================================================================
# REQUIREMENT 5: 12% deposit into shared reserve
# =============================================================================

def test_requirement_5_deposit_calculated_correctly():
    """REQ 5: 12% of every kept catch goes to reserve."""
    context = create_test_context()
    norm = create_test_norm()
    norm.on_round_start(context)

    decision = norm.evaluate(context, 'agent_0', raw_kg=4.0, proposed_kg=4.0)
    state = context.norm_state('round_5_limit')

    # 4kg * 12% = 0.48kg to reserve
    assert abs(state['shared_reserve'] - 0.48) < 0.001, f"Expected 0.48kg in reserve, got {state['shared_reserve']}kg"
    # Fisher keeps 4kg * 88% = 3.52kg
    assert abs(decision.kept_kg - 3.52) < 0.001, f"Expected 3.52kg kept, got {decision.kept_kg}kg"
    print("✓ REQ 5: 12% deposit calculated correctly")


def test_requirement_5_deposit_tracked_per_agent():
    """REQ 5: Season deposits tracked per agent."""
    context = create_test_context()
    norm = create_test_norm()
    norm.on_round_start(context)

    norm.evaluate(context, 'agent_0', raw_kg=5.0, proposed_kg=5.0)
    norm.evaluate(context, 'agent_1', raw_kg=5.0, proposed_kg=5.0)
    norm.evaluate(context, 'agent_0', raw_kg=4.0, proposed_kg=4.0)

    state = context.norm_state('round_5_limit')
    
    # agent_0: 5kg + 4kg = 9kg total; 12% = 1.08kg
    assert abs(state['season_deposits']['agent_0'] - 1.08) < 0.001, \
        f"agent_0 deposits: expected 1.08kg, got {state['season_deposits']['agent_0']}kg"
    
    # agent_1: 5kg; 12% = 0.6kg
    assert abs(state['season_deposits']['agent_1'] - 0.6) < 0.001, \
        f"agent_1 deposits: expected 0.6kg, got {state['season_deposits']['agent_1']}kg"
    
    print("✓ REQ 5: Per-agent deposit tracking works correctly")


def test_requirement_5_reserve_accumulates():
    """REQ 5: Shared reserve accumulates from all catches."""
    context = create_test_context()
    norm = create_test_norm()
    norm.on_round_start(context)

    norm.evaluate(context, 'agent_0', raw_kg=5.0, proposed_kg=5.0)  # 0.6kg deposit
    norm.evaluate(context, 'agent_1', raw_kg=5.0, proposed_kg=5.0)  # 0.6kg deposit
    norm.evaluate(context, 'agent_2', raw_kg=3.0, proposed_kg=3.0)  # 0.36kg deposit

    state = context.norm_state('round_5_limit')
    # Total: 0.6 + 0.6 + 0.36 = 1.56kg
    assert abs(state['shared_reserve'] - 1.56) < 0.001, \
        f"Expected 1.56kg total reserve, got {state['shared_reserve']}kg"
    print("✓ REQ 5: Reserve accumulates from multiple catches")


# =============================================================================
# REQUIREMENT 6: Reserve is locked (no withdrawals)
# =============================================================================

def test_requirement_6_no_withdrawal_mechanism():
    """REQ 6: No method exists to withdraw from reserve."""
    norm = create_test_norm()
    
    # Check that the norm class has no withdraw or reduce_reserve methods
    has_withdraw = hasattr(norm, 'withdraw') or hasattr(norm, 'withdraw_from_reserve')
    has_reduce = hasattr(norm, 'reduce_reserve') or hasattr(norm, 'decrease_reserve')
    
    assert not has_withdraw, "Norm should not have withdrawal methods"
    assert not has_reduce, "Norm should not have reserve reduction methods"
    
    # Verify reserve only increases
    context = create_test_context()
    norm.on_round_start(context)
    
    initial_reserve = context.norm_state('round_5_limit')['shared_reserve']
    norm.evaluate(context, 'agent_0', raw_kg=5.0, proposed_kg=5.0)
    final_reserve = context.norm_state('round_5_limit')['shared_reserve']
    
    assert final_reserve > initial_reserve, "Reserve should only increase"
    print("✓ REQ 6: No withdrawal mechanism exists, reserve only accumulates")


def test_requirement_6_reserve_persists_across_rounds():
    """REQ 6: Reserve balance persists and accumulates across rounds."""
    # Simulate round 1
    context1 = create_test_context(round_number=1)
    norm = create_test_norm()
    norm.on_round_start(context1)
    norm.evaluate(context1, 'agent_0', raw_kg=5.0, proposed_kg=5.0)
    reserve_after_r1 = context1.norm_state('round_5_limit')['shared_reserve']
    
    # Simulate round 2
    context2 = create_test_context(round_number=2)
    # Copy state from round 1 to round 2 context
    state2 = context2.norm_state('round_5_limit')
    state2['shared_reserve'] = reserve_after_r1
    
    norm.on_round_start(context2)
    norm.evaluate(context2, 'agent_0', raw_kg=5.0, proposed_kg=5.0)
    reserve_after_r2 = context2.norm_state('round_5_limit')['shared_reserve']
    
    # Reserve should have accumulated
    assert reserve_after_r2 > reserve_after_r1, "Reserve should accumulate across rounds"
    print("✓ REQ 6: Reserve persists and accumulates across rounds")


# =============================================================================
# REQUIREMENT 10: Excess fish returned to lake (forfeited to reserve)
# =============================================================================

def test_requirement_10_excess_forfeited_to_reserve():
    """REQ 10: When fisher exceeds limits, excess is forfeited to reserve."""
    context = create_test_context()
    norm = create_test_norm()
    norm.on_round_start(context)

    # Catch 8kg, limited to 5kg, so 3kg forfeited
    decision = norm.evaluate(context, 'agent_0', raw_kg=8.0, proposed_kg=8.0)
    state = context.norm_state('round_5_limit')

    # Reserve should have: 3kg (forfeited) + 0.6kg (12% deposit) = 3.6kg
    assert abs(state['shared_reserve'] - 3.6) < 0.001, \
        f"Expected 3.6kg in reserve (3kg forfeited + 0.6kg deposit), got {state['shared_reserve']}kg"
    print("✓ REQ 10: Excess catch forfeited to reserve")


def test_requirement_10_forfeiture_note():
    """REQ 10: Note mentions forfeiture of excess to reserve."""
    context = create_test_context()
    norm = create_test_norm()
    norm.on_round_start(context)

    decision = norm.evaluate(context, 'agent_0', raw_kg=8.0, proposed_kg=8.0)

    assert decision.note is not None, "Should have a note"
    assert "forfeit" in decision.note.lower() or "excess" in decision.note.lower(), \
        f"Note should mention forfeiture/excess: {decision.note}"
    print("✓ REQ 10: Forfeiture mentioned in decision note")


# =============================================================================
# ADDITIONAL VERIFICATION: Config and Institution Match
# =============================================================================

def test_config_parameters():
    """Verify config has correct parameters for Round 5."""
    import json
    with open('state/config.json') as f:
        config = json.load(f)
    
    norm_config = config['norms'][0]
    assert norm_config['type'] == 'catch_limit_with_penalty_trips', "Wrong norm type"
    assert norm_config['max_kg_per_trip'] == 5.0, "Wrong max kg per trip"
    assert norm_config['reserve_deposit_percent'] == 0.12, "Wrong reserve deposit percent"
    assert norm_config['min_stock_percent_remaining'] == 0.15, "Wrong min stock percent"
    assert norm_config['penalty_trip_kg'] == 1.0, "Wrong penalty trip kg"
    print("✓ CONFIG: Parameters match Round 5 specification")


def test_institution_registration():
    """Verify norm type is registered in institution."""
    import json
    with open('state/institution.json') as f:
        institution = json.load(f)
    
    assert 'catch_limit_with_penalty_trips' in institution['norm_types'], \
        "Norm type not registered in institution"
    
    norm_type = institution['norm_types']['catch_limit_with_penalty_trips']
    assert '5kg' in norm_type['description'] or '5 kg' in norm_type['description'], \
        "Description should mention 5kg limit"
    assert '12%' in norm_type['description'] or '12 percent' in norm_type['description'], \
        "Description should mention 12% deposit"
    print("✓ INSTITUTION: Norm type correctly registered")


# =============================================================================
# RUN ALL TESTS
# =============================================================================

def run_all_tests():
    """Run all independent evaluator tests."""
    print("=" * 60)
    print("ROUND 5 INDEPENDENT EVALUATION TESTS")
    print("=" * 60)
    
    tests = [
        # Requirement 1: 5kg limit
        test_requirement_1_5kg_limit_exact,
        test_requirement_1_5kg_limit_exceeded,
        test_requirement_1_5kg_limit_below,
        
        # Requirement 2: 85% collective rule
        test_requirement_2_collective_cap_calculation,
        test_requirement_2_collective_cap_enforced,
        test_requirement_2_collective_cap_violation,
        
        # Requirements 3 & 4: Penalty trips
        test_requirement_3_penalty_assigned_on_individual_limit_violation,
        test_requirement_3_penalty_assigned_on_collective_limit_violation,
        test_requirement_4_penalty_limits_to_1kg,
        test_requirement_4_multiple_penalties_served_sequentially,
        test_requirement_4_penalty_trip_includes_deposit,
        
        # Requirement 5: 12% deposit
        test_requirement_5_deposit_calculated_correctly,
        test_requirement_5_deposit_tracked_per_agent,
        test_requirement_5_reserve_accumulates,
        
        # Requirement 6: Reserve locked
        test_requirement_6_no_withdrawal_mechanism,
        test_requirement_6_reserve_persists_across_rounds,
        
        # Requirement 10: Excess forfeited
        test_requirement_10_excess_forfeited_to_reserve,
        test_requirement_10_forfeiture_note,
        
        # Config/Institution
        test_config_parameters,
        test_institution_registration,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: FAILED - {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
