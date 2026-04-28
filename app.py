import re
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
        "purpose": "Help the user hold the thought steadily without exaggerating it.",
        "voice": "soft, peaceful, grounding, emotionally gentle",
        "structure": "one calm reframing sentence plus one sentence of perspective",
        "avoid": ("melodrama", "forced therapy language", "overly decorative imagery"),
        "style_rules": (
            "preserve the user's meaning",
            "use plain emotional steadiness",
            "treat factual inputs as facts first",
        ),
    },
    "Cinematic": {
        "purpose": "Turn the thought into a vivid scene while preserving its facts.",
        "voice": "visual, story-like, dramatic, scene-based",
        "structure": "scene sentence, tension sentence, unresolved or reflective closing",
        "avoid": ("repeated film cliches", "stock lighting phrases", "camera cliches"),
        "style_rules": (
            "use concrete nouns from the input",
            "make factual inputs scene-like without changing facts",
            "vary the opening sentence",
        ),
    },
    "Poetic": {
        "purpose": "Make the thought expressive and beautiful without burying the meaning.",
        "voice": "expressive, metaphorical, lyrical, beautiful",
        "structure": "one careful metaphor plus one clear meaning sentence",
        "avoid": ("mixed metaphors", "vague prettiness", "repeating blossom imagery"),
        "style_rules": (
            "use one metaphor at a time",
            "keep factual inputs grounded",
            "make emotional inputs tender but not vague",
        ),
    },
    "Clarity": {
        "purpose": "Organize the thought into meaning and next action.",
        "voice": "organized, practical, clean, action-oriented",
        "structure": "Key point, Meaning, Next thought",
        "avoid": ("ornament", "emotional overreach", "long paragraphs"),
        "style_rules": (
            "separate facts from interpretation",
            "use short structured lines",
            "make the next step specific",
        ),
    },
}
EMOTION_KEYWORDS = {
    "sad": ("sad", "miss", "lonely", "hurt", "grief", "empty", "heavy", "cry"),
    "angry": ("angry", "mad", "furious", "annoyed", "unfair", "resent"),
    "anxious": ("anxious", "worried", "scared", "afraid", "panic", "stress", "nervous"),
    "hopeful": ("hopeful", "better", "improve", "possible", "trying", "still want"),
    "inspired": ("inspired", "excited", "motivated", "dream", "create", "alive"),
    "confused": ("confused", "unsure", "uncertain", "lost", "don't know", "unclear"),
}
CONTENT_KEYWORDS = {
    "goal/task": ("need to", "assignment", "finish", "task", "deadline", "work", "study"),
    "relationship": ("friend", "mother", "father", "family", "relationship", "they", "we", "someone"),
    "memory": ("remember", "used to", "back then", "miss the way", "childhood", "before"),
    "uncertainty": ("maybe", "unsure", "uncertain", "what if", "don't know", "confused"),
    "news/fact": (
        "mayor",
        "court",
        "case",
        "order",
        "denied",
        "approved",
        "announced",
        "reported",
        "removed",
        "appeal",
        "hearing",
    ),
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
    mode_lookup = {journal_mode.lower(): journal_mode for journal_mode in JOURNAL_MODES}
    normalized = mode_lookup.get(clean_ai_text(str(mode)).lower())
    if normalized:
        return normalized
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


def contains_any(text, phrases):
    return any(phrase in text for phrase in phrases)


def extract_key_phrases(text):
    text = clean_ai_text(text)
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", text)
    stop_words = {
        "the",
        "and",
        "but",
        "that",
        "this",
        "with",
        "from",
        "into",
        "about",
        "feel",
        "feeling",
        "still",
        "want",
        "need",
        "have",
        "keep",
        "to",
        "it",
        "i",
        "my",
        "me",
        "used",
        "things",
        "way",
    }
    phrases = []
    for index in range(len(words)):
        word = words[index].lower()
        if len(word) > 3 and word not in stop_words:
            phrases.append(words[index])
        if index < len(words) - 1:
            pair = f"{words[index]} {words[index + 1]}"
            if not any(part.lower() in stop_words for part in pair.split()):
                phrases.append(pair)
    return phrases[:5]


def detect_emotional_tone(text_lower):
    matched = [
        tone
        for tone, keywords in EMOTION_KEYWORDS.items()
        if contains_any(text_lower, keywords)
    ]
    if "sad" in matched:
        return "sad"
    if "angry" in matched:
        return "angry"
    if "anxious" in matched:
        return "anxious"
    if "hopeful" in matched:
        return "hopeful"
    if "inspired" in matched:
        return "inspired"
    if "confused" in matched:
        return "confused"
    return "neutral"


def detect_content_type(text_lower):
    if contains_any(text_lower, CONTENT_KEYWORDS["news/fact"]):
        return "news/fact"
    if contains_any(text_lower, CONTENT_KEYWORDS["goal/task"]):
        return "goal/task"
    if contains_any(text_lower, CONTENT_KEYWORDS["relationship"]):
        return "relationship"
    if contains_any(text_lower, CONTENT_KEYWORDS["memory"]):
        return "memory"
    if contains_any(text_lower, CONTENT_KEYWORDS["uncertainty"]):
        return "uncertainty"
    if any(pronoun in text_lower.split() for pronoun in ("i", "me", "my")):
        return "personal feeling"
    return "event summary"


def detect_intensity(text_lower):
    high_markers = ("very", "really", "so ", "panic", "furious", "terrified", "can't", "cannot")
    medium_markers = ("tired", "worried", "miss", "avoid", "unsure", "denied", "removal")
    if contains_any(text_lower, high_markers) or text_lower.count("!") >= 2:
        return "high"
    if contains_any(text_lower, medium_markers):
        return "medium"
    return "low"


def analyze_input(text):
    cleaned = clean_ai_text(text)
    text_lower = cleaned.lower()
    content_type = detect_content_type(text_lower)
    emotional_tone = detect_emotional_tone(text_lower)
    factual_markers = CONTENT_KEYWORDS["news/fact"] + (
        "temporary restraining order",
        "public",
        "official",
    )
    is_factual = content_type == "news/fact" or contains_any(text_lower, factual_markers)

    return {
        "cleaned": cleaned,
        "emotional_tone": emotional_tone,
        "content_type": content_type,
        "intensity": detect_intensity(text_lower),
        "key_phrases": extract_key_phrases(cleaned),
        "is_factual": is_factual,
        "is_emotional": not is_factual
        and (
            emotional_tone != "neutral"
            or content_type in ("personal feeling", "relationship", "memory", "uncertainty")
        ),
    }


def choose_pattern(text, mode, action):
    basis = f"{normalize_mode(mode)}|{action}|{text}"
    return sum(ord(character) for character in basis) % 3


def theme_from_analysis(analysis):
    if analysis["key_phrases"]:
        return ", ".join(analysis["key_phrases"][:3])
    return analysis["cleaned"][:90]


def next_step_for(analysis):
    content_type = analysis["content_type"]
    if content_type == "news/fact":
        return "track what decision, response, or appeal comes next"
    if content_type == "goal/task":
        return "choose the smallest next step and start there"
    if content_type == "relationship":
        return "name what you need before deciding what to say"
    if content_type == "memory":
        return "write what the memory is asking you to keep"
    if content_type == "uncertainty":
        return "separate what is known from what is still unresolved"
    return "notice the feeling and give it one clear sentence"


def factual_meaning(analysis):
    return "The note is centered on an external event, so the writing should separate the facts from any reaction around them."


def transform_thought(text, mode):
    analysis = analyze_input(text)
    text = analysis["cleaned"]
    mode = normalize_mode(mode)

    if not text:
        return "Share a thought first, and PILOT will help shape it."

    pattern = choose_pattern(text, mode, "Transform my thought")

    if mode == "Clarity":
        meaning = (
            "The situation continues without that temporary protection."
            if analysis["content_type"] == "news/fact"
            else f"The main thread is {theme_from_analysis(analysis)}."
        )
        return (
            f"Key point: {sentence_case(text)}.\n"
            f"Meaning: {meaning}\n"
            f"Next thought: {next_step_for(analysis)}."
        )

    if mode == "Calm":
        if analysis["is_factual"]:
            options = [
                f"Today's note captures a tense public detail: {text}. Writing it down helps separate the facts from the emotions around it.",
                f"This reads as a factual moment with unresolved edges: {text}. A calm page can hold what happened without rushing to decide what it means.",
                f"The entry records an external decision: {text}. Keeping it clear makes room to notice any reaction separately.",
            ]
        else:
            options = [
                f"{sentence_case(text)}. I can meet this thought gently and let it become clear one breath at a time.",
                f"This feeling can be held without being fixed immediately: {text}. I can give it patience, space, and a steadier shape.",
                f"I can write this honestly and softly: {text}. The page does not ask me to solve everything at once.",
            ]
        return options[pattern]

    if mode == "Cinematic":
        if analysis["is_factual"]:
            options = [
                f"A decision lands quietly: {text}, leaving the situation suspended in uncertainty.",
                f"The public record shifts with one hard turn: {text}. What follows now becomes the next scene to watch.",
                f"The moment has the weight of a closed door: {text}, and the case waits for its next movement.",
            ]
        else:
            options = [
                f"The moment gathers around one feeling: {text}. It moves like a scene where the smallest choice carries the most weight.",
                f"A quiet conflict takes shape: {text}. What matters is not only what happens next, but what the feeling reveals.",
                f"The scene narrows to this inner line: {text}. Everything around it seems to pause long enough to be understood.",
            ]
        return options[pattern]

    if mode == "Poetic":
        if analysis["is_factual"]:
            options = [
                f"A ruling falls like a closed gate: {text}. The matter remains outside it, waiting for another opening.",
                f"The words settle with the weight of stamped paper: {text}. What is unresolved keeps its place in the air.",
                f"A public decision becomes a hard edge on the page: {text}. The next turn has not arrived yet.",
            ]
        else:
            options = [
                f"{sentence_case(text)}. The feeling moves like a small tide, returning until it is finally named.",
                f"{sentence_case(text)}. Something in it glows softly, not to demand an answer, but to be witnessed.",
                f"{sentence_case(text)}. It carries the ache of a doorway: one side memory, the other becoming.",
            ]
        return options[pattern]

    return text


def make_softer(text, mode):
    analysis = analyze_input(text)
    text = analysis["cleaned"]
    mode = normalize_mode(mode)

    if not text:
        return "There is no rush. Start with one honest sentence, and let the rest come slowly."

    if analysis["is_factual"]:
        return (
            f"{sentence_case(text)}.\n"
            "A softer version can keep the facts intact while reducing the pressure around them. "
            f"For now, the next useful step is to {next_step_for(analysis)}."
        )

    return (
        f"{mode} softer suggestion:\n"
        f"{sentence_case(text)}\n"
        "I do not have to turn this into a judgment against myself. I can keep the meaning, lower the pressure, and take one gentle step from here."
    )


def summarize_meaning(text, mode):
    analysis = analyze_input(text)
    text = analysis["cleaned"]
    mode = normalize_mode(mode)
    profile = mode_profile(mode)

    if not text:
        return (
            "Tone: quiet and open.\n"
            "Theme: a thought waiting to be named.\n"
            "Meaning: there is not enough detail yet to infer a clear pattern.\n"
            "Next step: write one sentence about what happened or what you feel."
        )

    meaning = factual_meaning(analysis) if analysis["is_factual"] else (
        "This is a personal reflection, so the emotional pattern matters as much as the facts."
    )
    return (
        f"Tone: {analysis['emotional_tone']} ({analysis['intensity']} intensity).\n"
        f"Theme: {theme_from_analysis(analysis)}.\n"
        f"Meaning: {meaning} Mode lens: {profile['purpose']}\n"
        f"Next step: {next_step_for(analysis)}."
    )


def generate_ai_suggestion(text, mode, action):
    # Future replacement boundary:
    # - a trained classifier can replace analyze_input()
    # - a fine-tuned text generation model can replace the rule-based generators
    # - a local ML model or LLM API can be called here without changing routes/UI
    if action == "Make it softer":
        return make_softer(text, mode)
    if action == "Summarize meaning":
        return summarize_meaning(text, mode)
    return transform_thought(text, mode)


def get_ai_suggestion(text, mode, action):
    return generate_ai_suggestion(text, mode, action)


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
