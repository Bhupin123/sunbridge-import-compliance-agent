# SunBridge Import Compliance Agent — Task 2 (China → Bangladesh)

An autonomous pipeline that reads the three source documents SunBridge
has for its Bangladesh inverter order, extracts the facts **with source
attribution, status, and confidence**, and produces a clean compliance
draft SunBridge can circulate internally.

Built for the **Cantordust Analytics AI Engineer assessment
(trainee / junior track)**, Task 2: China → Bangladesh, 5 kW
grid-tied inverter.

The task is explicitly about **handling gaps and uncertainty**: half the
information does not exist yet, so the pipeline is built to say so
clearly (`pending_from_manufacturer`, `unverified`) instead of guessing.

---

## Table of contents

- [The problem](#the-problem)
- [What it does](#what-it-does)
- [Design decisions](#design-decisions)
- [Pipeline architecture](#pipeline-architecture)
- [Source-attribution & confidence model](#source-attribution--confidence-model)
- [How to run](#how-to-run)
- [Outputs](#outputs)
- [Assumptions](#assumptions)
- [What I would do with more time](#what-i-would-do-with-more-time)
- [Submission checklist coverage](#submission-checklist-coverage)

---

## The problem

SunBridge is importing a 5 kW grid-tied inverter from Deye in China to
Bangladesh. The factory has not yet sent verified paperwork, but the
import agent needs a compliance bundle to proceed. The agent gets three
things:

1. **Manufacturer datasheet** (PDF, from the public Deye link) — the only
   documentary source.
2. **Buyer form** (`INT-2024-8841`, targeting `SUN-5K-G06P3-EU-AM2-P1`)
   — what the purchasing side requested.
3. **Call notes** (2024-10-03) — verbal claims from the installer,
   including guesses and unconfirmed test mentions.

The job is to produce an honest draft: preserve every value **with its
source**, show conflicts side by side, mark verbal claims as unverified,
and list what is genuinely missing — rather than inventing answers.

---

## What it does

1. **Fetches** the manufacturer datasheet PDF from its public link
   (with an offline fallback so the pipeline always runs).
2. **Loads** the three sources: datasheet (PDF), buyer form (text),
   call notes (text).
3. **Extracts** structured claims with an LLM, tagging every value by
   `source`, `status`, and `confidence`.
4. **Analyzes** agreements, conflicts, and gaps **deterministically**
   (no LLM judgement call here).
5. **Generates** a human-readable Markdown draft that separates what is
   established by the datasheet, what is only verbal, where sources
   disagree, and what is still pending from the manufacturer.

---

## Design decisions

Every choice was deliberate. The brief rewards an honest, runnable
pipeline over a complex one.

- **Why LangGraph?** The task asks for an *agent*. A small stateful
  graph (`fetch → load → extract → analyze → report`) is the simplest
  thing that is genuinely autonomous: it fetches, reads, and reasons
  over the documents itself instead of being driven field-by-field.
- **Why no RAG / vector DB / Chroma?** The sources are three small
  documents — a few pages of text. A retrieval layer adds complexity
  with zero benefit. Everything is read directly into the prompt.
- **Why no OCR?** The Deye datasheet is a clean, text-based PDF, not a
  scan. PyMuPDF extracts it directly. OCR would add a heavy dependency
  and noise for no gain. If a future revision were a scan, only
  `document_loader.py` would need to change.
- **Why no multi-agent swarm?** This is a straight-line job. One graph,
  five steps, one shared state. Orchestration overhead would be theatre.
- **Why an LLM at all?** The datasheet is a wide multi-model spec table.
  Isolating the 5 kW row from sibling models (4K/6K/8K/…/15K) and
  reconciling it against two other sources is exactly the read-and-reason
  task a model is good at — and it keeps the pipeline robust to a
  different revision of the same datasheet (no hardcoded values).
- **Deterministic guardrails.** `extractor.py` runs
  `enforce_claim_rules` after the LLM: it re-asserts status and
  confidence from the values themselves, so the model cannot override
  compliance flags with its wording.

---

## Pipeline architecture

Built with **LangGraph** as a small stateful agent graph
(`src/workflow.py`).

```
START
  -> fetch_sources    (download datasheet PDF from URL; fallback to committed copy)
  -> load_documents   (read PDF + buyer form + call notes)
  -> extract_claims   (LLM extracts source-attributed claims; guardrails re-assert)
  -> analyze_claims   (deterministic agreement / conflict / gap analysis)
  -> generate_report  (Markdown draft for the agent)
  -> END
```

### Project structure

```
sunbridge-import-compliance-agent/
├── src/
│   ├── workflow.py            # LangGraph pipeline + report generation
│   ├── fetcher.py             # datasheet download (User-Agent + offline fallback)
│   ├── document_loader.py     # loads PDF + text sources
│   ├── extractor.py           # LLM extraction, cache, deterministic guardrails
│   ├── model.py               # Pydantic schema (SourceClaim, ProductExtraction)
│   └── test_model.py          # sanity tests for the data models
├── data/
│   ├── manufacturer_datasheet.pdf   # committed fallback copy of the datasheet
│   ├── buyer_form.txt
│   └── call_notes.txt
├── output/
│   ├── extracted_claims.json        # pipeline output (source-attributed)
│   └── sunbridge_compliance_draft.md # pipeline output (human-readable draft)
├── presentation/               # video deck assets (diagrams, exported PDF)
├── .env.example                # GROQ_API_KEY template
├── requirements.txt
└── README.md
```

### Source-attribution & confidence model

Every extracted claim carries five fields:

- `value` — preserved exactly, with its original unit.
- `source` — `manufacturer_datasheet` | `buyer_form` | `call_notes` | `none`.
- `status` — `manufacturer_stated` | `buyer_stated` | `verbal` |
  `unverified` | `pending_from_manufacturer`.
- `confidence` — `high` | `low` | `none`.
- `notes` — why a value is low confidence, or what the conflict is.

---

## How to run

### Prerequisites

- Python 3.10+ (developed on 3.14)
- A [Groq](https://console.groq.com/) API key (free tier is enough)

### Setup

```bash
# 1. Clone
git clone <your-repo-url>
cd sunbridge-import-compliance-agent

# 2. Create a virtual environment (optional but recommended)
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your API key
cp .env.example .env
# then edit .env and set GROQ_API_KEY=gsk_...
```

### Run the pipeline end to end

```bash
python src/workflow.py
```

This runs all five steps and writes:

- `output/extracted_claims.json` — machine-readable, source-attributed
- `output/sunbridge_compliance_draft.md` — the hand-to-agent draft

### Running offline / without re-paying for tokens

The free Groq tier has a daily token cap. Once the pipeline has run
once, the extraction is cached to `data/.extraction_cache.json`
(gitignored). To reuse it and skip the live API call:

```bash
# Windows PowerShell
$env:USE_EXTRACTION_CACHE=1
python src/workflow.py

# macOS / Linux
USE_EXTRACTION_CACHE=1 python src/workflow.py
```

Set `USE_EXTRACTION_CACHE=0` (or delete the cache file) to force a fresh
API extraction.

### Other commands

```bash
python src/test_model.py   # run the model sanity tests
python src/fetcher.py      # run only the datasheet fetch step
```

### Environment variables

| Variable              | Required | Purpose                                  |
|-----------------------|----------|------------------------------------------|
| `GROQ_API_KEY`        | Yes*     | Groq API key (only needed for a live LLM extraction) |
| `USE_EXTRACTION_CACHE`| No       | `1` to reuse the cached extraction; unset/`0` to call the API |

---

## Outputs

### `output/extracted_claims.json`

A machine-readable version of everything the agent knows. Every value is
tagged with its source, status, and confidence. The key conflict in this
task — the weight — is preserved exactly as it appears in each source:

```json
"weight": [
  {
    "value": "11 kg",
    "source": "manufacturer_datasheet",
    "confidence": "high",
    "status": "manufacturer_stated",
    "notes": "Weight from manufacturer datasheet"
  },
  {
    "value": "18 kg",
    "source": "call_notes",
    "confidence": "low",
    "status": "unverified",
    "notes": "Weight from call notes, installer's guess"
  }
]
```

### `output/sunbridge_compliance_draft.md`

The draft SunBridge hands over. It is organized so a reader can see in
seconds what is real, what is unconfirmed, and what is missing:

1. **What the datasheet actually establishes** — values in writing.
2. **Stated only verbally (call notes)** — flagged, never upgraded.
3. **Where the sources disagree** — shown side by side, not reconciled.
4. **Pending from the manufacturer** — test certificates, label photo.
5. **Questions for SunBridge to send the factory** — the concrete
   follow-ups the draft implies.

It also includes a source-comparison section (agreements / conflicts /
pending) generated deterministically by the `analyze_claims` step.

---

## Assumptions

1. **Target model is the 5 kW unit** (`SUN-5K-G06P3-EU-AM2-P1`), as the
   brief states. Only the 5K row of the datasheet is extracted.
2. **Datasheet = documentary source.** Buyer form = buyer-stated. Call
   notes = verbal (and explicitly marked `unverified` where Ramesh says
   it is a guess, e.g. the 18 kg weight). Verbal claims are never
   upgraded to manufacturer facts.
3. **Missing ≠ error.** Fields absent from all three sources are
   returned as `pending_from_manufacturer` (e.g. test certificates,
   label photo). This is intentional and matches the brief.
4. **Model numbers are preserved verbatim per source** (the datasheet
   and buyer form say `SUN-5K-G06P3-EU-AM2-P1`; the call notes say
   `SUN-5K-G06P3`). They are shown side by side, not silently
   normalized.
5. **Units are preserved** as written (e.g. `5 kW` vs `5000 W`).
6. The three sources are the *only* data used — no outside knowledge,
   no web lookups beyond fetching the supplied datasheet link.

---

## What I would do with more time

- **Multi-agent verification**: add a second LLM "reviewer" node that
  re-checks the 5K column isolation against the raw table, lowering
  confidence automatically when the row mapping is ambiguous (this is
  the single biggest extraction risk).
- **Table-aware parsing**: parse the datasheet's spec table into a
  row-keyed structure first (e.g. with `camelot`/`tabula` or a vision
  model), then ask the LLM to read that structure — far less prone to
  cross-column leakage than raw text.
- **Structured label field**: derive the expected label contents
  (model, ratings, manufacturer, origin, IP rating) explicitly from the
  extracted claims, rather than leaving labeling as fully pending.
- **Tests for the analysis layer**: unit tests for `analyze_claims`
  and `enforce_claim_rules` with fixed fixtures, so the deterministic
  logic is locked down independent of the LLM.
- **HTML/PDF export** of the draft via a lightweight renderer.
- **Config-driven sources**: move the datasheet URL and buyer/call-note
  text into a config so Task 1 (Nepal, two datasheets) can reuse the
  same pipeline unchanged.

---

## Submission checklist coverage

- Runnable from the links: `fetcher.py` downloads the datasheet.
- README: this file.
- Structured output with per-field source + confidence:
  `output/extracted_claims.json`.
- Human-readable draft generated by the pipeline:
  `output/sunbridge_compliance_draft.md`.
- Honest handling of gaps: `pending_from_manufacturer` and
  `unverified` statuses throughout.
