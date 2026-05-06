import json
from collections import Counter
from pathlib import Path


def load_jsonl(path):
    rows = []
    with Path(path).open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON on line {line_number}: {error}") from error
    return rows


def validate_required_fields(rows, required_fields):
    missing = []
    for index, row in enumerate(rows, start=1):
        for field in required_fields:
            if field not in row or row[field] in ("", None):
                missing.append((index, field))
    if missing:
        details = ", ".join(f"line {line}: {field}" for line, field in missing[:10])
        raise ValueError(f"Missing required fields: {details}")
    return True


def print_label_counts(rows, fields):
    for field in fields:
        counts = Counter(row[field] for row in rows)
        print(f"{field} counts:")
        for label, count in sorted(counts.items()):
            print(f"  {label}: {count}")
