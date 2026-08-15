import os
import json
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

from document_loader import load_sources
from model import ProductExtraction


# Last good extraction is cached here so the pipeline can run without
# hitting the API on every invocation (useful on the free tier's daily
# token cap, or for offline runs). Opt-in via USE_EXTRACTION_CACHE=1.
CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / ".extraction_cache.json"


load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)


SYSTEM_PROMPT = """
You are a careful document extraction assistant working on an
import-compliance review for SunBridge Trading.

The target product is the 5 kW inverter being ordered by SunBridge.

Your job is to extract factual claims from the supplied source documents.

CORE RULES:

1. Use ONLY the supplied source documents.
2. Do not use outside knowledge.
3. Do not guess missing information.
4. Preserve all relevant claims from all sources.
5. If sources disagree, preserve BOTH claims.
6. Never silently choose one conflicting value.
7. Identify the exact source supporting every claim.
8. Call notes are verbal unless the source provides written evidence.
9. Installer guesses and estimates must be marked unverified.
10. If information is genuinely missing, use:
    "pending_from_manufacturer"
11. Do not invent certificates, tests, labels, specifications,
    measurements, or manufacturer information.

5K TARGET RULE:

The manufacturer datasheet may contain multiple models.

For manufacturer_datasheet:

- First identify the exact 5K / 5 kW model.
- Extract product-specific specifications ONLY from the 5K model.
- Do not extract specifications from other models.
- Do not mix values between model columns or rows.
- If the document layout makes the 5K value unclear, flag it as
  uncertain rather than guessing.

For buyer_form and call_notes:

- Extract claims relevant to the requested 5 kW product.
- Preserve the model number exactly as written.
- Do not silently normalize different model numbers.

Do not convert units unless the source explicitly provides the
converted value.

For each claim return:

- value
- source
- confidence
- status
- notes

Possible status values:

- manufacturer_stated
- buyer_stated
- verbal
- unverified
- pending_from_manufacturer
- inferred
- conflicting

Return ONLY valid JSON.
"""


def extract_information(sources: dict, force: bool = False) -> dict:

    use_cache = os.getenv("USE_EXTRACTION_CACHE") == "1"

    if use_cache and not force and CACHE_PATH.exists():
        try:
            print("   (reusing cached extraction — set USE_EXTRACTION_CACHE=0 or force=True to refresh)")
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    source_text = "\n\n".join(
        f"===== SOURCE: {name} =====\n{content}"
        for name, content in sources.items()
    )

    user_prompt = f"""
TARGET PRODUCT

SunBridge is ordering the 5 kW model.

The supplied sources are:

1. manufacturer_datasheet
2. buyer_form
3. call_notes

SOURCE HANDLING RULES

Read each source independently.

For every field:

- Extract a claim only if that source actually contains information
  supporting the field.
- Do not create a claim merely because another source contains the field.
- Do not assume that a missing field has the same value as another source.
- If the field is absent from all supplied sources, return exactly one
  pending_from_manufacturer claim.
- Preserve all genuinely relevant claims when multiple sources mention
  the same field.

5K MODEL FILTER

The manufacturer datasheet may contain several models in the same table.

Before extracting manufacturer_datasheet specifications:

1. Identify the 5K / 5 kW model column or row.
2. Confirm that the specification belongs to that model.
3. Extract only that model's value.
4. Ignore specifications belonging to other models.
5. Never combine values from different model columns.
6. If the table layout makes the association uncertain, do not guess.
   Preserve the value only if there is reasonable evidence that it is
   associated with the 5K model, and mark:

   confidence: "low"

   with a note explaining the ambiguity.

Do NOT use values from 3K, 8K, 10K, 12K, 15K, or other models as the
5K manufacturer's specification.

SOURCE-SPECIFIC RULES

manufacturer_datasheet:

- Manufacturer claims must come directly from the datasheet.
- Product-specific specifications must belong to the 5K model.
- Do not use information from buyer_form or call_notes to fill gaps in
  the manufacturer datasheet.

buyer_form:

- Preserve the buyer's wording exactly.
- Mark claims as buyer_stated.
- Do not upgrade buyer claims to manufacturer_stated.

call_notes:

- Preserve the wording and meaning of the call notes.
- Mark ordinary spoken claims as verbal.
- If the call notes explicitly identify something as a guess, estimate,
  or uncertainty, mark it as unverified.
- Do not treat verbal claims as manufacturer documentation.

MODEL NUMBERS

Preserve model numbers exactly as written by each source.

For example:

manufacturer_datasheet:
SUN-5K-G06P3-EU-AM2-P1

buyer_form:
SUN-5K-G06P3-EU-AM2-P1

call_notes:
SUN-5K-G06P3

These are separate source claims.

Do not silently shorten, expand, normalize, or reconcile them.

UNIT PRESERVATION

When a source provides a numerical value together with its unit,
preserve the complete value including the unit.

For example:

"11 kg" → "11 kg"
"98.5%" → "98.5%"
"5000 W" → "5000 W"

Do not strip units from values.

Do not add a unit if the source does not provide one.

SOURCE AGREEMENT

Do not remove duplicate-looking claims merely because their values
are identical.

For example, if the manufacturer datasheet says "5 kW", the buyer form
says "5000 W", and the call notes say "5 kW", preserve all three claims.

The later analysis stage may determine that these values represent
agreement.

CONFIDENCE RULES

Use:

- "high" when the value is clearly stated and clearly associated with
  the target product.
- "low" when the value is ambiguous, poorly mapped because of document
  layout, estimated, or otherwise uncertain.
- "none" only for pending_from_manufacturer claims.

IMPORTANT:

If notes contain words such as:

- uncertain
- unclear
- ambiguous
- difficult to determine
- table layout
- may belong to another model
- estimated
- guessed

then do NOT use "high" confidence.

STATUS RULES

Use:

manufacturer_stated
    when directly stated by the manufacturer datasheet.

buyer_stated
    when directly stated by the buyer form.

verbal
    when stated in the call notes as a normal verbal claim.

unverified
    when the call notes identify the claim as a guess, estimate,
    or otherwise unverified statement.

pending_from_manufacturer
    when the information is not present in the supplied sources and
    needs to be obtained from the manufacturer.

Do not use "inferred" unless the source itself requires a genuine
inference. Prefer preserving the source wording instead.

FIELDS TO EXTRACT

Extract these fields:

- model
- rated_power
- manufacturer
- factory_address
- country_of_manufacture
- ip_rating
- weight
- max_efficiency
- grid_standards
- safety_emc_standards
- testing_evidence
- labeling

NOTE: The manufacturer datasheet footer usually contains the legal
company name and full factory address. Extract that as factory_address
when present, attributed to manufacturer_datasheet.

NOTE: The call notes may mention testing bodies or certificates
verbally (e.g. "SGS") with "nothing in writing". Capture such mentions
as verbal claims under testing_evidence instead of dropping them. They
are NOT manufacturer documentation and must not be marked
manufacturer_stated. If the same field also has no written evidence
anywhere, you may return BOTH the verbal claim and a
pending_from_manufacturer claim.

IMPORTANT MISSING-DATA RULE

If a field is not supported by any of the three sources, return:

{{
  "value": "pending_from_manufacturer",
  "source": "none",
  "confidence": "none",
  "status": "pending_from_manufacturer",
  "notes": "No information found in supplied sources."
}}

Do not invent missing certificates, test reports, labels, addresses,
measurements, specifications, or documentation.

FINAL VALIDATION BEFORE RETURNING JSON

Before producing the final JSON, check:

1. Every manufacturer product-specific value belongs to the 5K model.
2. No value from another model was copied into the 5K result.
3. Every claim identifies its source.
4. Buyer claims are not marked manufacturer_stated.
5. Verbal claims are not marked manufacturer_stated.
6. Guesses and estimates are unverified.
7. Uncertain table mappings have low confidence.
8. Missing information is marked pending_from_manufacturer.
9. Conflicting source claims are preserved.
10. Source wording and units are preserved.

SOURCE MATERIAL

{source_text}

Return exactly this JSON structure:

{{
  "model": [],
  "rated_power": [],
  "manufacturer": [],
  "factory_address": [],
  "country_of_manufacture": [],
  "ip_rating": [],
  "weight": [],
  "max_efficiency": [],
  "grid_standards": [],
  "safety_emc_standards": [],
  "testing_evidence": [],
  "labeling": []
}}
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ]
    )

    result = response.choices[0].message.content

    data = json.loads(result)

    validated = ProductExtraction.model_validate(data)

    data = validated.model_dump()

    data = enforce_claim_rules(data)

    if use_cache:
        CACHE_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    return data

def enforce_claim_rules(data: dict) -> dict:
    """
    Deterministic validation layer.

    The LLM performs extraction, but these rules are enforced
    programmatically so the final structured output remains
    consistent.
    """

    for field, claims in data.items():

        for claim in claims:

            source = claim.get("source", "")
            value = str(claim.get("value", ""))
            notes = str(claim.get("notes", "")).lower()

            # SOURCE STATUS ENFORCEMENT

            if source == "manufacturer_datasheet":
                claim["status"] = "manufacturer_stated"

            elif source == "buyer_form":
                claim["status"] = "buyer_stated"

            elif source == "call_notes":

                if any(
                    word in notes
                    for word in [
                        "guess",
                        "guessed",
                        "estimate",
                        "estimated",
                        "unverified",
                        "uncertain"
                    ]
                ):
                    claim["status"] = "unverified"
                else:
                    claim["status"] = "verbal"

            elif source == "none":
                claim["status"] = "pending_from_manufacturer"
                claim["confidence"] = "none"

            # CONFIDENCE ENFORCEMENT

            uncertainty_words = [
                "uncertain",
                "unclear",
                "ambiguous",
                "difficult to determine",
                "table layout",
                "may belong",
                "estimated",
                "guessed",
                "guess"
            ]

            has_uncertainty = any(
                word in notes
                for word in uncertainty_words
            )

            if has_uncertainty:
                claim["confidence"] = "low"

            # PENDING DATA

            if value == "pending_from_manufacturer":
                claim["source"] = "none"
                claim["confidence"] = "none"
                claim["status"] = "pending_from_manufacturer"

    return data

if __name__ == "__main__":

    sources = load_sources()

    result = extract_information(sources)

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        )
    )