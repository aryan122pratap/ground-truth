import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT_DIR / ".cache"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# Groq is preferred over Gemini when both keys are present: its free tier is
# dramatically faster (that's Groq's whole product — custom inference hardware)
# and far more generous than Gemini's, which we hit a hard wall on mid-build
# (gemini-2.0-flash retired outright; its replacement alias' free tier turned out
# to be a 20 requests/DAY cap, trivially exhausted by one multi-agent debate).
# Gemini stays configured as the fallback for whoever runs this with only a
# Gemini key.
GROQ_MODEL = "groq/llama-3.3-70b-versatile"
GEMINI_MODEL = "gemini/gemini-flash-lite-latest"

CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
MAX_REBUTTAL_ROUNDS = 2
AMBIGUOUS_CONFIDENCE_LOW = 40
AMBIGUOUS_CONFIDENCE_HIGH = 60
MAX_SEARCH_RESULTS = 5
LLM_MAX_REPAIR_ATTEMPTS = 2

# Requests-per-minute cap shared by all LLM calls, enforced in llm.py. Claims are
# audited concurrently (see graph.py), so without this a text with just 2-3 claims
# can burst past a free-tier RPM quota in seconds. Tuned against real keys:
# gemini-flash-lite-latest's binding constraint was a per-DAY quota, not RPM
# (15/min ran clean); groq/llama-3.3-70b-versatile's published free tier is
# ~30 RPM. At 15/min a clean 5-claim run took 190s, almost entirely our own
# throttling wait rather than model latency; at 25/min (still under Groq's
# limit) a 3-checkable-claim run completed in 67s with zero rate-limit errors —
# right at the spec's 60s/5-claim target. Lower this if your key's tier is
# tighter, raise it if you're on a paid tier.
LLM_MAX_CALLS_PER_MINUTE = 25

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
    if get_secret("GROQ_API_KEY"):
        return GROQ_MODEL
    if get_secret("GEMINI_API_KEY"):
        return GEMINI_MODEL
    return GROQ_MODEL


def ensure_llm_env() -> None:
    """Copy secrets into os.environ so litellm (which reads env vars) can see them."""
    for key in ("GEMINI_API_KEY", "GROQ_API_KEY", "TAVILY_API_KEY"):
        value = get_secret(key)
        if value:
            os.environ[key] = value
