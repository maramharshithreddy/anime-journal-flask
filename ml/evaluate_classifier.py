from pathlib import Path

from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

from dataset_utils import load_jsonl, validate_required_fields
from train_tone_classifier import FIELDS, build_pipeline


ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "datasets" / "tone_classifier_samples.jsonl"


def evaluate_field(rows, field):
    texts = [row["text"] for row in rows]
    labels = [row[field] for row in rows]
    train_texts, test_texts, train_labels, test_labels = train_test_split(
        texts,
        labels,
        test_size=0.25,
        random_state=42,
        stratify=labels,
    )
    model = build_pipeline()
    model.fit(train_texts, train_labels)
    predictions = model.predict(test_texts)
    accuracy = accuracy_score(test_labels, predictions)
    return accuracy, list(zip(test_texts[:5], test_labels[:5], predictions[:5]))


def main():
    rows = load_jsonl(DATASET_PATH)
    validate_required_fields(rows, ("text", *FIELDS))

    for field in FIELDS:
        accuracy, examples = evaluate_field(rows, field)
        print(f"{field} accuracy: {accuracy:.2f}")
        for text, expected, predicted in examples:
            print(f"  text: {text}")
            print(f"  expected={expected} predicted={predicted}")


if __name__ == "__main__":
    main()
