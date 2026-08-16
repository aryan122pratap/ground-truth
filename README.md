# Ground Truth

Adversarial multi-agent fact auditor — two AI agents argue for and against every claim
in a piece of text, and a judge scores each one with citations and an honest dissent.

**Live demo:** not yet deployed — see [Deployment](#deployment) below. Once deployed,
the Streamlit Community Cloud URL goes here and in the GitHub repo's About section.

![demo](assets/demo.gif)
<!-- TODO(human): record a ~20s GIF of a real audit run (paste an example, click Run,
     let the status stream and the annotated text render) and save it to
     assets/demo.gif. Placeholder left intentionally — see §9 of the build spec. -->

## The problem

A single-agent fact checker inherits the confirmation bias of whatever search query it
happens to write — ask it to "research this claim" and it tends to find sources that
agree with the claim's framing, not sources that challenge it. Ground Truth instead runs
two agents with opposing mandates against the same claim: a prosecutor searching
specifically for refutation, and a defender searching specifically for confirmation.
Adversarial evidence gathering surfaces contradictions that a single confirmation-seeking
retrieval pass systematically misses, and a judge that has to state the losing side's
strongest point (the `dissent` field) can't quietly rubber-stamp a claim either.

## Architecture

Ground Truth is a [LangGraph](https://github.com/langchain-ai/langgraph) state machine.
The top-level graph extracts claims, then fans out one subgraph invocation per checkable
claim (via `Send`) so claims are audited concurrently:

![architecture](assets/architecture.png)

```mermaid
graph TD;
	__start__([<p>__start__</p>]):::first
	extractor(extractor)
	debate_claim(debate_claim)
	aggregate(aggregate)
	__end__([<p>__end__</p>]):::last
	__start__ --> extractor;
	debate_claim --> aggregate;
	extractor -.-> __end__;
	extractor -.-> debate_claim;
	aggregate --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```

Each `debate_claim` invocation runs its own compiled subgraph — this is the real
adversarial core, also rendered straight from the compiled graph:

![claim subgraph](assets/claim_subgraph.png)

```mermaid
graph TD;
	__start__([<p>__start__</p>]):::first
	prosecute_node(prosecute_node)
	defend_node(defend_node)
	judge_node(judge_node)
	__end__([<p>__end__</p>]):::last
	__start__ --> defend_node;
	__start__ --> prosecute_node;
	defend_node --> judge_node;
	judge_node -.-> __end__;
	judge_node -.-> defend_node;
	judge_node -.-> prosecute_node;
	prosecute_node --> judge_node;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```

`prosecute_node` and `defend_node` run in parallel and, in round 1, never see each
other's output — that isolation is what keeps the evidence genuinely independent. If the
judge's confidence lands in the ambiguous 40-60 band, `judge_node` routes back to both
nodes for one rebuttal round where each side *does* see the opponent's argument and may
search again. The loop is capped at `MAX_REBUTTAL_ROUNDS = 2` in the routing function
itself ([graph.py](ground_truth/graph.py)), not in a prompt.

Both diagrams are regenerated straight from the compiled graph objects with
`python scripts/generate_diagram.py` — there is no hand-drawn version to go stale.

## How the debate works

This is real, live-captured output from `scripts/run_cli.py` (`gemini/gemini-flash-lite-latest`,
free tier) auditing the "Mixed" example, for the extracted claim *"SpaceX's Falcon 9
rocket achieved reflight in 2017."* The prosecutor searched for anything that would
refute or complicate the claim and came back empty; the defender found wire-service and
encyclopedia coverage of the March 2017 SES-10 mission. The judge's verdict:

```json
{
  "claim_id": "c3",
  "confidence": 100,
  "label": "supported",
  "reasoning": "Multiple independent sources, including Wikipedia and reporting from major outlets like The Guardian, confirm that SpaceX successfully achieved the first reflight of an orbital-class Falcon 9 rocket on March 30, 2017, with the SES-10 mission.",
  "dissent": "The prosecution brief itself noted that it found no contradicting evidence and that the provided evidence explicitly supports the claim, meaning there is no substantive argument against the claim.",
  "key_citations": [
    {"url": "https://en.wikipedia.org/wiki/Falcon_9"},
    {"url": "https://spacepolicyonline.com/news/spacex-launches-lands-reused-first-stage"},
    {"url": "https://www.theguardian.com/science/2017/mar/30/spacex-falcon-9-elon-musk-reusable-rocket"}
  ]
}
```

The same run also extracted *"SpaceX has never had a launch failure in its entire
history"* from the same input text — a false claim planted right next to three true
ones — and the judge correctly ruled it `contradicted` at confidence 0, citing the 2015
CRS-7 failure and a 2018 Starlink launch anomaly, with a dissent noting even the
defender's own brief conceded it found no supporting evidence. That's the adversarial
design working as intended: two independently-researched briefs, judged on evidence
quality rather than which side sounded more confident.

## Quickstart

```bash
git clone https://github.com/aryan122pratap/ground-truth.git
cd ground-truth
pip install -r requirements.txt
cp .env.example .env   # then add GEMINI_API_KEY — get one free at aistudio.google.com/apikey
streamlit run app.py
```

No `TAVILY_API_KEY` is required — `search.py` falls back to `ddgs` (DuckDuckGo, no key
needed) automatically. Every third-party dependency in the default configuration has a
free tier.

## Design decisions & tradeoffs

- **The rebuttal loop is capped at 2 rounds.** A third round buys very little marginal
  accuracy for roughly 50% more latency and LLM/search cost per ambiguous claim — for a
  demo-oriented tool where "doesn't look frozen" matters as much as precision, that's the
  wrong trade. The cap is enforced in `graph.py`'s routing function, not a prompt
  instruction, so it can't be talked out of it by the model.
- **Credibility is a heuristic, not ground truth.** `search.compute_credibility()` scores
  a source from its domain alone (`.gov`/`.edu`/`.int` and a short list of major wire and
  reference domains score higher, known low-quality patterns score lower, everything else
  is 0.5). It's a cheap prior to help the judge weigh sources, not an authority ranking —
  a `.gov` page can be wrong and a small outlet can break a real story first.
- **Claims are audited in parallel, per-claim.** Each checkable claim gets its own
  `Send`-dispatched subgraph invocation, so latency scales with the slowest single claim
  rather than the claim count — in principle. In practice, on a real free-tier key the
  binding constraint turned out to be a **shared** per-minute quota across all
  concurrent calls (see `llm.py`'s `_RateLimiter` and the note on `LLM_MAX_CALLS_PER_MINUTE`
  in `config.py`), so parallelism reduces latency but doesn't eliminate the linear cost of
  more claims needing more total LLM calls. Measured on a real key: a 4-claim audit took
  ~75-135s depending on how many claims needed the rebuttal round, above the spec's
  60-second target for 5 claims. The knob to trade off is `LLM_MAX_CALLS_PER_MINUTE`
  against your key's actual tier.
- **The default model is `gemini-flash-lite-latest`, not a pinned version.** The spec's
  original `gemini-2.0-flash` was retired by Google mid-build (404, "no longer available
  to new users"). Its replacement alias, `gemini-flash-latest`, currently resolves to
  `gemini-3.7-flash`, whose free tier turned out to be a hard
  `GenerateRequestsPerDayPerProjectPerModel-FreeTier` cap of just 20 requests/day — easy
  to exhaust with a single multi-claim audit (~5 LLM calls per claim per round). The lite
  alias has its own, separate quota. Both are Google-maintained aliases rather than a
  pinned model name, trading a small amount of run-to-run consistency for not going stale
  the same way again.
- **Agent outputs reference evidence by index, not by re-emitting full `Evidence` JSON.**
  Prosecutor/defender/judge LLM calls return a small draft schema
  (`used_evidence_indices` / `key_citation_indices`) pointing into evidence already
  fetched by `search.py`, and the real `Evidence` objects are substituted in code. This
  guarantees every citation is a real URL that was actually retrieved — the model can't
  hallucinate a source.
- **Every agent node catches its own exceptions and degrades to a stub result** (`graph.py`)
  instead of raising, so one failed claim or a down search API never crashes the whole
  audit — verified in `tests/test_graph.py` without needing a live LLM.

## Limitations

- The judge and debaters can still hallucinate in their *reasoning* even when the cited
  URLs are real — read the reasoning, don't just trust the confidence number.
- Search results reflect whatever DuckDuckGo/Tavily's index has right now; very recent
  events may be under-covered, and very old claims may surface modern retrospectives
  instead of contemporary sources.
- No paywalled sources are fetched or read in full — agents work from search snippets,
  which can miss nuance in the full article.
- English-only; claim extraction and query generation are not tested against other
  languages.
- The credibility heuristic is domain-based only, per the tradeoff above.
- Free-tier Gemini quotas are tight and change without notice — a model that works today
  may 404 or exhaust its daily quota tomorrow. If `streamlit run app.py` shows every claim
  as `unverifiable` with a "Judge agent failed" reasoning, check for a `RateLimitError` in
  the terminal: it usually means the day's free quota for the configured model is spent,
  not that something is broken. Swapping `DEFAULT_MODEL` in `config.py` to a different
  Gemini alias, or setting `GROQ_API_KEY` for the fallback, works around it.

## Roadmap

- Browser extension for auditing text in place on any page.
- PDF ingestion for longer documents (research papers, reports).
- Local Ollama support as a zero-network, zero-key model backend.

## Definition of done

See [GROUND_TRUTH_SPEC.md](GROUND_TRUTH_SPEC.md) §11 for the full checklist this build
was verified against.

## License

MIT — see [LICENSE](LICENSE).
