File / Folder	Description
sentiment_pipeline.py	Core pipeline. Reads all transcripts from Transcript_Data_Call/, calls the Claude API to analyze each one, saves per-call JSON to outputs/raw/, and generates the daily report in outputs/reports/. Can be run standalone for a one-off batch run.
watcher.py	Background folder watcher (using watchdog). Monitors Transcript_Data_Call/ continuously — the moment a new .txt file is added, it analyzes that single file, saves its JSON output, and regenerates the daily report from all results so far. Runs indefinitely until stopped (Ctrl+C).
Transcript_Data_Call/	Input folder. Drop .txt call transcripts here (format: Sales Rep / Customer dialogue).
outputs/raw/	Per-transcript structured analysis, one JSON file per transcript (same filename stem as the source .txt).
outputs/reports/	Daily Markdown reports, named daily_report_YYYY-MM-DD.md, summarizing all calls analyzed that day.
.env	Local environment file holding ANTHROPIC_API_KEY. Not committed to git (see .gitignore).
.gitignore	Excludes .env, __pycache__/, *.pyc, and local Claude settings from version control.
