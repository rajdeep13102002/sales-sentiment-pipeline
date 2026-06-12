"""
Folder watcher for the sales sentiment analysis pipeline.

Continuously monitors the transcript folder. The moment a new .txt file is
added, it:
  1. Analyzes that file with Claude
  2. Saves the resulting JSON to /outputs/raw
  3. Regenerates the daily report from ALL analyzed transcripts so far

Keep this script running in the background for fully automatic processing.
"""

import sys
import time
from datetime import date
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import sentiment_pipeline as pipeline

# Time to wait after a file is created before reading it, to make sure
# the writer has finished flushing the file to disk.
SETTLE_DELAY_SECONDS = 2


def regenerate_report():
    results = pipeline.load_all_results()
    report = pipeline.build_report(results)

    report_path = pipeline.REPORTS_DIR / f"daily_report_{date.today().isoformat()}.md"
    report_path.write_text(report, encoding="utf-8")

    print(f"  -> Daily report updated: {report_path}")


class TranscriptHandler(FileSystemEventHandler):
    def __init__(self, client):
        self.client = client

    def on_created(self, event):
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        if file_path.suffix.lower() != ".txt":
            return

        print(f"\n[WATCHER] New transcript detected: {file_path.name}")

        # Give the file a moment to finish being written to disk.
        time.sleep(SETTLE_DELAY_SECONDS)

        print(f"[WATCHER] Processing {file_path.name}...")
        analysis = pipeline.process_single_file(self.client, file_path)

        if analysis is not None:
            print(f"[WATCHER] Regenerating daily report...")
            regenerate_report()
        else:
            print(f"[WATCHER] {file_path.name} was skipped; report not regenerated.")


def main():
    # Ensure print statements appear immediately, even when stdout isn't a terminal.
    sys.stdout.reconfigure(line_buffering=True)

    print("=== Sales Sentiment Analysis - Folder Watcher ===")
    print(f"Watching folder: {pipeline.TRANSCRIPT_DIR}")
    print(f"Model: {pipeline.MODEL}")
    print("Waiting for new .txt files... (Press Ctrl+C to stop)\n")

    pipeline.RAW_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pipeline.REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    if not pipeline.TRANSCRIPT_DIR.is_dir():
        print(f"Creating transcript folder: {pipeline.TRANSCRIPT_DIR}")
        pipeline.TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)

    client = pipeline.get_client()

    event_handler = TranscriptHandler(client)
    observer = Observer()
    observer.schedule(event_handler, str(pipeline.TRANSCRIPT_DIR), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping watcher...")
        observer.stop()

    observer.join()
    print("Watcher stopped.")


if __name__ == "__main__":
    main()
