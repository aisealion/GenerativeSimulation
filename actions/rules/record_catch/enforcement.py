"""
Rule to detect violations and enable council enforcement actions
"""
from engine.institution.rules import Rule


class EnforcementRule(Rule):
    """
    Rule that detects violations in catch reporting and enables council enforcement
    """
    type_name = "enforcement"

    def __init__(self, key, params):
        super().__init__(key, params)
    
    def after_agent(self, ctx, agent_id, record_entry):
        """
        Apply the rule to detect violations and potentially trigger enforcement.
        This will be called after a fisher records a catch.
        """
        # Get catch amount from the record
        total_catch = record_entry.get('total_catch_kg', 0)
        
        # Check for different types of violations that would trigger different enforcement
        if total_catch > 2:  # Excessive catch - likely to trigger return excess or fine
            # Flag this record as potentially in violation for council review
            record_entry['_violation_detected'] = True
            record_entry['_violation_type'] = 'excessive_catch'
            record_entry['_enforcement_required'] = True
            record_entry['_council_decision_needed'] = True
            
            # Add severity or magnitude for decision making
            record_entry['_violation_severity'] = 'high'
            record_entry['_catch_amount'] = total_catch
        
        elif total_catch > 1.5:  # Slightly excessive - could trigger a fine
            record_entry['_violation_detected'] = True
            record_entry['_violation_type'] = 'slightly_excessive'
            record_entry['_enforcement_required'] = True
            record_entry['_council_decision_needed'] = True
            
            # Add severity or magnitude for decision making  
            record_entry['_violation_severity'] = 'medium'
            record_entry['_catch_amount'] = total_catch
        
        elif total_catch > 1:  # Marginal - could trigger a warning
            record_entry['_violation_detected'] = True
            record_entry['_violation_type'] = 'marginal_excess'
            record_entry['_enforcement_required'] = True  
            record_entry['_council_decision_needed'] = True
            
            # Add severity or magnitude for decision making
            record_entry['_violation_severity'] = 'low'
            record_entry['_catch_amount'] = total_catch
      
        return record_entry

    def after_action(self, ctx, round_record):
        """
        Post-processing to see if enforcement actions need to be applied
        """
        # Apply enforcement mechanisms based on council decisions
        # This method processes the enforcement decision from the council
        
        if round_record.get('council_enforcement_decisions'):
            enforcement_decisions = round_record['council_enforcement_decisions']
            
            # Process each enforcement decision
            for decision in enforcement_decisions:
                decision_type = decision.get('type')
                fisher_id = decision.get('fisher_id')
                if decision_type == 'return_excess':
                    # Implement return of excess enforcement
                    self._process_return_of_excess(ctx, fisher_id, decision)
                elif decision_type == 'fine':
                    # Implement fine enforcement
                    self._process_fine(ctx, fisher_id, decision) 
                elif decision_type == 'suspension':
                    # Implement suspension enforcement
                    self._process_suspension(ctx, fisher_id, decision)
        
        # Handle council decision-making logic for violations that require decisions
        self._make_council_decisions(ctx, round_record)
        
        return round_record

    def _make_council_decisions(self, ctx, round_record):
        """
        Process the decision-making for council to determine which enforcement 
        to apply (return of excess, fine, or suspension) based on the violation type
        and severity.
        """
        # Create council decisions based on the violations detected
        # This simulates the council reviewing violations and making decisions
        if not round_record.get('council_enforcement_decisions'):
            round_record['council_enforcement_decisions'] = []
        
        # Look for records with violations that need council decision
        for record_entry in round_record.get('records', []):
            if record_entry.get('_council_decision_needed') and record_entry.get('_violation_detected'):
                # Determine the appropriate enforcement based on severity
                severity = record_entry.get('_violation_severity')
                fisher_id = record_entry['fisher_id']
                
                # Council decision-making logic
                if severity == 'high':
                    # High severity violations get more severe penalties
                    enforcement_type = self._select_heavier_enforcement()
                    round_record['council_enforcement_decisions'].append({
                        'type': enforcement_type,
                        'fisher_id': fisher_id,
                        'violation_type': record_entry.get('_violation_type'),
                        'severity': severity,
                        'catch_amount': record_entry.get('_catch_amount')
                    })
                elif severity == 'medium':
                    # Medium severity violations get moderate penalties
                    enforcement_type = self._select_moderate_enforcement()
                    round_record['council_enforcement_decisions'].append({
                        'type': enforcement_type,
                        'fisher_id': fisher_id,
                        'violation_type': record_entry.get('_violation_type'),
                        'severity': severity,
                        'catch_amount': record_entry.get('_catch_amount')
                    })
                elif severity == 'low':
                    # Low severity violations get lighter penalties or warnings
                    enforcement_type = self._select_light_enforcement()
                    round_record['council_enforcement_decisions'].append({
                        'type': enforcement_type,
                        'fisher_id': fisher_id,
                        'violation_type': record_entry.get('_violation_type'),
                        'severity': severity,
                        'catch_amount': record_entry.get('_catch_amount')
                    })

    def _select_heavier_enforcement(self):
        """
        Select a heavier enforcement action (return of excess or fine)
        for high severity violations
        """
        import random
        # Return excess or fine - we'll randomly pick one for now 
        # In a real system, this could be based on a more complex rule.
        return random.choice(['return_excess', 'fine'])

    def _select_moderate_enforcement(self):
        """
        Select a moderate enforcement action (fine or suspension)
        for medium severity violations
        """
        import random
        # Fine or suspension - we'll randomly pick one for now
        return random.choice(['fine', 'suspension'])

    def _select_light_enforcement(self):
        """
        Select a light enforcement action (return of excess or warning)
        for low severity violations
        """
        import random
        # Return of excess for simple cases or warning 
        return random.choice(['return_excess', 'fine'])  # simpler approach

    def _process_return_of_excess(self, ctx, fisher_id, decision):
        """
        Process enforcement decision for return of excess
        """
        # This is where we would actually implement the return of excess mechanism
        # For example, reducing the fisher's catch in the community stock
        # In our simulation, we modify the fisher's community stock or record
        pass

    def _process_fine(self, ctx, fisher_id, decision):
        """
        Process enforcement decision for fine
        """
        # This would apply financial penalty to the fisher
        # Example: reduce payoff or community stock  
        pass

    def _process_suspension(self, ctx, fisher_id, decision):
        """
        Process enforcement decision for suspension
        """
        # This would remove the fisher from fishing rights for a period
        # Example: mark fisher as suspended, prevent them from fishing  
        pass