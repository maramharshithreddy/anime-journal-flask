# PILOT

PILOT is a private Flask journaling app for saving thoughts, moods, and episode notes in a subtle interface environment.

## Features

- User registration, login, and logout
- Password hashing with Werkzeug
- Private journal entries stored per user
- Create and delete journal entries
- Mood selection for each entry
- Dashboard entry cards with previews
- Flash messages for success and error states
- Live character counter on the journal entry form

## Tech Stack

- Python
- Flask
- SQLite
- HTML templates with Jinja
- CSS
- Minimal JavaScript

## Setup On Windows

Create and activate a virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
py -m pip install -r requirements.txt
```

## Run

Start the development server:

```powershell
py app.py
```

Open http://127.0.0.1:5000 in your browser.

## Usage Flow

1. Register a new account.
2. Log in with your username and password.
3. Create a journal entry from the New Entry page.
4. Review your entries on the dashboard.
5. Delete entries you no longer want.
6. Log out when you are finished.

## Database

The app uses `database.db`, which is generated locally when the app starts. This file is ignored by Git so each developer has their own local database.

## Optional Local ML

PILOT includes optional local ML input-pattern recognition for tone, content type, and intensity. The Flask app still works without trained models because it falls back to the rule-based analyzer.

Train the classifiers:

```powershell
py ml/train_tone_classifier.py
```

Evaluate them:

```powershell
py ml/evaluate_classifier.py
```

The trained `.joblib` model files are saved in `models/`.

## Screenshots

Screenshots will be added later.
