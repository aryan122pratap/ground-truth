import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT_DIR / ".cache"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

DEFAULT_MODEL = "gemini/gemini-2.0-flash"
FALLBACK_MODEL = "groq/llama-3.3-70b-versatile"

CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
MAX_REBUTTAL_ROUNDS = 2
AMBIGUOUS_CONFIDENCE_LOW = 40
AMBIGUOUS_CONFIDENCE_HIGH = 60
MAX_SEARCH_RESULTS = 5
LLM_MAX_REPAIR_ATTEMPTS = 2

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
