"""
Automated sales call sentiment analysis pipeline.

1. Reads .txt transcripts from /Transcript_Data_Call
2. Analyzes each with the Anthropic Claude API
3. Saves per-call structured JSON to /outputs/raw
4. Compiles a daily Markdown report into /outputs/reports
"""

import os
import sys
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

import anthropic

BASE_DIR = Path(__file__).resolve().parent
TRANSCRIPT_DIR = BASE_DIR / "Transcript_Data_Call"
RAW_OUTPUT_DIR = BASE_DIR / "outputs" / "raw"
REPORTS_DIR = BASE_DIR / "outputs" / "reports"

MODEL = "claude-sonnet-4-20250514"

ANALYSIS_PROMPT = """You are an expert sales call analyst. Read the following sales call transcript \
between a Sales Rep and a Customer, then extract structured information about it.

Respond with ONLY a single valid JSON object (no markdown formatting, no code fences, no extra text) \
with exactly these keys:

- "overall_sentiment": one of "positive", "neutral", "negative"
- "customer_interest_level": one of "high", "medium", "low"
- "key_topics": a list of strings naming the products or topics discussed
- "objections_raised": a list of strings describing concerns or hesitations raised by the customer \
(empty list if none)
- "outcome": a short string describing the likely outcome, e.g. "likely to purchase", \
"needs follow-up", "not interested"
- "summary": a 2-3 sentence plain English summary of the call

Transcript:
---
{transcript}
---
"""


def get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: Environment variable ANTHROPIC_API_KEY is not set.")
        sys.exit(1)
    return anthropic.Anthropic(api_key=api_key)


def extract_json(text: str) -> dict:
    """Extract a JSON object from the model's response, tolerating code fences."""
    text = text.strip()

    # Strip markdown code fences if present
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # Fall back to grabbing the first {...} block
    if not text.startswith("{"):
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            text = brace_match.group(0)

    return json.loads(text)


def analyze_transcript(client: anthropic.Anthropic, transcript_text: str) -> dict:
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": ANALYSIS_PROMPT.format(transcript=transcript_text),
            }
        ],
    )

    response_text = "".join(
        block.text for block in response.content if block.type == "text"
    )

    return extract_json(response_text)


def validate_analysis(analysis: dict) -> dict:
    """Ensure required keys exist and have sane defaults/types."""
    defaults = {
        "overall_sentiment": "neutral",
        "customer_interest_level": "medium",
        "key_topics": [],
        "objections_raised": [],
        "outcome": "needs follow-up",
        "summary": "",
    }
    for key, default_value in defaults.items():
        if key not in analysis or analysis[key] is None:
            analysis[key] = default_value

    if not isinstance(analysis["key_topics"], list):
        analysis["key_topics"] = [str(analysis["key_topics"])]
    if not isinstance(analysis["objections_raised"], list):
        analysis["objections_raised"] = [str(analysis["objections_raised"])]

    analysis["overall_sentiment"] = str(analysis["overall_sentiment"]).lower().strip()
    analysis["customer_interest_level"] = str(analysis["customer_interest_level"]).lower().strip()

    return analysis


def ingest_transcripts() -> list[Path]:
    if not TRANSCRIPT_DIR.is_dir():
        print(f"ERROR: Transcript directory not found: {TRANSCRIPT_DIR}")
        sys.exit(1)

    files = sorted(TRANSCRIPT_DIR.glob("*.txt"))
    return files


def process_single_file(client: anthropic.Anthropic, file_path: Path) -> dict | None:
    """Analyze a single transcript file, save its JSON output, and return the
    analysis dict, or None if the file was skipped due to an error."""
    try:
        transcript_text = file_path.read_text(encoding="utf-8")

        if not transcript_text.strip():
            print(f"  -> SKIPPED: {file_path.name} is empty.")
            return None

        analysis = analyze_transcript(client, transcript_text)
        analysis = validate_analysis(analysis)
        analysis["source_file"] = file_path.name

        output_path = RAW_OUTPUT_DIR / f"{file_path.stem}.json"
        output_path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")

        print(
            f"  -> OK: sentiment={analysis['overall_sentiment']}, "
            f"interest={analysis['customer_interest_level']}, "
            f"outcome={analysis['outcome']}"
        )

        return analysis

    except json.JSONDecodeError as e:
        print(f"  -> SKIPPED: failed to parse JSON response for {file_path.name} ({e})")
    except anthropic.APIError as e:
        print(f"  -> SKIPPED: Anthropic API error for {file_path.name} ({e})")
    except Exception as e:
        print(f"  -> SKIPPED: unexpected error for {file_path.name} ({e})")

    return None


def process_transcripts(client: anthropic.Anthropic, files: list[Path]) -> list[dict]:
    results = []

    for i, file_path in enumerate(files, start=1):
        print(f"[{i}/{len(files)}] Processing {file_path.name}...")
        analysis = process_single_file(client, file_path)
        if analysis is not None:
            results.append(analysis)

    return results


def load_all_results() -> list[dict]:
    """Load every previously-analyzed transcript's JSON from RAW_OUTPUT_DIR."""
    results = []
    for json_path in sorted(RAW_OUTPUT_DIR.glob("*.json")):
        try:
            results.append(json.loads(json_path.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"  -> WARNING: could not read {json_path.name} ({e})")
    return results


def build_report(results: list[dict]) -> str:
    total = len(results)

    sentiment_counts = Counter(r["overall_sentiment"] for r in results)
    interest_counts = Counter(r["customer_interest_level"] for r in results)

    objection_counts: Counter[str] = Counter()
    topic_counts: Counter[str] = Counter()
    for r in results:
        for objection in r.get("objections_raised", []):
            objection_counts[objection.strip()] += 1
        for topic in r.get("key_topics", []):
            topic_counts[topic.strip()] += 1

    high_interest = [r for r in results if r["customer_interest_level"] == "high"]

    report_date = date.today().isoformat()

    lines = []
    lines.append(f"# Daily Sales Call Sentiment Report - {report_date}")
    lines.append("")
    lines.append("## Overview")
    lines.append(f"- **Total calls processed:** {total}")
    lines.append("")

    lines.append("## Sentiment Breakdown")
    if total > 0:
        for sentiment in ["positive", "neutral", "negative"]:
            count = sentiment_counts.get(sentiment, 0)
            pct = (count / total) * 100
            lines.append(f"- **{sentiment.capitalize()}:** {count} ({pct:.0f}%)")
    else:
        lines.append("- No calls processed.")
    lines.append("")

    lines.append("## Customer Interest Level Breakdown")
    if total > 0:
        for level in ["high", "medium", "low"]:
            count = interest_counts.get(level, 0)
            pct = (count / total) * 100
            lines.append(f"- **{level.capitalize()}:** {count} ({pct:.0f}%)")
    else:
        lines.append("- No calls processed.")
    lines.append("")

    lines.append("## Top Recurring Objections")
    if objection_counts:
        for objection, count in objection_counts.most_common(10):
            lines.append(f"- {objection} ({count})")
    else:
        lines.append("- None recorded.")
    lines.append("")

    lines.append("## Top Topics / Products Mentioned")
    if topic_counts:
        for topic, count in topic_counts.most_common(10):
            lines.append(f"- {topic} ({count})")
    else:
        lines.append("- None recorded.")
    lines.append("")

    lines.append("## High-Interest Customers")
    if high_interest:
        for r in high_interest:
            lines.append(f"- **{r['source_file']}** (outcome: {r['outcome']})")
            lines.append(f"  - {r['summary']}")
    else:
        lines.append("- None identified.")
    lines.append("")

    lines.append("## Overall Recommendation for Sales Head")
    if total == 0:
        lines.append(
            "No calls were processed today, so no recommendation can be made."
        )
    else:
        positive_pct = (sentiment_counts.get("positive", 0) / total) * 100
        negative_pct = (sentiment_counts.get("negative", 0) / total) * 100
        high_interest_pct = (interest_counts.get("high", 0) / total) * 100

        recommendation_parts = []
        recommendation_parts.append(
            f"Out of {total} calls, {positive_pct:.0f}% were positive and "
            f"{negative_pct:.0f}% were negative, with {high_interest_pct:.0f}% of "
            f"customers showing high interest."
        )

        if objection_counts:
            top_objection, _ = objection_counts.most_common(1)[0]
            recommendation_parts.append(
                f"The most common objection was '{top_objection}' — consider "
                f"preparing reps with stronger talking points or supporting "
                f"materials to address this proactively."
            )

        if high_interest:
            recommendation_parts.append(
                f"Prioritize timely follow-up with the {len(high_interest)} "
                f"high-interest customer(s) identified above to maximize "
                f"conversion."
            )

        if negative_pct > 30:
            recommendation_parts.append(
                "A significant share of calls were negative — review these "
                "transcripts for coaching opportunities."
            )

        lines.append(" ".join(recommendation_parts))

    lines.append("")

    return "\n".join(lines)


def main():
    print("=== Sales Sentiment Analysis Pipeline ===")
    print(f"Model: {MODEL}")
    print(f"Transcript directory: {TRANSCRIPT_DIR}")
    print()

    RAW_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    client = get_client()

    files = ingest_transcripts()
    if not files:
        print("No .txt transcript files found. Exiting.")
        return

    print(f"Found {len(files)} transcript file(s).\n")

    results = process_transcripts(client, files)

    print()
    print(f"Successfully analyzed {len(results)}/{len(files)} transcripts.")

    print("Building daily report...")
    report = build_report(results)

    report_path = REPORTS_DIR / f"daily_report_{date.today().isoformat()}.md"
    report_path.write_text(report, encoding="utf-8")

    print(f"Report saved to {report_path}")
    print("Done.")


if __name__ == "__main__":
    main()
