# PILOT ML Classifier

PILOT includes an optional local machine-learning layer for input-pattern recognition. The Flask app still works without trained models because `app.py` falls back to its rule-based analyzer whenever model files are missing or prediction fails.

## What It Predicts

The classifier predicts three labels from a raw journal thought:

- `tone`
- `content_type`
- `intensity`

These labels help PILOT choose calmer, clearer, more mode-aware mock AI suggestions.

## Dataset Format

`datasets/tone_classifier_samples.jsonl` contains one JSON object per line:

```json
{"text":"I feel tired but hopeful","tone":"hopeful","content_type":"personal_feeling","intensity":"medium"}
```

`datasets/mode_rewrite_samples.jsonl` contains examples for future rewrite-model training:

```json
{"input":"I miss the way things used to feel","mode":"Poetic","tone":"sad","content_type":"memory","target_output":"The memory carries a quiet ache..."}
```

## Train

```powershell
py ml/train_tone_classifier.py
```

This saves:

- `models/tone_classifier.joblib`
- `models/content_type_classifier.joblib`
- `models/intensity_classifier.joblib`

## Evaluate

```powershell
py ml/evaluate_classifier.py
```

The evaluation prints accuracy for each classifier and a few example predictions.

## Flask Integration

`app.py` calls `ml.predictor.predict_input_pattern(text)` inside `analyze_input(text)`. If trained models exist, PILOT uses the ML predictions. If model files are missing, corrupted, or unavailable, PILOT safely falls back to the rule-based analyzer.
