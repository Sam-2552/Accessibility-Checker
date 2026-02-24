"""AppLens Flask web application."""

import json
import os
import sys
import time
from functools import wraps
from pathlib import Path

# Load .env from parent project directory before anything else
_parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(_parent_dir))

try:
    from dotenv import load_dotenv
    load_dotenv(_parent_dir / ".env")
except ImportError:
    pass

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, jsonify, Response, flash, g, send_file,
)

import db
from db import redact_credentials
import worker as wk

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-me-in-production-webapt-2025")

# ── Auth helpers ───────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = session.get("token")
        user = db.get_session_user(token)
        if not user:
            return redirect(url_for("login", next=request.path))
        g.user = user
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = session.get("token")
        user = db.get_session_user(token)
        if not user or not user["is_admin"]:
            return redirect(url_for("dashboard"))
        g.user = user
        return f(*args, **kwargs)
    return decorated


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    token = session.get("token")
    if db.get_session_user(token):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db.authenticate(username, password)
        if user:
            token = db.create_session(user["id"])
            session["token"] = token
            next_url = request.args.get("next", url_for("dashboard"))
            return redirect(next_url)
        flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    token = session.pop("token", None)
    if token:
        db.delete_session(token)
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    queue = db.get_queue()
    my_tasks = db.get_user_tasks(g.user["id"])
    running = next((t for t in queue if t["status"] == "running"), None)
    queued = [t for t in queue if t["status"] == "queued"]
    # Redact credentials from displayed task inputs
    my_tasks = [
        {**t, "extra_task": redact_credentials(t.get("extra_task", ""))}
        for t in my_tasks
    ]
    return render_template(
        "dashboard.html",
        user=g.user,
        running=running,
        queued=queued,
        my_tasks=my_tasks,
        queue_length=len(queued),
    )


@app.route("/submit", methods=["POST"])
@login_required
def submit_task():
    import re as _re
    import csv
    import io

    input_mode = request.form.get("input_mode", "text")
    project_name = request.form.get("project_name", "").strip()

    # ── Parse input: text mode or CSV mode ─────────────────────────────────
    csv_credentials = []  # list of dicts: {url, role, username, password}

    if input_mode == "csv":
        csv_file = request.files.get("csv_file")
        if not csv_file or csv_file.filename == "":
            flash("Please select a CSV file to upload.", "error")
            return redirect(url_for("dashboard"))

        try:
            stream = io.StringIO(csv_file.stream.read().decode("utf-8-sig"))
            reader = csv.DictReader(stream)

            # Validate headers
            if reader.fieldnames is None:
                flash("CSV file is empty.", "error")
                return redirect(url_for("dashboard"))

            fieldnames_lower = [f.strip().lower() for f in reader.fieldnames]
            if "url" not in fieldnames_lower:
                flash("CSV must have a 'url' column. Found columns: "
                      + ", ".join(reader.fieldnames), "error")
                return redirect(url_for("dashboard"))

            # Build column name mapping (original → lowercase)
            col_map = {orig: low for orig, low in zip(reader.fieldnames, fieldnames_lower)}

            urls = []
            for row_num, row in enumerate(reader, start=2):
                norm_row = {col_map.get(k, k.strip().lower()): (v or "").strip() for k, v in row.items()}
                url = norm_row.get("url", "").strip()
                if not url:
                    continue
                urls.append(url)
                csv_credentials.append({
                    "url": url,
                    "role": norm_row.get("role", ""),
                    "username": norm_row.get("username", ""),
                    "password": norm_row.get("password", ""),
                })

            if not urls:
                flash("CSV contains no valid URLs.", "error")
                return redirect(url_for("dashboard"))

            # Build task_input text from CSV rows (compatible with existing pipeline)
            lines = []
            for cred in csv_credentials:
                line = cred["url"]
                parts = []
                if cred["role"]:
                    parts.append(f"role: {cred['role']}")
                if cred["username"] and cred["password"]:
                    parts.append(f"credentials: {cred['username']}/{cred['password']}")
                elif cred["username"]:
                    parts.append(f"username: {cred['username']}")
                if parts:
                    line += " - " + ", ".join(parts)
                lines.append(line)

            task_input = "\n".join(lines)

        except UnicodeDecodeError:
            flash("CSV file must be UTF-8 encoded.", "error")
            return redirect(url_for("dashboard"))
        except csv.Error as e:
            flash(f"Malformed CSV: {e}", "error")
            return redirect(url_for("dashboard"))
    else:
        task_input = request.form.get("task_input", "").strip()

    if not task_input:
        flash("Task input is required.", "error")
        return redirect(url_for("dashboard"))

    if not project_name:
        flash("Project name is required.", "error")
        return redirect(url_for("dashboard"))

    # Read scan_type from radio buttons; map 'both' → 'full' for DB storage
    scan_type = request.form.get("scan_type", "accessibility")
    if scan_type == "both":
        task_type = "full"
    elif scan_type in ("accessibility", "analysis"):
        task_type = scan_type
    else:
        task_type = "full"  # safe default

    # Extract first URL from task_input for target_url field
    url_pattern = r'https?://[^\s,;)>\]]+'
    found_urls = _re.findall(url_pattern, task_input)
    target_url = found_urls[0] if found_urls else ""

    task_id = db.enqueue_task(
        user_id=g.user["id"],
        task_type=task_type,     # accessibility / analysis / full
        target_url=target_url,   # First URL found (may be empty)
        extra_task=task_input,   # Full unified input stored here
        project_name=project_name,
    )

    # Store per-URL credentials from CSV upload
    if csv_credentials:
        db.store_task_credentials(task_id, csv_credentials)

    # Broadcast queue update
    wk.broadcast_update("queue_updated", {"queue": db.get_queue()})

    flash(f"Task #{task_id} queued successfully!", "success")
    return redirect(url_for("dashboard"))


@app.route("/task/<int:task_id>")
@login_required
def task_detail(task_id):
    task = db.get_task(task_id)
    if not task:
        flash("Task not found.", "error")
        return redirect(url_for("dashboard"))
    # Only admin or task owner can view
    if task["user_id"] != g.user["id"] and not g.user["is_admin"]:
        flash("Access denied.", "error")
        return redirect(url_for("dashboard"))

    # Redact credentials from displayed fields
    task = dict(task)
    task["extra_task"] = redact_credentials(task.get("extra_task", ""))

    # Gather downloadable files
    files = {"pdfs": [], "reports": [], "screenshots": []}
    if task.get("output_dir"):
        webapp_dir = Path(__file__).parent
        output_dir = webapp_dir / task["output_dir"]

        pdf_dir = output_dir / "pdf"
        if pdf_dir.exists():
            files["pdfs"] = [p.name for p in sorted(pdf_dir.glob("*.pdf"))]

        for report_subdir in ["accessibility_reports", "analysis_reports"]:
            rd = output_dir / report_subdir
            if rd.exists():
                files["reports"].extend(
                    [(f"{report_subdir}/{p.name}", p.stem.replace("_", " ").title())
                     for p in sorted(rd.glob("*.md"))]
                )

        qa = output_dir / "qa_report.md"
        if qa.exists():
            files["reports"].append(("qa_report.md", "QA Report"))

        ss_dir = output_dir / "screenshots"
        if ss_dir.exists():
            # rglob captures screenshots in accessibility/ and analysis/ subdirs too
            files["screenshots"] = [
                str(p.relative_to(ss_dir)) for p in sorted(ss_dir.rglob("*.png"))
            ]

    return render_template("task_detail.html", user=g.user, task=task, files=files)


@app.route("/task/<int:task_id>/download/<path:filename>")
@login_required
def download_file(task_id, filename):
    """Download (or view inline) a report file for a task."""
    task = db.get_task(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    if task["user_id"] != g.user["id"] and not g.user["is_admin"]:
        return jsonify({"error": "Access denied"}), 403
    if not task.get("output_dir"):
        return jsonify({"error": "No output available for this task"}), 404

    webapp_dir = Path(__file__).parent
    output_dir = (webapp_dir / task["output_dir"]).resolve()

    # Security: prevent path traversal
    try:
        file_path = (output_dir / filename).resolve()
    except Exception:
        return jsonify({"error": "Invalid path"}), 400

    if not str(file_path).startswith(str(output_dir) + os.sep) and str(file_path) != str(output_dir):
        return jsonify({"error": "Access denied — path escapes output directory"}), 403

    if not file_path.exists() or not file_path.is_file():
        return jsonify({"error": "File not found"}), 404

    # Images served inline; everything else as download
    suffix = file_path.suffix.lower()
    as_attachment = suffix not in {".png", ".jpg", ".jpeg", ".gif", ".webp"}
    return send_file(file_path, as_attachment=as_attachment)


@app.route("/task/<int:task_id>/files")
@login_required
def task_files(task_id):
    """Return JSON list of available files for a task."""
    task = db.get_task(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    if task["user_id"] != g.user["id"] and not g.user["is_admin"]:
        return jsonify({"error": "Access denied"}), 403
    if not task.get("output_dir"):
        return jsonify({"pdfs": [], "reports": [], "screenshots": []})

    webapp_dir = Path(__file__).parent
    output_dir = webapp_dir / task["output_dir"]

    result = {"pdfs": [], "reports": [], "screenshots": []}

    pdf_dir = output_dir / "pdf"
    if pdf_dir.exists():
        result["pdfs"] = [p.name for p in sorted(pdf_dir.glob("*.pdf"))]

    for report_subdir in ["accessibility_reports", "analysis_reports"]:
        rd = output_dir / report_subdir
        if rd.exists():
            result["reports"].extend(
                [f"{report_subdir}/{p.name}" for p in sorted(rd.glob("*.md"))]
            )

    qa = output_dir / "qa_report.md"
    if qa.exists():
        result["reports"].append("qa_report.md")

    ss_dir = output_dir / "screenshots"
    if ss_dir.exists():
        # rglob captures screenshots in accessibility/ and analysis/ subdirs too
        result["screenshots"] = [
            str(p.relative_to(ss_dir)) for p in sorted(ss_dir.rglob("*.png"))
        ]

    return jsonify(result)


@app.route("/task/<int:task_id>/cancel", methods=["POST"])
@login_required
def cancel_task(task_id):
    cancelled = db.cancel_task(task_id, g.user["id"])
    if cancelled:
        db.recompute_queue_positions()
        wk.broadcast_update("queue_updated", {"queue": db.get_queue()})
        flash(f"Task #{task_id} cancelled.", "success")
    else:
        flash("Could not cancel task (already running or not yours).", "error")
    return redirect(url_for("dashboard"))


@app.route("/admin")
@admin_required
def admin_panel():
    all_tasks = db.get_all_tasks(limit=100)
    return render_template("admin.html", user=g.user, tasks=all_tasks)


@app.route("/admin/users/create", methods=["POST"])
@admin_required
def admin_create_user():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    is_admin = bool(request.form.get("is_admin"))
    if username and password:
        ok = db.create_user(username, password, is_admin)
        flash(f"User '{username}' created." if ok else f"Username '{username}' already exists.", 
              "success" if ok else "error")
    return redirect(url_for("admin_panel"))


# ── API endpoints ──────────────────────────────────────────────────────────────

@app.route("/api/queue")
@login_required
def api_queue():
    queue = db.get_queue()
    return jsonify(queue)


@app.route("/api/task/<int:task_id>/status")
@login_required
def api_task_status(task_id):
    task = db.get_task(task_id)
    if not task:
        return jsonify({"error": "not found"}), 404
    return jsonify(task)


# ── Server-Sent Events ─────────────────────────────────────────────────────────

@app.route("/events")
@login_required
def sse_stream():
    """Real-time queue updates via SSE."""
    def generate():
        q = wk.subscribe_sse()
        try:
            # Send initial state
            queue_data = db.get_queue()
            yield f"event: queue_updated\ndata: {json.dumps({'queue': queue_data})}\n\n"

            while True:
                try:
                    msg = q.get(timeout=20)
                    yield msg
                except Exception:
                    # Heartbeat
                    yield ": heartbeat\n\n"
        finally:
            wk.unsubscribe_sse(q)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Bootstrap ──────────────────────────────────────────────────────────────────

def create_app():
    db.init_db()
    wk.start_worker()
    return app


if __name__ == "__main__":
    create_app()
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
