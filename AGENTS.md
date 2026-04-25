# PILOT Agent Guide

## Project Overview

PILOT is a beginner-friendly Flask app for private anime-themed journaling. It uses SQLite for local storage, Flask sessions for authentication state, and Jinja templates for the UI.

## Setup Commands

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

## Run Command

```powershell
py app.py
```

The local app runs at http://127.0.0.1:5000.

## Code Style Rules

- Keep code beginner-friendly and readable.
- Use Flask, SQLite, HTML, CSS, and minimal JavaScript.
- Keep route logic straightforward.
- Prefer small helper functions over clever abstractions.
- Keep templates simple and descriptive.
- Do not add paid APIs or extra web frameworks.

## Security Rules

- Never store plain text passwords.
- Always use `generate_password_hash` and `check_password_hash`.
- Users can only access their own journal entries.
- Keep dashboard, new entry, and delete routes protected behind login.
- Do not expose `database.db` or commit local database files.
