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
#
# llama-3.3-70b-versatile (this constant's original value) was decommissioned
# by Groq mid-build — "does not exist or you do not have access to it." Same
# for llama-3.1-8b-instant, llama3-70b-8192, gemma2-9b-it, and
# deepseek-r1-distill-llama-70b, all of which 404/400 on a real key as of
# 2026-08-17. openai/gpt-oss-120b (OpenAI's open-weight model, Groq-hosted) is
# confirmed live against a real key at time of writing.
GROQ_MODEL = "groq/openai/gpt-oss-120b"
GEMINI_MODEL = "gemini/gemini-flash-lite-latest"

CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
MAX_REBUTTAL_ROUNDS = 2
AMBIGUOUS_CONFIDENCE_LOW = 40
AMBIGUOUS_CONFIDENCE_HIGH = 60
MAX_SEARCH_RESULTS = 5
LLM_MAX_REPAIR_ATTEMPTS = 2

# Requests-per-minute cap shared by all LLM calls, enforced in llm.py. Claims are
# audited concurrently (see graph.py), so without this a text with just 2-3 claims
# can burst past a free-tier RPM quota in seconds.
#
# groq/llama-3.3-70b-versatile (this file's original model) got decommissioned
# by Groq mid-build; its replacement, groq/openai/gpt-oss-120b, has a tighter
# free-tier limit — 25/min (tuned for the old model) still produced a real
# RateLimitError on the judge call partway through a 4-claim run. Dropped to
# 12/min for the new model. If you change GROQ_MODEL, re-verify this number
# with a live run rather than assuming it still holds — Groq's per-model free
# tiers are not uniform and change without notice (see the GROQ_MODEL comment
# above for the full list of models that stopped working during this build).
LLM_MAX_CALLS_PER_MINUTE = 12

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
