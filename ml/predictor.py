from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "models"
MODEL_PATHS = {
    "tone": MODELS_DIR / "tone_classifier.joblib",
    "content_type": MODELS_DIR / "content_type_classifier.joblib",
    "intensity": MODELS_DIR / "intensity_classifier.joblib",
}
_MODEL_CACHE = None


def load_models():
    global _MODEL_CACHE
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE

    if not all(path.exists() for path in MODEL_PATHS.values()):
        return None

    try:
        import joblib

        _MODEL_CACHE = {
            label: joblib.load(path) for label, path in MODEL_PATHS.items()
        }
        return _MODEL_CACHE
    except Exception:
        _MODEL_CACHE = None
        return None


def predict_input_pattern(text):
    models = load_models()
    if not models:
        return None

    try:
        return {
            "tone": models["tone"].predict([text])[0],
            "content_type": models["content_type"].predict([text])[0],
            "intensity": models["intensity"].predict([text])[0],
            "source": "ml_classifier",
        }
    except Exception:
        return None
