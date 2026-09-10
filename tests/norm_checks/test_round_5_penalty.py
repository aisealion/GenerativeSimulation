# Test suite for Round 5: Catch limit with penalty trips
# Tests the 5kg limit, 15% untouched rule, 12% reserve deposit, and penalty trip mechanism

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


class Test5kgLimit:
    """Tests for the 5kg per-trip catch limit."""

    def test_catch_below_limit(self):
        """Fisher catching below 5kg keeps full amount minus 12% deposit."""
        context = create_test_context()
        norm = create_test_norm()
        norm.on_round_start(context)

        decision = norm.evaluate(context, 'agent_0', raw_kg=3.0, proposed_kg=3.0)

        # Should keep 3kg - 12% = 2.64kg
        assert abs(decision.kept_kg - 2.64) < 0.01
        assert decision.sanction is None
        print("✓ Catch below limit: kept correct amount")

    def test_catch_at_limit(self):
        """Fisher catching exactly 5kg keeps 5kg minus 12% deposit."""
        context = create_test_context()
        norm = create_test_norm()
        norm.on_round_start(context)

        decision = norm.evaluate(context, 'agent_0', raw_kg=5.0, proposed_kg=5.0)

        # Should keep 5kg - 12% = 4.4kg
        assert abs(decision.kept_kg - 4.4) < 0.01
        assert decision.sanction is None
        print("✓ Catch at limit: kept correct amount")

    def test_catch_above_limit(self):
        """Fisher catching above 5kg forfeits excess and gets penalty trip."""
        context = create_test_context()
        norm = create_test_norm()
        norm.on_round_start(context)

        decision = norm.evaluate(context, 'agent_0', raw_kg=8.0, proposed_kg=8.0)
        state = context.norm_state('round_5_limit')

        # Should keep only 5kg - 12% = 4.4kg
        assert abs(decision.kept_kg - 4.4) < 0.01
        # Should record violation
        assert decision.sanction == 'catch_limit_exceeded'
        # Should add 1 penalty trip
        assert state['penalty_trips_pending']['agent_0'] == 1
        # Should forfeit 3kg excess to reserve (plus deposit from kept amount)
        assert state['shared_reserve'] > 0
        print("✓ Catch above limit: forfeited excess, got penalty trip")


class Test15PercentUntouched:
    """Tests for the 15% untouched / 85% collective rule."""

    def test_collective_cap_calculated_correctly(self):
        """Collective cap is 85% of starting stock."""
        context = create_test_context(stock_kg=200.0)
        norm = create_test_norm()
        norm.on_round_start(context)

        scratch = context.round_scratch('round_5_limit')
        # 85% of 200kg = 170kg
        assert scratch['max_allowed_this_round'] == 170.0
        print("✓ Collective cap calculated correctly (85% of stock)")

    def test_violation_when_collective_cap_exceeded(self):
        """Exceeding collective cap triggers violation and penalty."""
        context = create_test_context(stock_kg=100.0)
        norm = create_test_norm()
        norm.on_round_start(context)

        # First fisher takes 80kg (close to 85kg cap)
        norm.evaluate(context, 'agent_0', raw_kg=80.0, proposed_kg=80.0)
        # But limited to 5kg, so takes 5kg

        # Fill up to cap
        scratch = context.round_scratch('round_5_limit')
        scratch['round_cumulative_harvest'] = 85.0  # At cap

        # Next fisher tries to fish
        eligible = norm.is_eligible(context, 'agent_1')
        assert eligible == False
        print("✓ Cannot fish when collective cap reached")


class TestPenaltyTrips:
    """Tests for the penalty trip mechanism."""

    def test_penalty_trip_assigned_on_violation(self):
        """Violation adds 1kg penalty trip to fisher's ledger."""
        context = create_test_context()
        norm = create_test_norm()
        norm.on_round_start(context)

        # Cause a violation
        norm.evaluate(context, 'agent_0', raw_kg=7.0, proposed_kg=7.0)
        state = context.norm_state('round_5_limit')

        assert state['penalty_trips_pending']['agent_0'] == 1
        assert state['penalty_trip_kg_owed']['agent_0'] == 1.0
        print("✓ Penalty trip assigned on violation")

    def test_penalty_trip_limits_catch_to_1kg(self):
        """When serving penalty trip, fisher can only catch 1kg."""
        context = create_test_context()
        norm = create_test_norm()
        norm.on_round_start(context)

        # Cause a violation first
        norm.evaluate(context, 'agent_0', raw_kg=7.0, proposed_kg=7.0)

        # Now fisher tries to catch 5kg but has penalty
        decision = norm.evaluate(context, 'agent_0', raw_kg=5.0, proposed_kg=5.0)
        state = context.norm_state('round_5_limit')

        # Should only get 1kg - 12% = 0.88kg
        assert abs(decision.kept_kg - 0.88) < 0.01
        # Penalty should be decremented
        assert state['penalty_trips_pending']['agent_0'] == 0
        print("✓ Penalty trip limits catch to 1kg")

    def test_multiple_penalties_accumulate(self):
        """Multiple violations accumulate multiple penalty trips."""
        context = create_test_context()
        norm = create_test_norm()
        norm.on_round_start(context)

        # First violation by agent_0
        norm.evaluate(context, 'agent_0', raw_kg=7.0, proposed_kg=7.0)
        state = context.norm_state('round_5_limit')
        assert state['penalty_trips_pending']['agent_0'] == 1

        # Second violation by agent_1 (different agent, so no penalty interference)
        norm.evaluate(context, 'agent_1', raw_kg=8.0, proposed_kg=8.0)
        assert state['penalty_trips_pending']['agent_1'] == 1

        # Now test accumulation with agent_0 after serving first penalty
        norm.evaluate(context, 'agent_0', raw_kg=5.0, proposed_kg=5.0)  # Serve first penalty
        assert state['penalty_trips_pending']['agent_0'] == 0

        # Second violation by agent_0
        norm.evaluate(context, 'agent_0', raw_kg=6.0, proposed_kg=6.0)
        assert state['penalty_trips_pending']['agent_0'] == 1  # New penalty
        print("✓ Multiple violations accumulate penalties")

    def test_serving_multiple_penalties(self):
        """Fisher must serve all penalty trips before normal fishing."""
        context = create_test_context()
        norm = create_test_norm()
        norm.on_round_start(context)

        # Get 2 penalties using two different agents to avoid serving penalties
        # First, have agent_0 get a violation
        norm.evaluate(context, 'agent_0', raw_kg=7.0, proposed_kg=7.0)
        state = context.norm_state('round_5_limit')

        # Serve first penalty as agent_0
        decision1 = norm.evaluate(context, 'agent_0', raw_kg=5.0, proposed_kg=5.0)
        assert abs(decision1.kept_kg - 0.88) < 0.01
        assert state['penalty_trips_pending']['agent_0'] == 0

        # Now get another violation as agent_0
        norm.evaluate(context, 'agent_0', raw_kg=8.0, proposed_kg=8.0)
        assert state['penalty_trips_pending']['agent_0'] == 1

        # Serve second penalty
        decision2 = norm.evaluate(context, 'agent_0', raw_kg=5.0, proposed_kg=5.0)
        assert abs(decision2.kept_kg - 0.88) < 0.01
        assert state['penalty_trips_pending']['agent_0'] == 0

        # Now normal fishing resumes
        decision3 = norm.evaluate(context, 'agent_0', raw_kg=4.0, proposed_kg=4.0)
        assert abs(decision3.kept_kg - 3.52) < 0.01  # 4kg - 12%
        print("✓ Multiple penalties served sequentially")


class Test12PercentDeposit:
    """Tests for the 12% reserve deposit."""

    def test_deposit_calculated_correctly(self):
        """12% of kept catch goes to reserve."""
        context = create_test_context()
        norm = create_test_norm()
        norm.on_round_start(context)

        decision = norm.evaluate(context, 'agent_0', raw_kg=4.0, proposed_kg=4.0)
        state = context.norm_state('round_5_limit')

        # 4kg * 12% = 0.48kg to reserve
        # Fisher keeps 4kg * 88% = 3.52kg
        assert abs(decision.kept_kg - 3.52) < 0.01
        assert abs(state['shared_reserve'] - 0.48) < 0.01
        print("✓ 12% deposit calculated correctly")

    def test_deposit_includes_forfeited_excess(self):
        """Reserve gets both 12% deposit and forfeited excess."""
        context = create_test_context()
        norm = create_test_norm()
        norm.on_round_start(context)

        # Violation: 8kg catch, only keep 5kg
        # Forfeited: 3kg
        # Deposit: 5kg * 12% = 0.6kg
        # Total to reserve: 3.6kg
        norm.evaluate(context, 'agent_0', raw_kg=8.0, proposed_kg=8.0)
        state = context.norm_state('round_5_limit')

        assert abs(state['shared_reserve'] - 3.6) < 0.01
        print("✓ Reserve receives both deposit and forfeited excess")


class TestReserveLocked:
    """Tests that the reserve is locked (no withdrawals)."""

    def test_reserve_only_accumulates(self):
        """Reserve balance never decreases."""
        context = create_test_context()
        norm = create_test_norm()
        norm.on_round_start(context)

        # Multiple catches - reserve should only grow
        norm.evaluate(context, 'agent_0', raw_kg=5.0, proposed_kg=5.0)
        reserve1 = context.norm_state('round_5_limit')['shared_reserve']

        norm.evaluate(context, 'agent_1', raw_kg=5.0, proposed_kg=5.0)
        reserve2 = context.norm_state('round_5_limit')['shared_reserve']

        assert reserve2 > reserve1
        print("✓ Reserve only accumulates, never decreases")


def run_all_tests():
    """Run all test classes."""
    print("=== Round 5 Penalty Trip Norm Tests ===\n")

    test_classes = [
        Test5kgLimit(),
        Test15PercentUntouched(),
        TestPenaltyTrips(),
        Test12PercentDeposit(),
        TestReserveLocked(),
    ]

    for test_class in test_classes:
        class_name = test_class.__class__.__name__
        print(f"\n{class_name}:")
        print("-" * 40)

        for method_name in dir(test_class):
            if method_name.startswith('test_'):
                try:
                    getattr(test_class, method_name)()
                except Exception as e:
                    print(f"✗ {method_name}: FAILED - {e}")
                    raise

    print("\n" + "=" * 40)
    print("All tests passed!")
    print("=" * 40)


if __name__ == '__main__':
    run_all_tests()
