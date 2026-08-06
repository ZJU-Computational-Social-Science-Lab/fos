#!/usr/bin/env python3
"""
Download Reddit comments + submissions for April 2019 from Hugging Face,
decompress them with zstd long-range mode, count how many times each author
posted, and save the busy authors (25+ posts) to april_2019_users.csv.

This script does the work in three stages:
  1. download()  — fetch the two compressed files from Hugging Face with curl
     (resuming an interrupted download with -C - when needed)
  2. process_file() — stream each file through `zstd -d -c --long=31`, read the
     decompressed JSON lines one at a time, and count each author
  3. save_and_report() — keep authors with 25+ posts, write them to the CSV,
     and print the summary + top 20

The files are several gigabytes when decompressed, so we never load them into
memory. Only the author counter grows.
"""

import csv
import json
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_CSV = REPO_ROOT / "april_2019_users.csv"
MIN_COUNT = 25

# Authors we never count: deleted accounts and the AutoModerator bot.
EXCLUDE_AUTHORS = {"[deleted]", "AutoModerator"}

@dataclass(frozen=True)
class RedditFile:
    """One compressed file to download and process: its display name, URL,
    and the filename it is saved as on disk."""

    name: str
    url: str
    filename: str


FILES = [
    RedditFile(
        name="comments (RC_2019-04.zst)",
        url="https://huggingface.co/datasets/peternasser99/reddit/resolve/main/comments/RC_2019-04.zst",
        filename="RC_2019-04.zst",
    ),
    RedditFile(
        name="submissions (RS_2019-04.zst)",
        url="https://huggingface.co/datasets/peternasser99/reddit/resolve/main/submissions/RS_2019-04.zst",
        filename="RS_2019-04.zst",
    ),
]


def download_file(url: str, dest: Path) -> None:
    """Download one .zst file from Hugging Face to the given path.

    Uses curl with -L to follow redirects and -C - to resume an interrupted
    download instead of starting over. Raises SystemExit if curl fails.
    """
    print(f"Downloading {url}", flush=True)
    print(f"  -> {dest}", flush=True)
    result = subprocess.run(
        ["curl", "-L", "-C", "-", "-o", str(dest), url],
        check=False,
    )
    if result.returncode != 0:
        print(
            f"ERROR: curl failed with exit code {result.returncode} for {url}",
            flush=True,
        )
        sys.exit(1)
    size_mb = dest.stat().st_size / (1024 * 1024)
    print(f"Downloaded {dest.name}: {size_mb:.1f} MB", flush=True)


def process_file(path: Path, counter: Counter, file_label: str) -> int:
    """Stream one .zst file through zstd and count each author.

    Decompresses with `zstd -d -c --long=31` in a subprocess and reads the
    JSON lines from its stdout one by one, so the whole file never fits in
    memory. Returns the number of lines that could not be parsed as JSON.
    """
    if not shutil.which("zstd"):
        print(
            "ERROR: zstd is not installed. Install it (e.g. `apt install zstd`) and rerun.",
            flush=True,
        )
        sys.exit(1)

    cmd = ["zstd", "-d", "-c", "--long=31", str(path)]
    print(f"Processing {file_label} with: {' '.join(cmd)}", flush=True)
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    skipped = 0
    lines = 0
    assert proc.stdout is not None
    for raw_line in proc.stdout:
        lines += 1
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError:
            skipped += 1
            continue
        author = record.get("author")
        if author and author not in EXCLUDE_AUTHORS:
            counter[author] += 1
        if lines % 5_000_000 == 0:
            print(
                f"  {file_label}: {lines/1_000_000:.0f}M lines, "
                f"{len(counter):,} unique authors so far",
                flush=True,
            )

    proc.wait()
    print(
        f"Done with {file_label}: {lines:,} lines, {skipped:,} unparseable, "
        f"{len(counter):,} unique authors total",
        flush=True,
    )
    return skipped


def save_and_report(counter: Counter) -> None:
    """Filter to busy authors (>= 25 posts), write the CSV, print the summary.

    The CSV lives at the repo root as april_2019_users.csv with the columns
    username,count, sorted from busiest to least busy.
    """
    busy = [(author, count) for author, count in counter.items() if count >= MIN_COUNT]
    busy.sort(key=lambda pair: pair[1], reverse=True)

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["username", "count"])
        for author, count in busy:
            writer.writerow([author, count])
    print(f"Saved {len(busy)} authors (>= {MIN_COUNT} posts) to {OUTPUT_CSV}", flush=True)

    print(f"\n{'=' * 60}")
    print(f"TOTAL UNIQUE AUTHORS: {len(counter):,}")
    print(f"AUTHORS WITH >= {MIN_COUNT} POSTS: {len(busy):,}")
    print(f"{'=' * 60}")
    print("TOP 20 AUTHORS")
    print(f"{'=' * 60}")
    print(f"{'rank':>4}  {'username':<30} {'count':>8}")
    print("-" * 60)
    for rank, (author, count) in enumerate(busy[:20], 1):
        print(f"{rank:>4}  {author:<30} {count:>8}")

def main() -> int:
    """Run the download -> count -> save pipeline, then clean up."""
    workdir = Path(tempfile.mkdtemp(prefix="april2019_"))
    counter: Counter = Counter()
    total_skipped = 0

    try:
        for file_info in FILES:
            dest = workdir / file_info.filename
            download_file(file_info.url, dest)
            total_skipped += process_file(dest, counter, file_info.name)

        if total_skipped:
            print(f"Note: {total_skipped:,} JSON lines were skipped as unparseable", flush=True)

        save_and_report(counter)
        return 0
    finally:
        # Clean up the downloaded .zst files (multi-GB) regardless of outcome.
        shutil.rmtree(workdir, ignore_errors=True)
        print(f"Cleaned up temporary files in {workdir}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
