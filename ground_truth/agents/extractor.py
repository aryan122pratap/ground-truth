from pydantic import BaseModel

from ground_truth.llm import load_prompt, structured_call
from ground_truth.models import Claim


class _ClaimList(BaseModel):
    claims: list[Claim]


def extract_claims(text: str) -> list[Claim]:
    prompt = load_prompt("extractor").format(text=text)
    result = structured_call(prompt, _ClaimList)
    # Reassign ids sequentially so downstream code can rely on c1..cN regardless
    # of what the model produced.
    return [
        claim.model_copy(update={"id": f"c{i + 1}"})
        for i, claim in enumerate(result.claims)
    ]
