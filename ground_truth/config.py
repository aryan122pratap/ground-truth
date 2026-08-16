import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT_DIR / ".cache"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# gemini-2.0-flash was retired by Google and now 404s ("no longer available to
# new users"). gemini-flash-latest currently resolves to gemini-3.7-flash, whose
# free tier is GenerateRequestsPerDayPerProjectPerModel-FreeTier = 20/day — easy
# to exhaust with a multi-agent debate (each claim needs ~5 calls per round).
# gemini-flash-lite-latest is a separate model with its own (in testing, much
# less immediately exhausted) daily quota, so it's the safer default for a
# zero-paid-key demo. Both are Google-maintained aliases that track whatever
# model Google currently recommends, so this shouldn't go stale the way a pinned
# version number did.
DEFAULT_MODEL = "gemini/gemini-flash-lite-latest"
FALLBACK_MODEL = "groq/llama-3.3-70b-versatile"

CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
MAX_REBUTTAL_ROUNDS = 2
AMBIGUOUS_CONFIDENCE_LOW = 40
AMBIGUOUS_CONFIDENCE_HIGH = 60
MAX_SEARCH_RESULTS = 5
LLM_MAX_REPAIR_ATTEMPTS = 2

# Requests-per-minute cap shared by all LLM calls, enforced in llm.py. Claims are
# audited concurrently (see graph.py), so without this a text with just 2-3 claims
# can burst past a free-tier RPM quota in seconds. In testing against a real
# gemini-flash-lite-latest free-tier key, the binding constraint turned out to be
# a per-DAY quota on the full (non-lite) flash model, not a per-minute one on the
# lite model — 8/min was overly conservative and became the main latency
# bottleneck once that was fixed (a 4-claim audit at 8/min took ~150s of pure
# throttling wait, matching ~20 calls / 8 per min almost exactly). At 15/min the
# same class of 4-claim audit ran clean with zero rate-limit errors in ~75-135s
# depending on how many claims needed the rebuttal round. Lower this if your
# key's tier is tighter, raise it if you're on a paid tier.
LLM_MAX_CALLS_PER_MINUTE = 15

# Credibility heuristic domain lists — see search.py. Documented as a heuristic,
# not ground truth: a simple signal to bias the judge, not an authority ranking.
HIGH_CREDIBILITY_TLDS = (".gov", ".edu", ".int")
HIGH_CREDIBILITY_DOMAINS = {
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "bbc.co.uk",
    "nature.com",
    "science.org",
    "nih.gov",
    "who.int",
    "arxiv.org",
}
MEDIUM_CREDIBILITY_DOMAINS = {"wikipedia.org"}
LOW_CREDIBILITY_DOMAIN_PATTERNS = (
    "buzzfeed",
    "clickbait",
    "listicle",
    "contentfarm",
)


def get_secret(key: str) -> str | None:
    """Read a config value from Streamlit secrets, falling back to the environment."""
    try:
        import streamlit as st

        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.environ.get(key)


def select_model() -> str:
    if get_secret("GEMINI_API_KEY"):
        return DEFAULT_MODEL
    if get_secret("GROQ_API_KEY"):
        return FALLBACK_MODEL
    return DEFAULT_MODEL


def ensure_llm_env() -> None:
    """Copy secrets into os.environ so litellm (which reads env vars) can see them."""
    for key in ("GEMINI_API_KEY", "GROQ_API_KEY", "TAVILY_API_KEY"):
        value = get_secret(key)
        if value:
            os.environ[key] = value
