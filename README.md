# Sales Sentiment Analysis Pipeline

An automated pipeline that analyzes sales call transcripts using the Anthropic Claude API,
extracts structured insights (sentiment, customer interest, objections, outcomes), and
compiles a daily Markdown report for the sales team.

## How it works

1. **Ingest** — Read all `.txt` transcripts from `Transcript_Data_Call/`.
2. **Analyze** — Send each transcript to Claude (`claude-sonnet-4-20250514`) and extract:
   - `overall_sentiment` (positive / neutral / negative)
   - `customer_interest_level` (high / medium / low)
   - `key_topics` (products/topics discussed)
   - `objections_raised` (customer concerns/hesitations)
   - `outcome` (e.g. likely to purchase, needs follow-up, not interested)
   - `summary` (2-3 sentence plain English summary)
3. **Store** — Save each transcript's analysis as JSON in `outputs/raw/`.
4. **Report** — Compile all analyses into a daily Markdown report in `outputs/reports/`.

## Files

| File / Folder | Description |
|---|---|
| `sentiment_pipeline.py` | Core pipeline. Reads all transcripts from `Transcript_Data_Call/`, calls the Claude API to analyze each one, saves per-call JSON to `outputs/raw/`, and generates the daily report in `outputs/reports/`. Can be run standalone for a one-off batch run. |
| `watcher.py` | Background folder watcher (using `watchdog`). Monitors `Transcript_Data_Call/` continuously — the moment a new `.txt` file is added, it analyzes that single file, saves its JSON output, and regenerates the daily report from all results so far. Runs indefinitely until stopped (Ctrl+C). |
| `Transcript_Data_Call/` | Input folder. Drop `.txt` call transcripts here (format: `Sales Rep` / `Customer` dialogue). |
| `outputs/raw/` | Per-transcript structured analysis, one JSON file per transcript (same filename stem as the source `.txt`). |
| `outputs/reports/` | Daily Markdown reports, named `daily_report_YYYY-MM-DD.md`, summarizing all calls analyzed that day. |
| `.env` | Local environment file holding `ANTHROPIC_API_KEY`. **Not committed to git** (see `.gitignore`). |
| `.gitignore` | Excludes `.env`, `__pycache__/`, `*.pyc`, and local Claude settings from version control. |
| `Output_Images/` | Reference screenshots related to the project. |

## Setup

1. Install dependencies:
   ```powershell
   pip install anthropic watchdog
   ```
2. Set your API key as an environment variable:
   ```powershell
   $env:ANTHROPIC_API_KEY = "your-api-key-here"
   ```

## Usage

**Run a one-off batch analysis** (processes all transcripts currently in `Transcript_Data_Call/` and regenerates the daily report):
```powershell
python sentiment_pipeline.py
```

**Run the folder watcher** (continuously processes new transcripts as they're added):
```powershell
python watcher.py
```

## Daily report contents

Each `daily_report_YYYY-MM-DD.md` includes:
- Total calls processed
- Sentiment breakdown (positive / neutral / negative)
- Customer interest level breakdown (high / medium / low)
- Top recurring objections across all calls
- Top topics/products mentioned
- List of high-interest customers with call summaries
- Overall recommendation for the sales head
