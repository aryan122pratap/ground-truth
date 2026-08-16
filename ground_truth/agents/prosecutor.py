from ground_truth.agents._debater import run_debate_side
from ground_truth.models import Argument, Claim, Stance


def prosecute(claim: Claim, opponent_argument: Argument | None = None) -> Argument:
    return run_debate_side(claim, Stance.REFUTE, "prosecutor", opponent_argument)
