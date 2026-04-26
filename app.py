import sqlite3

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
# Development-only secret key. In production, load this from an environment variable.
app.secret_key = "anime-journal-dev-key"

DATABASE = "database.db"
JOURNAL_MODES = ("Calm", "Cinematic", "Poetic", "Clarity")
AI_ACTIONS = ("Transform my thought", "Make it softer", "Summarize meaning")
MODE_BEHAVIOR = {
    "Calm": {
        "label": "Calm suggestion",
        "voice": "soft, peaceful, grounding, emotionally gentle",
        "opening": "I can let this arrive gently.",
        "bridge": "There is room to breathe around it.",
        "image": "like petals resting on quiet water",
        "next_step": "pause, name the feeling, and offer myself one small kindness",
    },
    "Cinematic": {
        "label": "Cinematic suggestion",
        "voice": "visual, story-like, dramatic, scene-based",
        "opening": "The scene opens in a wash of blue-pink light.",
        "bridge": "The camera lingers on the feeling before anything needs to be solved.",
        "image": "like a final frame held after the music softens",
        "next_step": "notice the image, the tension, and the choice the scene is pointing toward",
    },
    "Poetic": {
        "label": "Poetic suggestion",
        "voice": "expressive, metaphorical, lyrical, beautiful",
        "opening": "Something tender is trying to become language.",
        "bridge": "It moves through me with a small shimmer of truth.",
        "image": "like a blossom crossing the sky before dusk",
        "next_step": "keep the image that glows and let the rest fall away",
    },
    "Clarity": {
        "label": "Clarity suggestion",
        "voice": "organized, practical, clean, action-oriented",
        "opening": "Here is the thought in clearer shape.",
        "bridge": "I can separate the feeling from the next step.",
        "image": "like a clean horizon after the clouds open",
        "next_step": "identify what matters, what can wait, and one action I can take",
    },
}


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


def mode_profile(mode):
    return MODE_BEHAVIOR[normalize_mode(mode)]


def sentence_case(text):
    text = clean_ai_text(text)
    if not text:
        return ""
    return text[0].upper() + text[1:]


def infer_emotional_tone(text, mode):
    text_lower = text.lower()
    if any(word in text_lower for word in ("tired", "overwhelmed", "sad", "heavy")):
        return "heavy but honest"
    if any(word in text_lower for word in ("happy", "hopeful", "excited", "inspired")):
        return "bright and hopeful"
    if mode == "Clarity":
        return "focused and reflective"
    if mode == "Cinematic":
        return "vivid and emotionally charged"
    if mode == "Poetic":
        return "tender and expressive"
    return "quiet and reflective"


def infer_main_theme(text):
    text = clean_ai_text(text)
    if len(text) <= 90:
        return text
    return f"{text[:87]}..."


def transform_thought(text, mode):
    text = clean_ai_text(text)
    profile = mode_profile(mode)

    if not text:
        return "Share a thought first, and PILOT will help shape it."

    if normalize_mode(mode) == "Clarity":
        return (
            f"{profile['label']}:\n"
            f"{profile['opening']}\n"
            f"Thought: {sentence_case(text)}\n"
            f"Meaning: {profile['bridge']}\n"
            f"Next step: {profile['next_step']}."
        )

    return (
        f"{profile['label']}:\n"
        f"{profile['opening']} {sentence_case(text)}\n"
        f"{profile['bridge']} It feels {profile['image']}, and it deserves a page where it can be seen without being forced."
    )


def make_softer(text, mode):
    text = clean_ai_text(text)
    mode = normalize_mode(mode)
    profile = mode_profile(mode)

    if not text:
        return "There is no rush. Start with one honest sentence, and let the rest come slowly."

    return (
        f"{mode} softer suggestion:\n"
        "I do not have to carry this perfectly.\n"
        f"{sentence_case(text)}\n"
        f"I can meet this with the {profile['voice']} tone of this mode: {profile['next_step']}."
    )


def summarize_meaning(text, mode):
    text = clean_ai_text(text)
    mode = normalize_mode(mode)
    profile = mode_profile(mode)

    if not text:
        return (
            "Emotional tone: quiet and open.\n"
            "Main theme: a thought waiting to be named.\n"
            "Possible next step: write one sentence about what you feel right now."
        )

    return (
        f"Emotional tone: {infer_emotional_tone(text, mode)}.\n"
        f"Main theme: {infer_main_theme(text)}\n"
        f"Mode lens: {profile['voice']}.\n"
        f"Possible next step: {profile['next_step']}."
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
