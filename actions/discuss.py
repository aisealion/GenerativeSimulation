# Reads: state/config.json, state/fluents.json, state/runtime.json (proposals).
# Writes: state/runtime.json (discussion log).

from engine.phase_base import Phase


class DiscussPhase(Phase):
    name = "discuss"

    def run(self, state):
        raise NotImplementedError


PHASE = DiscussPhase()
