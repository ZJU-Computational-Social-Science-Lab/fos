# Shared helpers for the restored-stimuli tests (imported by the test
# modules above; not tests themselves).
#   load_records           — every parsed record of one records.jsonl.
#   archived_prompt_options — the option strings of one archived prompt,
#                             read back out of its "X. text" lines.
import json
from pathlib import Path


def load_records(path: Path) -> list[dict]:
    """Parse every non-blank line of one records.jsonl file."""
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def archived_prompt_options(user_prompt: str) -> list[str]:
    """The option texts of one archived prompt, in listed order.

    Archived prompts list options one per line as "A. text", "B. text",
    ... after the question text; this returns just the text parts.
    """
    options: list[str] = []
    in_options = False
    for line in user_prompt.splitlines():
        letter, separator, text = line.partition(". ")
        if separator and len(letter) == 1 and letter.isupper():
            options.append(text)
            in_options = True
        elif in_options:
            break
    return options
