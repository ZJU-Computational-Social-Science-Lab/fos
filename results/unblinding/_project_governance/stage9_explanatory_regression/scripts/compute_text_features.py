# Compute the automatable text features (spec features 7-10, 12) for all 38
# contrasts from the verbatim arm texts in arm_texts_original.py /
# arm_texts_expansion.py, and write text_features.csv plus a human-readable
# evidence log (negation hits, first-difference excerpts).
#
# Functions:
#   normalize(text)      -> lowercase, punctuation stripped, whitespace tokens
#   wording_difference() -> proportion of tokens changed between two arms
#   manipulation_location() -> relative position (0-1) of the first changed token
#   negation_tokens()    -> negation-list hits in an arm text
#   main()               -> writes text_features.csv and text_features_evidence.txt

import csv
import difflib
import re
from pathlib import Path

from arm_texts_original import CONTRAST_ARMS_ORIGINAL
from arm_texts_expansion import CONTRAST_ARMS_EXPANSION

OUT_DIR = Path(__file__).resolve().parent.parent

# Fixed negation token list required by the spec (searched on lowercased,
# punctuation-stripped tokens; contractions are matched on their stem, e.g.
# "doesn't" -> "doesn", "t" after stripping the apostrophe).
NEGATION_TOKENS = [
    "no", "not", "never", "none", "cannot", "dont", "doesnt", "isnt",
    "arent", "wont", "wouldnt", "shouldnt", "couldnt", "without",
    "neither", "nor", "unlikely",
]


def normalize(text):
    """Lowercase, strip punctuation, and split into whitespace tokens."""
    lowered = text.lower()
    stripped = re.sub(r"[^\w\s%$/]", " ", lowered)
    return stripped.split()


def diff_opcodes(tokens_a, tokens_b):
    """SequenceMatcher opcodes between two normalized token lists."""
    matcher = difflib.SequenceMatcher(a=tokens_a, b=tokens_b, autojunk=False)
    return matcher.get_opcodes()


def changed_token_count(opcodes):
    """Count replace+delete+insert tokens across all opcodes."""
    total = 0
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "replace":
            total += (i2 - i1) + (j2 - j1)
        elif tag == "delete":
            total += i2 - i1
        elif tag == "insert":
            total += j2 - j1
    return total


def first_change_position(opcodes, tokens_a):
    """Position (index into arm A tokens) of the first changed token, or None."""
    for tag, i1, i2, j1, j2 in opcodes:
        if tag != "equal":
            return i1
    return None


def negation_tokens(text):
    """Return the set of negation-list tokens present in a text."""
    tokens = set(normalize(text))
    found = set()
    for neg in NEGATION_TOKENS:
        if neg in tokens:
            found.add(neg)
    # contraction stems keep the apostrophe-stripped form together, e.g. "doesn" + "t"
    return found


def excerpt_around(tokens, index, window=8):
    """Readable excerpt of tokens around a position, for the evidence log."""
    start = max(0, index - window)
    end = min(len(tokens), index + window + 1)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(tokens) else ""
    return prefix + " ".join(tokens[start:end]) + suffix


def compute_text_features(contrast_id, arms):
    """Compute the script-based features for one contrast."""
    tokens_a = normalize(arms["control"])
    tokens_b = normalize(arms["treatment"])
    opcodes = diff_opcodes(tokens_a, tokens_b)

    changed = changed_token_count(opcodes)
    denom = (len(tokens_a) + len(tokens_b)) / 2
    wording_diff = changed / denom if denom else 0.0

    pos = first_change_position(opcodes, tokens_a)
    if pos is None:
        location = ""
        first_diff_excerpt = "(no token difference)"
    else:
        location = round(pos / len(tokens_a), 4)
        first_diff_excerpt = excerpt_around(tokens_a, pos)

    neg_a = negation_tokens(arms["control"])
    neg_b = negation_tokens(arms["treatment"])
    neg_diff = sorted(neg_a.symmetric_difference(neg_b))
    neg_common_hits = sorted(neg_a & neg_b)

    return {
        "contrast_id": contrast_id,
        "question_length": round((len(tokens_a) + len(tokens_b)) / 2, 1),
        "wording_difference": round(wording_diff, 4),
        "manipulation_location": location,
        "negation_tokens_control": " ".join(sorted(neg_a)),
        "negation_tokens_treatment": " ".join(sorted(neg_b)),
        "negation_tokens_changed": " ".join(neg_diff),
        "negation_common_hits": " ".join(neg_common_hits),
        "first_diff_excerpt": first_diff_excerpt,
        "n_tokens_control": len(tokens_a),
        "n_tokens_treatment": len(tokens_b),
    }


def main():
    all_arms = {**CONTRAST_ARMS_ORIGINAL, **CONTRAST_ARMS_EXPANSION}
    rows = []
    evidence_lines = []
    for contrast_id in sorted(all_arms):
        row = compute_text_features(contrast_id, all_arms[contrast_id])
        rows.append(row)
        evidence_lines.append(
            f"== {contrast_id} ({all_arms[contrast_id]['control_label']} vs "
            f"{all_arms[contrast_id]['treatment_label']})\n"
            f"  tokens: {row['n_tokens_control']} vs {row['n_tokens_treatment']} "
            f"(mean {row['question_length']})\n"
            f"  wording_difference: {row['wording_difference']}\n"
            f"  first change at token {row['manipulation_location']}: "
            f"{row['first_diff_excerpt']}\n"
            f"  negations control: [{row['negation_tokens_control']}]\n"
            f"  negations treatment: [{row['negation_tokens_treatment']}]\n"
            f"  negation sets differ by: [{row['negation_tokens_changed']}]\n"
            f"  negations hit in BOTH arms (manual-check candidates): "
            f"[{row['negation_common_hits']}]\n"
        )
    with open(OUT_DIR / "text_features.csv", "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    (OUT_DIR / "text_features_evidence.txt").write_text("\n".join(evidence_lines))
    print(f"wrote text_features.csv and text_features_evidence.txt for {len(rows)} contrasts")


if __name__ == "__main__":
    main()
