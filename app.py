import sqlite3

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
# Development-only secret key. In production, load this from an environment variable.
app.secret_key = "anime-journal-dev-key"

DATABASE = "database.db"
JOURNAL_MODES = ("Calm", "Cinematic", "Poetic", "Clarity")
AI_ACTIONS = ("Transform my thought", "Make it softer", "Summarize meaning")


def get_db_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    connection = get_db_connection()
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            mood TEXT NOT NULL DEFAULT 'Calm',
            content TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """
    )
    ensure_journal_entry_columns(connection)
    connection.commit()
    connection.close()


def ensure_journal_entry_columns(connection):
    existing_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(journal_entries)").fetchall()
    }
    columns = {
        "mode": "TEXT NOT NULL DEFAULT 'Calm'",
        "original_content": "TEXT",
        "ai_output": "TEXT",
        "final_content": "TEXT",
    }

    for column_name, column_definition in columns.items():
        if column_name not in existing_columns:
            connection.execute(
                f"ALTER TABLE journal_entries ADD COLUMN {column_name} {column_definition}"
            )


def normalize_mode(mode):
    if mode in JOURNAL_MODES:
        return mode
    return "Calm"


def clean_ai_text(text):
    return " ".join(text.strip().split())


def transform_thought(text, mode):
    text = clean_ai_text(text)
    mode = normalize_mode(mode)

    if not text:
        return "Share a thought first, and PILOT will help shape it."

    if mode == "Cinematic":
        return (
            "Cinematic suggestion: The moment opens like a quiet scene: "
            f"{text} The feeling lingers in the frame, asking to be noticed."
        )
    if mode == "Poetic":
        return (
            "Poetic suggestion: "
            f"{text} It drifts through me like a soft blossom, carrying a small truth in its light."
        )
    if mode == "Clarity":
        return (
            "Clarity suggestion: "
            f"{text} Main takeaway: name the feeling, keep what matters, and choose one gentle next step."
        )

    return (
        "Calm suggestion: "
        f"{text} I can let this feeling arrive softly, breathe with it, and give it a safe place on the page."
    )


def make_softer(text, mode):
    text = clean_ai_text(text)
    mode = normalize_mode(mode)

    if not text:
        return "There is no rush. Start with one honest sentence, and let the rest come slowly."

    return (
        f"{mode} softer suggestion: I am allowed to feel this without solving it all at once. "
        f"{text} I can meet this moment with patience, care, and a little more room to breathe."
    )


def summarize_meaning(text, mode):
    text = clean_ai_text(text)
    mode = normalize_mode(mode)

    if not text:
        return (
            "Emotional tone: quiet and open.\n"
            "Main theme: a thought waiting to be named.\n"
            "Possible next step: write one sentence about what you feel right now."
        )

    return (
        f"Emotional tone: {mode.lower()} and reflective.\n"
        f"Main theme: {text[:120]}{'...' if len(text) > 120 else ''}\n"
        "Possible next step: choose one detail worth carrying forward."
    )


def get_ai_suggestion(text, mode, action):
    if action == "Make it softer":
        return make_softer(text, mode)
    if action == "Summarize meaning":
        return summarize_meaning(text, mode)
    return transform_thought(text, mode)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please enter your username and password.", "error")
            return render_template("login.html")

        connection = get_db_connection()
        user = connection.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        connection.close()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid username or password.", "error")
            return render_template("login.html")

        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        flash("You are now logged in.", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("Please fill out every field.", "error")
            return render_template("register.html")

        connection = get_db_connection()
        existing_user = connection.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?",
            (username, email),
        ).fetchone()

        if existing_user is not None:
            connection.close()
            flash("That username or email is already registered.", "error")
            return render_template("register.html")

        connection.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, generate_password_hash(password)),
        )
        connection.commit()
        connection.close()

        flash("Account created. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        flash("Please log in to view your dashboard.", "error")
        return redirect(url_for("login"))

    connection = get_db_connection()
    entries = connection.execute(
        """
        SELECT
            id,
            title,
            mode,
            mood,
            COALESCE(final_content, content) AS display_content,
            created_at
        FROM journal_entries
        WHERE user_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (session["user_id"],),
    ).fetchall()
    connection.close()

    return render_template(
        "dashboard.html", username=session["username"], entries=entries
    )


@app.route("/new_entry", methods=["GET", "POST"])
def new_entry():
    if "user_id" not in session:
        flash("Please log in to write a journal entry.", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        mode = normalize_mode(request.form.get("mode", "").strip())
        mood = request.form.get("mood", "").strip() or "Calm"
        original_content = (
            request.form.get("original_content", "").strip()
            or request.form.get("content", "").strip()
        )
        ai_output = request.form.get("ai_output", "").strip()
        final_content = request.form.get("final_content", "").strip() or original_content

        if not title or not final_content:
            flash("Title and content are required.", "error")
            return render_template(
                "new_entry.html",
                title=title,
                mode=mode,
                mood=mood,
                original_content=original_content,
                ai_output=ai_output,
                final_content=final_content,
            )

        connection = get_db_connection()
        connection.execute(
            """
            INSERT INTO journal_entries (
                user_id,
                title,
                mode,
                mood,
                content,
                original_content,
                ai_output,
                final_content
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                title,
                mode,
                mood,
                final_content,
                original_content,
                ai_output,
                final_content,
            ),
        )
        connection.commit()
        connection.close()

        flash("Journal entry saved.", "success")
        return redirect(url_for("dashboard"))

    return render_template("new_entry.html")


@app.route("/ai_assist", methods=["POST"])
def ai_assist():
    if "user_id" not in session:
        return jsonify({"error": "Please log in to use AI Assist."}), 401

    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    mode = normalize_mode(data.get("mode", "Calm"))
    action = data.get("action", "Transform my thought")

    if action not in AI_ACTIONS:
        action = "Transform my thought"

    if not text.strip():
        return jsonify({"error": "Add a thought before using AI Assist."}), 400

    return jsonify(
        {
            "mode": mode,
            "action": action,
            "suggestion": get_ai_suggestion(text, mode, action),
        }
    )


@app.route("/entries/new")
def old_new_entry():
    return redirect(url_for("new_entry"))


@app.route("/delete/<int:entry_id>", methods=["POST"])
def delete_entry(entry_id):
    if "user_id" not in session:
        flash("Please log in to manage your journal entries.", "error")
        return redirect(url_for("login"))

    connection = get_db_connection()
    result = connection.execute(
        "DELETE FROM journal_entries WHERE id = ? AND user_id = ?",
        (entry_id, session["user_id"]),
    )
    connection.commit()
    connection.close()

    if result.rowcount:
        flash("Journal entry deleted.", "success")
    else:
        flash("That journal entry could not be found.", "error")

    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
