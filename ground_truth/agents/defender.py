from ground_truth.agents._debater import run_debate_side
from ground_truth.models import Argument, Claim, Stance


def defend(claim: Claim, opponent_argument: Argument | None = None) -> Argument:
    return run_debate_side(claim, Stance.SUPPORT, "defender", opponent_argument)
