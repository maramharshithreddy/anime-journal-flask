from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from dataset_utils import load_jsonl, print_label_counts, validate_required_fields


ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "datasets" / "tone_classifier_samples.jsonl"
MODELS_DIR = ROOT / "models"
FIELDS = ("tone", "content_type", "intensity")


def build_pipeline():
    return Pipeline(
        steps=[
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
            ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced")),
        ]
    )


def train_classifier(rows, label_field):
    model = build_pipeline()
    texts = [row["text"] for row in rows]
    labels = [row[label_field] for row in rows]
    model.fit(texts, labels)
    return model


def main():
    rows = load_jsonl(DATASET_PATH)
    validate_required_fields(rows, ("text", *FIELDS))
    print_label_counts(rows, FIELDS)

    MODELS_DIR.mkdir(exist_ok=True)
    for field in FIELDS:
        model = train_classifier(rows, field)
        output_path = MODELS_DIR / f"{field}_classifier.joblib"
        joblib.dump(model, output_path)
        print(f"Saved {field} classifier to {output_path}")


if __name__ == "__main__":
    main()
