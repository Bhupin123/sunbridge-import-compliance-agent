import json
from pathlib import Path

from typing import TypedDict

from langgraph.graph import StateGraph, START, END

from document_loader import load_sources
from extractor import extract_information
from fetcher import fetch_datasheet


class AgentState(TypedDict):
    sources: dict
    claims: dict
    analysis: str
    report: str


def fetch_sources(state: AgentState):

    print("0. Fetching source documents from their links...")

    # Always try to pull the datasheet from its public URL. If the
    # network is unavailable it falls back to the committed copy so the
    # pipeline still runs end to end.
    datasheet_path = fetch_datasheet(force=True)

    print(f"   Datasheet: {datasheet_path.name}")

    return {}


def load_documents(state: AgentState):

    print("1. Loading source documents...")

    sources = load_sources()

    return {
        "sources": sources
    }


def extract_claims(state: AgentState):

    print("2. Extracting source-attributed claims...")

    claims = extract_information(
        state["sources"]
    )

    return {
        "claims": claims
    }


def analyze_claims(state: AgentState):

    print("3. Analyzing claims and conflicts...")

    claims = state["claims"]

    agreements = []
    conflicts = []
    pending = []

    source_label = {
        "manufacturer_datasheet": "datasheet",
        "buyer_form": "buyer form",
        "call_notes": "call notes",
        "none": "none",
    }

    for field, values in claims.items():

        has_pending = any(
            c.get("status") == "pending_from_manufacturer" for c in values
        )
        actual = [
            c for c in values
            if c.get("status") != "pending_from_manufacturer" and c.get("value")
        ]

        if has_pending:
            pending.append(field)
        if not actual:
            continue

        # Group by a normalized value so we can tell agreement from
        # conflict. The original text is kept for display; we only
        # normalize to decide whether two claims mean the same thing.
        def norm(v):
            s = str(v)
            if field == "rated_power":
                t = s.lower().replace(" ", "")
                return "5kw" if t in {"5kw", "5000w", "5k"} else t
            if field == "manufacturer":
                return "deye" if "deye" in s.lower() else s.lower().strip()
            return s.lower().strip()

        groups = {}
        for c in actual:
            groups.setdefault(norm(c["value"]), []).append(c)

        def srcs_of(group):
            return {c["source"] for c in group}

        def show(group):
            out = []
            for c in group:
                t = str(c["value"]).strip()
                if t not in out:
                    out.append(t)
            return ", ".join(out)

        if len(groups) == 1:
            grp = next(iter(groups.values()))
            srcs = srcs_of(grp)
            if len(srcs) >= 2:
                agreements.append(
                    f"{field}: {'/'.join(sorted(source_label.get(s, s) for s in srcs))} "
                    f"agree on {show(grp)}"
                )
            else:
                s = next(iter(srcs))
                agreements.append(
                    f"{field}: only {source_label.get(s, s)} provides {show(grp)}"
                )
        else:
            parts = []
            for grp in groups.values():
                parts.append(
                    f"{show(grp)} "
                    f"({'/'.join(sorted(source_label.get(s, s) for s in srcs_of(grp)))})"
                )
            conflicts.append(f"{field}: " + " vs ".join(parts))

    analysis = ""
    if agreements:
        analysis += "### Agreements\n\n" + "\n".join(f"- {a}" for a in agreements) + "\n"
    if conflicts:
        analysis += (
            "\n### Potential Conflicts or Differences\n\n"
            + "\n".join(f"- {c}" for c in conflicts)
            + "\n"
        )
    if pending:
        analysis += "\n### Pending From Manufacturer\n\n"
        analysis += "\n".join(f"- {f}" for f in sorted(set(pending))) + "\n"

    if not analysis:
        analysis = "No significant differences identified."

    return {
        "analysis": analysis
    }


def generate_report(state: AgentState):

    print("4. Generating draft report...")

    claims = state["claims"]
    analysis = state["analysis"]

    report = "# SunBridge Import Compliance Draft (Task 2: China → Bangladesh)\n\n"
    report += (
        "Target product: the 5 kW grid-tied inverter SunBridge is "
        "ordering. Sources used: (1) manufacturer datasheet, "
        "(2) buyer form INT-2024-8841, (3) Ramesh's call notes "
        "2024-10-03. Every value below is traced to its source.\n\n"
    )

    # Full field-by-field evidence table
    report += "## Product Summary (field-by-field evidence)\n\n"
    report += "| Field | Source Evidence | Assessment |\n"
    report += "|---|---|---|\n"

    for field, values in claims.items():

        evidence = []
        for claim in values:
            value = claim.get("value", "")
            source = claim.get("source", "")
            status = claim.get("status", "")
            notes = claim.get("notes", "")
            evidence.append(
                f"**{value}** ({source}; {status})<br>{notes}"
            )

        statuses = [claim.get("status") for claim in values]

        if "pending_from_manufacturer" in statuses:
            assessment = "Pending / incomplete"
        elif "unverified" in statuses:
            assessment = "Contains unverified information"
        elif len(values) > 1:
            assessment = "Multiple source claims"
        else:
            assessment = "Documented"

        report += (
            f"| {field} | "
            f"{'<br><br>'.join(evidence)} | "
            f"{assessment} |\n"
        )

    readable = lambda f: f.replace("_", " ")

    # 1. Established by the datasheet
    report += "\n## 1. What the datasheet actually establishes\n\n"
    report += (
        "These are stated in writing by the manufacturer datasheet "
        "(the only documentary source we have):\n\n"
    )
    established = []
    for field, values in claims.items():
        for c in values:
            if c.get("status") == "manufacturer_stated" and \
               c.get("value") not in (None, "pending_from_manufacturer"):
                established.append(
                    f"- **{readable(field)}**: {c.get('value')}"
                )
    report += ("\n".join(established) + "\n") if established else "- (none found)\n"

    # 2. Stated only verbally (call notes)
    report += "\n## 2. Stated only verbally (call notes) — not in writing\n\n"
    report += (
        "These appear only in Ramesh's call notes. They are verbal "
        "claims, not manufacturer documentation, and must not be "
        "treated as confirmed facts:\n\n"
    )
    verbal_only = []
    for field, values in claims.items():
        for c in values:
            if c.get("status") in ("verbal", "unverified"):
                tag = "unverified guess" if c.get("status") == "unverified" \
                      else "verbal"
                verbal_only.append(
                    f"- **{readable(field)}**: {c.get('value')} ({tag})"
                )
    report += ("\n".join(verbal_only) + "\n") if verbal_only else "- (none)\n"

    # 3. Where the sources disagree
    report += "\n## 3. Where the sources disagree\n\n"
    disagreements = []
    for field, values in claims.items():
        stated = [c for c in values if c.get("status") == "manufacturer_stated"]
        others = [c for c in values
                  if c.get("status") in ("verbal", "unverified", "buyer_stated")]
        if not stated or not others:
            continue
        stated_vals = {c.get("value") for c in stated}
        other_vals = {c.get("value") for c in others}
        if not other_vals.issubset(stated_vals):
            doc = ", ".join(sorted(str(v) for v in stated_vals))
            alt = ", ".join(sorted(str(v) for v in other_vals))
            disagreements.append(
                f"- **{readable(field)}**: datasheet says *{doc}*; "
                f"other sources say *{alt}*. Shown side by side — "
                f"not reconciled."
            )
    report += ("\n".join(disagreements) + "\n") if disagreements \
        else "- No outright disagreements between documentary and verbal sources.\n"

    # 4. Pending from the manufacturer
    report += "\n## 4. Pending from the manufacturer\n\n"
    report += (
        "Especially test evidence, certificates, and label photos. "
        "These are genuinely missing from the three supplied sources:\n\n"
    )
    pending_fields = []
    for field, values in claims.items():
        if any(c.get("status") == "pending_from_manufacturer" for c in values):
            pending_fields.append(f"- **{readable(field)}**")
    confirm_fields = []
    for field, values in claims.items():
        if any(c.get("status") == "unverified" for c in values):
            confirm_fields.append(
                f"- **{readable(field)}** — verify with factory"
            )
    report += ("\n".join(pending_fields) + "\n") if pending_fields \
        else "- (none flagged as fully missing)\n"
    if confirm_fields:
        report += "\nStill needs factory confirmation (verbal/unverified):\n\n"
        report += "\n".join(confirm_fields) + "\n"

    # 5. Concrete questions for the manufacturer
    report += "\n## 5. Questions for SunBridge to send the factory\n\n"
    questions = []
    for field, values in claims.items():
        for c in values:
            status = c.get("status")
            value = c.get("value", "")
            if status == "pending_from_manufacturer":
                questions.append(
                    f"- Please provide the official manufacturer "
                    f"documentation for {readable(field)}."
                )
            elif status == "unverified":
                questions.append(
                    f"- Please confirm the official value for "
                    f"{readable(field)}. Our call notes contain an "
                    f"unverified value: {value}."
                )
    questions = list(dict.fromkeys(questions))
    report += ("\n".join(questions) + "\n") if questions else "- No open questions.\n"

    # Source comparison from the analysis step
    report += "\n## Source comparison and analysis\n\n"
    report += analysis

    report += (
        "\n\n## Important note\n\n"
        "This draft is based only on the three supplied sources. "
        "Manufacturer-documented information is kept distinct from "
        "buyer-provided and verbal information. The call notes include "
        "unverified statements and estimates, which are not treated as "
        "equivalent to manufacturer documentation. No certificates, "
        "test reports, or label photograph were supplied in the source "
        "material, so these remain pending from the manufacturer. "
        "Marking a field 'pending from manufacturer' is a valid answer, "
        "not a failure."
    )

    return {
        "report": report
    }


# LangGraph pipeline: fetch -> load -> extract -> analyze -> report
builder = StateGraph(AgentState)

builder.add_node("fetch_sources", fetch_sources)
builder.add_node("load_documents", load_documents)
builder.add_node("extract_claims", extract_claims)
builder.add_node("analyze_claims", analyze_claims)
builder.add_node("generate_report", generate_report)

builder.add_edge(START, "fetch_sources")
builder.add_edge("fetch_sources", "load_documents")
builder.add_edge("load_documents", "extract_claims")
builder.add_edge("extract_claims", "analyze_claims")
builder.add_edge("analyze_claims", "generate_report")
builder.add_edge("generate_report", END)

graph = builder.compile()


if __name__ == "__main__":

    initial_state = {
        "sources": {},
        "claims": {},
        "analysis": "",
        "report": ""
    }

    result = graph.invoke(initial_state)

    output_dir = Path(__file__).resolve().parent.parent / "output"
    output_dir.mkdir(exist_ok=True)

    json_path = output_dir / "extracted_claims.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result["claims"], f, indent=2, ensure_ascii=False)

    report_path = output_dir / "sunbridge_compliance_draft.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(result["report"])

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print(f"Structured output: {json_path}")
    print(f"Human-readable draft: {report_path}")

    print("\n" + "=" * 60)
    print("FINAL REPORT")
    print("=" * 60)

    # Guard against console encoding errors on Windows (cp1252)
    try:
        print(result["report"])
    except UnicodeEncodeError:
        print(result["report"].encode("ascii", "replace").decode("ascii"))
