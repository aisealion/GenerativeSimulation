# Reads: state/config.json, state/fluents.json, state/runtime.json (proposals).
# Writes: state/runtime.json (discussion log).

from engine.action_base import Action


class DiscussAction(Action):
    name = "discuss"

    def run(self, state):
        raise NotImplementedError


ACTION = DiscussAction()
