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
ML_CONTENT_TYPE_TO_INTERNAL = {
    "personal_feeling": "personal feeling",
    "factual_news": "news/fact",
    "goal_task": "goal/task",
    "memory": "memory",
    "relationship": "relationship",
    "uncertainty": "uncertainty",
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
        "is",
        "not",
        "when",
        "you",
        "are",
        "especially",
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
            parts = pair.split()
            if (
                not any(part.lower() in stop_words for part in parts)
                and any(len(part) > 3 for part in parts)
            ):
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
    ml_prediction = predict_input_pattern_safe(text)
    if ml_prediction:
        return build_analysis_from_prediction(text, ml_prediction)
    return analyze_input_rule_based(text)


def predict_input_pattern_safe(text):
    try:
        from ml.predictor import predict_input_pattern

        return predict_input_pattern(text)
    except Exception:
        return None


def build_analysis_from_prediction(text, prediction):
    cleaned = clean_ai_text(text)
    text_lower = cleaned.lower()
    content_type = ML_CONTENT_TYPE_TO_INTERNAL.get(
        prediction.get("content_type"), detect_content_type(text_lower)
    )
    emotional_tone = prediction.get("tone") or detect_emotional_tone(text_lower)
    intensity = prediction.get("intensity") or detect_intensity(text_lower)
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
        "intensity": intensity,
        "key_phrases": extract_key_phrases(cleaned),
        "is_factual": is_factual,
        "is_emotional": not is_factual
        and (
            emotional_tone != "neutral"
            or content_type in ("personal feeling", "relationship", "memory", "uncertainty")
        ),
        "source": prediction.get("source", "ml_classifier"),
    }


def analyze_input_rule_based(text):
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
        "source": "rule_based",
    }


def choose_pattern(text, mode, action, count=5):
    basis = f"{normalize_mode(mode)}|{action}|{text}"
    return sum(ord(character) for character in basis) % count


def theme_from_analysis(analysis):
    if analysis["key_phrases"]:
        return ", ".join(analysis["key_phrases"][:3])
    return analysis["cleaned"][:90]


def input_focus(analysis):
    text = analysis["cleaned"]
    lower_text = text.lower()
    if "coming back" in lower_text and "old version" in lower_text:
        return "coming back feels difficult because you are returning as someone changed"
    if "tired" in lower_text and "better" in lower_text:
        return "tiredness and the wish to become better are both present"
    if analysis["content_type"] == "news/fact":
        return f"the public detail: {text}"
    if analysis["content_type"] == "goal/task":
        return f"the task pressure around {theme_from_analysis(analysis)}"
    if analysis["content_type"] == "memory":
        return f"the memory carried by {theme_from_analysis(analysis)}"
    if analysis["content_type"] == "relationship":
        return f"the relationship signal around {theme_from_analysis(analysis)}"
    if analysis["content_type"] == "uncertainty":
        return f"the uncertainty around {theme_from_analysis(analysis)}"
    return theme_from_analysis(analysis)


def meaning_for(analysis):
    text = analysis["cleaned"]
    lower_text = text.lower()
    if "temporary restraining order" in lower_text and "removal case" in lower_text:
        return "The case continues without that temporary protection."
    if "coming back" in lower_text and "old version" in lower_text:
        return "You may be comparing your current self to an older version, and that makes returning feel heavier."
    if "tired" in lower_text and "better" in lower_text:
        return "Your energy is low, but your direction still matters."
    if analysis["is_factual"]:
        return factual_meaning(analysis)
    if analysis["content_type"] == "goal/task":
        return "Avoidance may be a sign that the first step needs to be smaller."
    if analysis["content_type"] == "memory":
        return "The past is asking to be honored without becoming the only place you can belong."
    if analysis["content_type"] == "relationship":
        return "The feeling points toward a need for care, clarity, or repair."
    if analysis["content_type"] == "uncertainty":
        return "The unknown is taking up space because the next choice is not clear yet."
    return "This is a personal reflection, so the emotional pattern matters as much as the facts."


def next_step_for(analysis):
    text_lower = analysis["cleaned"].lower()
    content_type = analysis["content_type"]
    if "temporary restraining order" in text_lower or "removal case" in text_lower:
        return "watch for the next legal filing or appeal"
    if "coming back" in text_lower and "old version" in text_lower:
        return "return slowly, without forcing yourself to become who you used to be"
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


def tone_modifier(analysis):
    tone = str(analysis["emotional_tone"])
    intensity = str(analysis["intensity"])
    modifiers = {
        "sad": "with tenderness for what feels lost",
        "anxious": "without adding pressure to what already feels tense",
        "angry": "while preserving the boundary inside the anger",
        "hopeful": "while protecting the hope that is still present",
        "neutral": "with clear attention to what happened",
        "inspired": "with respect for the energy that wants to move",
        "confused": "without pretending the answer is already clear",
    }
    base = modifiers.get(tone, modifiers["neutral"])
    if intensity == "high":
        return f"{base}, and with extra care for the intensity of it"
    return base


def mode_options(mode, analysis):
    text = analysis["cleaned"]
    lower_text = text.lower()
    sentence = sentence_case(text)
    focus = input_focus(analysis)
    meaning = meaning_for(analysis)
    next_step = next_step_for(analysis)
    tone = tone_modifier(analysis)
    is_returning = "coming back" in lower_text or "old version" in lower_text

    if mode == "Calm":
        if analysis["is_factual"]:
            return [
                f"{sentence}. A calm note can keep this factual: {meaning} From here, {next_step}.",
                f"This entry records {focus}. It does not need extra drama; it needs a clear place on the page.",
                f"{sentence}. Writing it calmly helps separate what happened from any reaction around it.",
                f"The fact to hold is simple: {text}. The next useful move is to {next_step}.",
                f"This is a public or factual detail, not a feeling to solve. {meaning}",
            ]
        return [
            f"{sentence}. You can hold this {tone}. {meaning} You only need one honest step from where you are now.",
            f"{focus.capitalize()}. Let that be enough for this page; the return does not have to happen all at once.",
            f"{sentence}. There is no need to become a past version of yourself to begin again.",
            f"This thought can be met gently: {focus}. {meaning}",
            f"{sentence}. Lower the pressure, keep the truth, and {next_step}.",
        ]

    if mode == "Cinematic":
        if analysis["is_factual"]:
            return [
                f"A decision lands in the record: {text}. The next part of the case now waits on {next_step}.",
                f"The public story turns on one sentence: {text}. What matters next is what response follows.",
                f"The room changes after the decision: {text}. The facts stay sharp, and the outcome remains unfinished.",
                f"A legal detail becomes the center of the scene: {text}. The tension is procedural, not personal.",
                f"The case moves forward under a hard fact: {text}. The next filing will decide where the story bends.",
            ]
        if is_returning:
            return [
                "The return does not feel like a grand entrance. It feels like standing at the edge of a familiar place, realizing the person who left and the person who came back are not the same.",
                f"{sentence}. In this scene, the tension is not the doorway; it is recognizing how much the person reaching for it has changed.",
                f"A familiar place waits ahead, but the old self is not the one walking toward it. That is why {focus} feels so charged.",
                f"The scene holds on the threshold: {focus}. Nothing explodes, but everything has shifted.",
                f"{sentence}. The drama is quiet: a return, a changed self, and the courage to enter without pretending.",
            ]
        return [
            f"A quiet turning point forms around {focus}. The scene is not loud, but the choice to continue gives it movement.",
            f"{sentence}. The tension is human and close: wanting change while carrying the weight of the day.",
            f"The day narrows to this honest line: {focus}. What happens next begins with one manageable step.",
            f"{sentence}. It plays like a small scene of endurance, where hope stays present even when energy is low.",
            f"The pressure sits in the foreground, but the direction is still visible: {focus}.",
        ]

    if mode == "Poetic":
        if analysis["is_factual"]:
            return [
                f"A ruling closes one gate: {text}. The case remains outside it, waiting for another opening.",
                f"The words fall with the weight of stamped paper: {text}. What is unresolved keeps its place.",
                f"A public decision becomes a hard edge on the page: {text}. The next turn has not arrived yet.",
                f"The order is denied, and the case stands in the pause after refusal.",
                f"A legal door stays shut for now: {text}. The waiting becomes part of the record.",
            ]
        if is_returning:
            return [
                "You are not the old version, and maybe that is why coming back aches. The door is familiar, but the hands reaching for it have changed.",
                f"{sentence}. The old shape does not fit, yet the path still remembers your footsteps.",
                f"Returning can ache when the self has outgrown its former name. {meaning}",
                f"{focus.capitalize()} is a quiet threshold: part memory, part becoming.",
                f"{sentence}. Something in the return asks not for the old self, but for a truer one.",
            ]
        return [
            f"{sentence}. Hope is not a flame today; it is an ember that still knows how to stay warm.",
            f"{focus.capitalize()} rests in the same hand: the ache of effort and the wish to grow.",
            f"{sentence}. Even tired soil can hold the first green thread of becoming.",
            f"The feeling is not simple, but it is alive: {focus}. Something in it still leans toward light.",
            f"{sentence}. There is beauty in wanting better even before strength has fully returned.",
        ]

    return [
        f"Main thought: {sentence}.\nMeaning: {meaning}\nNext step: {next_step}.",
        f"Key point: {focus.capitalize()}.\nMeaning: {meaning}\nNext step: {next_step}.",
        f"What is happening: {sentence}.\nWhy it matters: {meaning}\nTry next: {next_step}.",
        f"Core issue: {focus}.\nInterpretation: {meaning}\nUseful action: {next_step}.",
        f"Summary: {sentence}.\nPattern: {analysis['content_type']} with {analysis['emotional_tone']} tone.\nNext step: {next_step}.",
    ]


def transform_thought(text, mode):
    analysis = analyze_input(text)
    text = analysis["cleaned"]
    mode = normalize_mode(mode)

    if not text:
        return "Share a thought first, and PILOT will help shape it."

    options = mode_options(mode, analysis)
    return options[choose_pattern(text, mode, "Transform my thought", len(options))]


def make_softer(text, mode):
    analysis = analyze_input(text)
    text = analysis["cleaned"]
    mode = normalize_mode(mode)

    if not text:
        return "There is no rush. Start with one honest sentence, and let the rest come slowly."

    if analysis["is_factual"]:
        options = [
            f"{sentence_case(text)}. A softer version keeps the facts intact and avoids adding conclusions too early.",
            f"The note can stay simple: {text}. The next useful step is to {next_step_for(analysis)}.",
            f"This can be recorded without extra pressure: {text}. Let the facts remain clear first.",
            f"{sentence_case(text)}. It is enough to name what happened and watch what follows.",
            f"Keep the wording steady: {text}. No emotional interpretation has to be forced onto it.",
        ]
    else:
        options = [
            f"{sentence_case(text)}\nYou do not have to carry this perfectly. Keep the meaning, lower the pressure, and take one gentle step from here.",
            f"{meaning_for(analysis)}\nA softer version can begin with patience instead of blame.",
            f"{input_focus(analysis).capitalize()}.\nLet this be true without turning it into a verdict on who you are.",
            f"{sentence_case(text)}\nYou can honor the feeling and still move slowly.",
            f"This is tender, not final: {input_focus(analysis)}. Give it room before asking it for answers.",
        ]
    return options[choose_pattern(text, mode, "Make it softer", len(options))]


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

    return (
        f"Tone: {analysis['emotional_tone']} ({analysis['intensity']} intensity).\n"
        f"Theme: {theme_from_analysis(analysis)}.\n"
        f"Meaning: {meaning_for(analysis)} Mode lens: {profile['purpose']}\n"
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

    analysis = analyze_input(text)
    debug = {
        "mode": mode,
        "action": action,
        "tone": str(analysis["emotional_tone"]),
        "content_type": analysis["content_type"],
        "intensity": str(analysis["intensity"]),
        "source": analysis.get("source", "unknown"),
    }
    print(
        "AI_ASSIST_DEBUG "
        f"mode={debug['mode']} "
        f"action={debug['action']} "
        f"tone={debug['tone']} "
        f"content_type={debug['content_type']} "
        f"intensity={debug['intensity']} "
        f"source={debug['source']}"
    )

    return jsonify(
        {
            "mode": mode,
            "action": action,
            "suggestion": get_ai_suggestion(text, mode, action),
            "debug": debug,
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
