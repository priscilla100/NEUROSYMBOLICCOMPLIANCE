"""
connector/dataset_loader.py
────────────────────────────────────────────────────────────────────────────
Smart CSV loader that handles all three benchmark formats:

  FORMAT A — Your handmade QA benchmark:
    columns: id, question, topic, complexity, answer, regulation, ...
    question column: "question"
    ground truth:    "answer" (Yes/No)

  FORMAT B — PrivacyCI:
    columns: norm_type, sender, sender_role, recipient, recipient_role,
             subject, subject_role, information_type, consent_form,
             purpose, followed_articles, violated_articles, case_content
    question column: "case_content" (long narrative)
    ground truth:    "norm_type" (prohibit/permit)

  FORMAT C — GoldCoin:
    columns: refer_regulation, generate_HIPAA_type,
             generate_background, generate_characteristics
    question column: "generate_background" (long narrative)
    ground truth:    "generate_HIPAA_type" (Forbid/Permit)

Auto-detection is based on column name presence.
Users can also manually specify column names (for any other format).

Usage:
    rows = load_dataset("path/to/file.csv")
    for row in rows:
        print(row.question)        # always populated
        print(row.ground_truth)    # PERMITTED | DENIED | "" if unknown
        print(row.format)          # "qa" | "privacyci" | "goldcoin" | "custom"
        print(row.raw)             # original dict row
"""

import csv
import re
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Result row
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DatasetRow:
    question:     str          # the text to run through the pipeline
    ground_truth: str          # "PERMITTED" | "DENIED" | ""
    format:       str          # "qa" | "privacyci" | "goldcoin" | "custom"
    row_id:       str = ""     # id if present
    topic:        str = ""     # topic/category if present
    complexity:   str = ""     # complexity if present
    regulation:   str = ""     # cited regulation if present
    raw:          dict = field(default_factory=dict)   # original CSV row

    def is_labeled(self) -> bool:
        return self.ground_truth in ("PERMITTED", "DENIED")


# ─────────────────────────────────────────────────────────────────────────────
# Ground-truth normalization
# ─────────────────────────────────────────────────────────────────────────────

def normalize_gt(value: str) -> str:
    """Normalize any ground-truth value to PERMITTED | DENIED | ''"""
    if not value:
        return ""
    v = value.strip().lower()
    if v in ("yes", "permitted", "allowed", "permit", "true", "1"):
        return "PERMITTED"
    if v in ("no", "denied", "not permitted", "forbid", "prohibit",
             "false", "0", "violation"):
        return "DENIED"
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Format detection
# ─────────────────────────────────────────────────────────────────────────────

def detect_format(columns: list[str]) -> str:
    cols = {c.lower().strip() for c in columns}
    if "generate_background" in cols or "generate_hipaa_type" in cols:
        return "goldcoin"
    if "case_content" in cols or "norm_type" in cols:
        return "privacyci"
    if "question" in cols:
        return "qa"
    return "custom"


def detect_question_col(columns: list[str], fmt: str) -> str:
    """Return the column name that contains the question/narrative."""
    col_lower = {c.lower().strip(): c for c in columns}
    if fmt == "goldcoin":
        for k in ("generate_background", "case_content"):
            if k in col_lower: return col_lower[k]
    if fmt == "privacyci":
        for k in ("case_content",):
            if k in col_lower: return col_lower[k]
    # QA or custom — try common names
    for k in ("question", "text", "query", "input", "content", "narrative", "background"):
        if k in col_lower: return col_lower[k]
    # Last resort: first column
    return columns[0]


def detect_gt_col(columns: list[str], fmt: str) -> str:
    """Return the column name that contains the ground truth."""
    col_lower = {c.lower().strip(): c for c in columns}
    if fmt == "goldcoin":
        for k in ("generate_hipaa_type", "label", "verdict"):
            if k in col_lower: return col_lower[k]
    if fmt == "privacyci":
        for k in ("norm_type", "label", "verdict"):
            if k in col_lower: return col_lower[k]
    for k in ("answer", "label", "verdict", "ground_truth", "expected",
              "permitted", "result"):
        if k in col_lower: return col_lower[k]
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# PrivacyCI / GoldCoin question builder
# ─────────────────────────────────────────────────────────────────────────────

def privacyci_to_question(row: dict) -> str:
    """
    Convert a PrivacyCI row to a natural-language question for the pipeline.
    Extracts the key entities and purpose from the structured columns.
    """
    sender   = _clean_list(row.get("sender", ""))
    s_role   = _clean_list(row.get("sender_role", ""))
    recip    = _clean_list(row.get("recipient", ""))
    r_role   = _clean_list(row.get("recipient_role", ""))
    subject  = _clean_list(row.get("subject", ""))
    info     = _clean_list(row.get("information_type", ""))
    purpose  = row.get("purpose", "").strip()
    narrative = row.get("case_content", "").strip()

    if narrative and len(narrative) > 100:
        # Use the narrative directly — it's a full legal description
        return narrative

    # Fallback: construct a question from structured fields
    parts = []
    if sender and recip:
        parts.append(f"Can {s_role or sender} share {info or 'health information'} "
                     f"with {recip} ({r_role})?")
    if purpose:
        parts.append(f"The purpose is: {purpose}.")
    if subject:
        parts.append(f"The information is about: {subject}.")
    return " ".join(parts) if parts else narrative


def goldcoin_to_question(row: dict) -> str:
    """
    Convert a GoldCoin row to a question.
    GoldCoin has a full narrative in generate_background and structured
    characteristics in generate_characteristics.
    """
    background = row.get("generate_background", "").strip()
    chars_raw  = row.get("generate_characteristics", "").strip()

    if background and len(background) > 100:
        return background

    # Try to extract from characteristics JSON-like string
    if chars_raw:
        try:
            import ast
            chars = ast.literal_eval(chars_raw)
            if isinstance(chars, dict):
                sender  = chars.get("Sender", "")
                recip   = chars.get("Recipient", "")
                info    = chars.get("Type", "health information")
                purpose = chars.get("Purpose", "")
                q = f"Can {sender} disclose {info} to {recip}?"
                if purpose:
                    q += f" The purpose is: {purpose}."
                return q
        except Exception:
            pass

    return background or chars_raw


def _clean_list(val: str) -> str:
    """Convert "['item1', 'item2']" → "item1, item2" """
    if not val: return ""
    # Remove list brackets and quotes
    val = re.sub(r"[\[\]']", "", val).strip()
    return val


# ─────────────────────────────────────────────────────────────────────────────
# Main loader
# ─────────────────────────────────────────────────────────────────────────────

def load_dataset(
    path: str,
    question_col: Optional[str] = None,  # override auto-detection
    gt_col: Optional[str] = None,        # override auto-detection
    encoding: str = "utf-8",
) -> list[DatasetRow]:
    """
    Load any supported CSV format. Returns list of DatasetRow.

    Parameters
    ----------
    path : str
        Path to CSV file.
    question_col : str, optional
        Column name containing the question/narrative. Auto-detected if None.
    gt_col : str, optional
        Column name containing ground truth. Auto-detected if None.
    encoding : str
        File encoding (default utf-8).

    Returns
    -------
    list[DatasetRow]
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    with open(path, newline="", encoding=encoding, errors="replace") as f:
        reader = csv.DictReader(f)
        raw_rows = list(reader)
        columns  = list(reader.fieldnames or [])

    if not raw_rows:
        return []

    # Re-read fieldnames from first row since DictReader.fieldnames
    # is only populated after reading
    columns = list(raw_rows[0].keys())

    fmt        = detect_format(columns)
    q_col_used = question_col or detect_question_col(columns, fmt)
    g_col_used = gt_col       or detect_gt_col(columns, fmt)

    rows = []
    for i, raw in enumerate(raw_rows):
        # Build question text
        if fmt == "privacyci":
            question = privacyci_to_question(raw)
        elif fmt == "goldcoin":
            question = goldcoin_to_question(raw)
        else:
            question = raw.get(q_col_used, "").strip()

        if not question:
            if i == 0 and fmt == "other" and q_col_used not in raw:
                print(f"  WARNING: question column '{q_col_used}' not found in CSV. "
                      f"Available columns: {list(raw.keys())[:8]}")
            continue

        # Ground truth
        gt_raw = raw.get(g_col_used, "").strip() if g_col_used else ""
        gt     = normalize_gt(gt_raw)

        rows.append(DatasetRow(
            question     = question,
            ground_truth = gt,
            format       = fmt,
            row_id       = str(raw.get("id", i + 1)),
            topic        = raw.get("topic", raw.get("category", "")),
            complexity   = raw.get("complexity", ""),
            regulation   = raw.get("regulation", raw.get("refer_regulation",
                           raw.get("followed_articles", ""))),
            raw          = dict(raw),
        ))

    return rows


def load_dataset_from_bytes(
    content: bytes,
    filename: str = "upload.csv",
    question_col: Optional[str] = None,
    gt_col: Optional[str] = None,
) -> tuple[list[DatasetRow], str, str]:
    """
    Load from bytes (e.g. Streamlit file_uploader).
    Returns (rows, detected_question_col, detected_gt_col).
    """
    text    = content.decode("utf-8", errors="replace")
    reader  = csv.DictReader(io.StringIO(text))
    raw_rows = list(reader)
    if not raw_rows:
        return [], "", ""

    columns    = list(raw_rows[0].keys())
    fmt        = detect_format(columns)
    q_col_used = question_col or detect_question_col(columns, fmt)
    g_col_used = gt_col       or detect_gt_col(columns, fmt)

    # Write temp file and delegate
    import tempfile, os
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv",
                                     delete=False, encoding="utf-8") as tmp:
        tmp.write(text)
        tmp_path = tmp.name

    try:
        rows = load_dataset(tmp_path, question_col, gt_col)
    finally:
        os.unlink(tmp_path)

    return rows, q_col_used, g_col_used


def describe_dataset(rows: list[DatasetRow]) -> dict:
    """Summary stats for a loaded dataset."""
    labeled   = [r for r in rows if r.is_labeled()]
    permitted = sum(1 for r in labeled if r.ground_truth == "PERMITTED")
    denied    = sum(1 for r in labeled if r.ground_truth == "DENIED")
    formats   = {}
    for r in rows:
        formats[r.format] = formats.get(r.format, 0) + 1
    return {
        "total":     len(rows),
        "labeled":   len(labeled),
        "permitted": permitted,
        "denied":    denied,
        "unlabeled": len(rows) - len(labeled),
        "formats":   formats,
    }
