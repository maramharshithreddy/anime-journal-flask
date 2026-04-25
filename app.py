import sqlite3

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
# Development-only secret key. In production, load this from an environment variable.
app.secret_key = "anime-journal-dev-key"

DATABASE = "database.db"


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
    connection.commit()
    connection.close()


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
        SELECT id, title, mood, content, created_at
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
        mood = request.form.get("mood", "").strip() or "Calm"
        content = request.form.get("content", "").strip()

        if not title or not content:
            flash("Title and content are required.", "error")
            return render_template(
                "new_entry.html", title=title, mood=mood, content=content
            )

        connection = get_db_connection()
        connection.execute(
            """
            INSERT INTO journal_entries (user_id, title, mood, content)
            VALUES (?, ?, ?, ?)
            """,
            (session["user_id"], title, mood, content),
        )
        connection.commit()
        connection.close()

        flash("Journal entry saved.", "success")
        return redirect(url_for("dashboard"))

    return render_template("new_entry.html")


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
