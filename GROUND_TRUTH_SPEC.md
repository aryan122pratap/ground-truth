# Ground Truth — Build Specification

> **For the coding agent:** This is a complete, self-contained build spec. Build the entire project end-to-end without asking clarifying questions. Where a decision is ambiguous, choose the option that keeps the demo working with zero paid API keys. Commit in logical chunks. When done, the repo must run with `streamlit run app.py` after `pip install -r requirements.txt` and a `.env` file.

---

## 1. What we are building

**Ground Truth** is an adversarial multi-agent fact auditor.

A user pastes any text — a news article, a LinkedIn post, a research abstract, a tweet thread. The system:

1. Breaks the text into **atomic, checkable claims**
2. Runs an **adversarial debate** on each claim: one agent argues it is false, one argues it is true, both must cite real web evidence
3. A **Judge** agent weighs both cases and returns a confidence score 0–100 with reasoning and citations
4. Renders the **original text back to the user, sentence by sentence, color-coded by confidence** — green (supported), amber (disputed/unverifiable), red (contradicted). Clicking any sentence opens the full debate transcript and sources.

The core differentiator versus a normal RAG chatbot is the **debate topology**: evidence is gathered by two agents with opposing mandates, which surfaces contradicting sources that a single "research this claim" agent systematically misses.

### Non-goals (do not build these)
- No user accounts, no login, no database of users
- No fine-tuning, no model training
- No browser extension (a stretch goal at most)
- No paid infrastructure. Everything must run on Streamlit Community Cloud free tier.

---

## 2. Tech stack (use exactly this)

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.11 | |
| Agent orchestration | **LangGraph** (`langgraph`) | Explicit state graph — the graph itself is a selling point, render it in the README |
| LLM client | **LiteLLM** (`litellm`) | One interface, swappable providers. Do NOT hardcode OpenAI. |
| Default model | `gemini/gemini-2.0-flash` | Generous free tier. Fall back to `groq/llama-3.3-70b-versatile` if key present. |
| Web search | **Tavily** (`tavily-python`) primary, **DuckDuckGo** (`ddgs`) fallback | Tavily free tier is 1000 searches/mo; DDGS needs no key so the demo never hard-fails |
| UI | **Streamlit** | Single `app.py` entry point |
| Caching | `diskcache` | Cache search results + LLM calls by hash so repeat demos are instant and free |
| Data models | **Pydantic v2** | All agent outputs are validated Pydantic models, never raw strings |
| Testing | `pytest` | |
| Deploy | Streamlit Community Cloud | Secrets via `st.secrets`, falling back to `os.environ` |

Add `python-dotenv`, `tenacity` (retries), `plotly` (one chart).

---

## 3. Repository layout

```
ground-truth/
├── app.py                     # Streamlit entry point (UI only, no logic)
├── ground_truth/
│   ├── __init__.py
│   ├── config.py              # env/secrets loading, model selection, constants
│   ├── models.py              # Pydantic: Claim, Evidence, Argument, Verdict, AuditResult
│   ├── llm.py                 # LiteLLM wrapper: structured_call(prompt, schema) -> Pydantic
│   ├── search.py              # Tavily -> DDGS fallback, cached, returns list[Evidence]
│   ├── graph.py               # LangGraph definition + compiled app
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── extractor.py       # text -> list[Claim]
│   │   ├── prosecutor.py      # claim -> Argument(stance=REFUTE)
│   │   ├── defender.py        # claim -> Argument(stance=SUPPORT)
│   │   └── judge.py           # claim + both Arguments -> Verdict
│   ├── prompts/               # .md files, one per agent. NEVER inline long prompts in .py
│   │   ├── extractor.md
│   │   ├── prosecutor.md
│   │   ├── defender.md
│   │   └── judge.md
│   └── render.py              # AuditResult -> annotated HTML for Streamlit
├── tests/
│   ├── test_models.py
│   ├── test_extractor.py      # mocked LLM
│   ├── test_judge.py          # mocked LLM, asserts score bounds + citation presence
│   └── fixtures/sample_texts.py
├── assets/
│   └── architecture.png       # generated graph diagram (see §9)
├── .env.example
├── .streamlit/config.toml     # theme
├── requirements.txt
├── README.md
└── LICENSE                    # MIT
```

---

## 4. Data models (`models.py`)

Implement these exactly. Everything downstream depends on them.

```python
class Stance(str, Enum):
    SUPPORT = "support"
    REFUTE  = "refute"

class Evidence(BaseModel):
    url: str
    title: str
    snippet: str
    source_domain: str
    published: str | None = None
    credibility: float = Field(ge=0, le=1, default=0.5)  # heuristic, see §6

class Claim(BaseModel):
    id: str                     # "c1", "c2"...
    text: str                   # the atomic, self-contained restatement
    original_sentence: str      # verbatim span from input, for highlighting
    checkable: bool             # False for opinions/predictions -> skip debate
    claim_type: Literal["factual", "statistical", "causal", "opinion", "prediction"]

class Argument(BaseModel):
    stance: Stance
    reasoning: str
    evidence: list[Evidence]
    strength: float = Field(ge=0, le=1)   # agent's self-assessed case strength

class Verdict(BaseModel):
    claim_id: str
    confidence: int = Field(ge=0, le=100)  # 100 = certainly true
    label: Literal["supported", "disputed", "contradicted", "unverifiable"]
    reasoning: str
    key_citations: list[Evidence]
    dissent: str        # strongest surviving point from the LOSING side. Required, never empty.

class AuditResult(BaseModel):
    original_text: str
    claims: list[Claim]
    arguments: dict[str, list[Argument]]   # claim_id -> [prosecution, defense]
    verdicts: list[Verdict]
    elapsed_seconds: float
    model_used: str
```

**The `dissent` field is the signature feature.** Even when the Judge is confident, it must state the best counter-argument. This is what makes the output feel intellectually honest rather than an LLM rubber-stamp. Do not let it be optional or empty — validate it.

---

## 5. The LangGraph (`graph.py`)

State: `AuditState(TypedDict)` carrying `raw_text`, `claims`, `arguments`, `verdicts`, `errors`.

```
        START
          │
    ┌─────▼─────┐
    │ extractor │   text -> claims[]
    └─────┬─────┘
          │  conditional: if no checkable claims -> END
    ┌─────▼──────────────┐
    │  fan_out_claims    │  Send() one branch per checkable claim
    └─────┬──────────────┘
          │
    ┌─────┴──────┐              (these two run in PARALLEL)
    ▼            ▼
┌────────┐  ┌─────────┐
│prosecu │  │defender │   each: independent web search + argument
│  tor   │  │         │
└────┬───┘  └────┬────┘
     └─────┬─────┘
      ┌────▼────┐
      │  judge  │   sees BOTH arguments, never the raw text bias
      └────┬────┘
           │  conditional: if confidence in 40..60 AND round < 2 -> rebuttal loop
           │              else -> aggregate
      ┌────▼────┐
      │aggregate│
      └────┬────┘
           ▼
          END
```

Implementation notes:
- Use LangGraph's `Send` API for the per-claim fan-out so claims are audited concurrently.
- Prosecutor and Defender must run in parallel branches and **must not see each other's output** in round 1. This isolation is what makes the evidence genuinely independent.
- **Rebuttal loop:** if the Judge's confidence lands in the ambiguous 40–60 band, run one more round where each side *does* see the opponent's argument and may search again to rebut. Cap at 2 rounds total — this is a hard limit, enforce it in the conditional edge, not in a prompt.
- Every node wraps its LLM call in `tenacity` retry (3 attempts, exponential backoff) and writes failures into `state["errors"]` rather than raising. A single failed claim must never kill the whole audit.

---

## 6. Search layer (`search.py`)

- `search(query: str, max_results: int = 5) -> list[Evidence]`
- Try Tavily if `TAVILY_API_KEY` present; on any exception or missing key, fall back to `ddgs`.
- Cache on `sha256(query)` via `diskcache` with a 7-day TTL. Cache directory `.cache/` — gitignore it.
- **Credibility heuristic** (keep it simple and document it honestly in the README as a heuristic, not ground truth):
  - `.gov`, `.edu`, `.int` → 0.9
  - Known reference/major-wire domains (reuters, apnews, bbc, nature, science, nih, who, arxiv) → 0.8
  - Wikipedia → 0.6
  - Everything else → 0.5
  - Known content-farm / SEO-spam patterns → 0.3
  Put the domain lists in `config.py` as editable constants.
- Prosecutor and Defender must generate **different queries** for the same claim. Prosecutor's prompt asks for queries likely to surface refutation ("X debunked", "X false", "criticism of X"); Defender's asks for confirmation. This asymmetry is the whole point.

---

## 7. Prompts (`prompts/*.md`)

Load them from disk with a small `load_prompt(name)` helper. Each uses `{placeholders}` filled via `.format()`.

**extractor.md** — Instruct: split into atomic claims, each independently checkable and self-contained (resolve pronouns; "he founded it in 2019" → "Elon Musk founded SpaceX in 2019"). Classify each as factual/statistical/causal/opinion/prediction. Mark opinions and predictions `checkable: false`. Preserve the exact original sentence for highlighting. Return JSON matching the `Claim` schema.

**prosecutor.md** — "You are a hostile fact-checker. Your job is to find any reason this claim is false, misleading, outdated, or missing crucial context. Search aggressively for contradicting evidence. If after searching you find no contradicting evidence, say so honestly and set strength low — do NOT fabricate a case." That last sentence is essential; without it the model invents objections.

**defender.md** — Mirror image. Same honesty clause.

**judge.md** — "You receive two adversarial briefs. Weigh evidence quality, source credibility, and recency — not rhetorical confidence. A single high-credibility source outweighs three low-credibility ones. Output confidence 0–100 where 100 means certainly true. You MUST populate `dissent` with the strongest surviving point from whichever side you ruled against. If both sides found no real evidence, label `unverifiable` and set confidence near 50."

Keep every prompt under ~400 words. Include one worked example in each.

---

## 8. Streamlit UI (`app.py`)

Layout, top to bottom:

1. **Header** — title, one-line pitch, GitHub link.
2. **Input** — big text area + three "Try an example" buttons preloaded with sample texts (one mostly-true, one mixed, one full of falsehoods). The examples matter enormously for the demo: a visitor with nothing to paste must still see the product work in one click.
3. **Run button** → shows a live status area streaming graph progress ("Extracting claims… Auditing claim 2/5… Judge deliberating…"). Use `st.status()` and LangGraph's streaming so it doesn't look frozen. A 40-second silent spinner is what kills these demos.
4. **Results — Annotated Text.** The original text re-rendered, each audited sentence wrapped in a span with a background color scaled by confidence. Use a colorblind-safe scale: teal `#0d9488` (supported), amber `#d97706` (disputed), rose `#e11d48` (contradicted), grey (unverifiable/skipped). Never rely on color alone — append a small superscript badge with the numeric score so it's readable in greyscale.
5. **Verdict cards** — one expander per claim: score, label, judge reasoning, the `dissent` block visually distinguished, then the prosecution and defense briefs side by side in two columns with clickable source links.
6. **Summary strip** — overall "truthfulness score" (evidence-weighted mean), claim count by label, and one Plotly horizontal bar of per-claim confidence.
7. **Footer disclaimer** — plainly state this is an AI-assisted research aid, that scores are model judgments over web search results, and that it is not a substitute for human fact-checking. Include this. It costs nothing and it signals engineering maturity to anyone senior who looks at the project.

Theme: dark, in `.streamlit/config.toml`. Keep the type large and the layout wide.

---

## 9. README.md (this is half the value of the project — do not rush it)

Must contain, in order:

1. One-sentence pitch + live demo badge/link + a screenshot-sized **animated GIF** of an audit running (leave a placeholder `assets/demo.gif` and a `TODO` note for the human to record it)
2. **The problem**: single-agent fact checkers inherit the confirmation bias of one search query. Adversarial evidence gathering surfaces contradictions that confirmation-seeking retrieval misses. Say this crisply in three sentences.
3. **Architecture diagram** — generate it programmatically from the compiled LangGraph (`graph.get_graph().draw_mermaid_png()`), save to `assets/architecture.png`, and also embed the Mermaid source inline so it renders on GitHub.
4. **How the debate works** — walk one real claim through prosecution → defense → verdict, with actual output. Concrete beats abstract.
5. **Quickstart** — clone, `pip install -r requirements.txt`, copy `.env.example`, `streamlit run app.py`. Must work with zero API keys except one free LLM key.
6. **Design decisions & tradeoffs** — a short honest section: why the rebuttal loop is capped at 2 rounds (cost/latency vs. marginal accuracy), why the credibility score is a heuristic, why claims are audited in parallel. Recruiters read this section. It's where you stop looking like a tutorial-follower.
7. **Limitations** — model hallucination in reasoning, search index recency, no paywalled sources, English-only. Be direct about them.
8. **Roadmap** — browser extension, PDF ingest, local Ollama support.

Write it in plain, direct prose. No emoji headers, no marketing adjectives, no "🚀 revolutionary".

---

## 10. Build order (follow this sequence)

1. Scaffold repo, `requirements.txt`, `.env.example`, `.gitignore`, MIT license
2. `models.py` + `tests/test_models.py` — get the contracts right before any agent exists
3. `config.py`, `llm.py` (structured output via LiteLLM + Pydantic, with a JSON-repair retry), `search.py` with cache and fallback
4. `extractor.py` + prompt + test with mocked LLM
5. `prosecutor.py`, `defender.py`, `judge.py` + prompts
6. `graph.py` — wire the LangGraph, verify with a CLI smoke script `scripts/run_cli.py "some text"` before touching Streamlit
7. `render.py` + `app.py`
8. Examples, Plotly summary, streaming status
9. Generate architecture diagram, write README
10. Full test pass, `ruff` clean, final manual run on all three example texts

Commit after each numbered step with a clear message.

---

## 11. Definition of done

- [ ] `pip install -r requirements.txt && streamlit run app.py` works from a clean clone
- [ ] All three example texts produce sensible, differentiated results
- [ ] Every verdict has at least one real, clickable citation URL
- [ ] Every verdict has a non-empty `dissent`
- [ ] A failing search or LLM call degrades gracefully — no stack trace ever reaches the UI
- [ ] `pytest` passes; no test requires a live API key
- [ ] README complete with architecture diagram rendering on GitHub
- [ ] Total cold-run latency on a 5-claim text under ~60s

---

## 12. Deployment

1. Push to GitHub, public, repo name `ground-truth`
2. share.streamlit.io → deploy from repo, main branch, `app.py`
3. Add `GEMINI_API_KEY` and optionally `TAVILY_API_KEY` in Streamlit secrets
4. Put the live URL in the GitHub repo's About section and at the top of the README
