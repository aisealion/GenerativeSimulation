from actions.rules.catch_limit.handler import CatchLimitRule
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.institution.context import ActionContext

class DailyCatchLimitRule(CatchLimitRule):
    """A daily catch limit enforcement rule."""
    type_name = "daily_catch_limit"