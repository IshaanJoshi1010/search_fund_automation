"""
Flask routes for the SFAO admin dashboard.
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, jsonify
)
from werkzeug.utils import secure_filename

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import get_session, init_db
from models import Lead, EmailLog, Thesis, ResponseStatus, EmailType

main_bp = Blueprint("main", __name__)

ATTACHMENTS_DIR = Path(__file__).parent.parent / "attachments"
ALLOWED_EXTENSIONS = {"pdf"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ── Dashboard homepage ─────────────────────────────────────────────────────────

@main_bp.route("/")
def index():
    init_db()
    session = get_session()
    try:
        today = datetime.utcnow().date()
        today_start = datetime.combine(today, datetime.min.time())

        total_leads = session.query(Lead).count()
        new_leads = session.query(Lead).filter_by(response_status=ResponseStatus.new).count()
        contacted = session.query(Lead).filter_by(response_status=ResponseStatus.contacted).count()
        replied = session.query(Lead).filter_by(response_status=ResponseStatus.replied).count()
        closed = session.query(Lead).filter_by(response_status=ResponseStatus.closed_no_response).count()
        sent_today = session.query(EmailLog).filter(EmailLog.sent_at >= today_start).count()

        stats = {
            "total_leads": total_leads,
            "new_leads": new_leads,
            "contacted": contacted,
            "replied": replied,
            "closed": closed,
            "sent_today": sent_today,
        }
        return render_template("index.html", stats=stats)
    finally:
        session.close()


# ── Leads list ─────────────────────────────────────────────────────────────────

@main_bp.route("/leads")
def leads():
    init_db()
    session = get_session()
    try:
        status_filter = request.args.get("status", "all")
        page = int(request.args.get("page", 1))
        per_page = 25

        query = session.query(Lead)
        if status_filter != "all":
            query = query.filter(Lead.response_status == status_filter)

        query = query.order_by(Lead.created_at.desc())
        total = query.count()
        leads_list = query.offset((page - 1) * per_page).limit(per_page).all()
        total_pages = max(1, (total + per_page - 1) // per_page)

        return render_template(
            "leads.html",
            leads=leads_list,
            status_filter=status_filter,
            page=page,
            total_pages=total_pages,
            total=total,
            statuses=[s.value for s in ResponseStatus],
        )
    finally:
        session.close()


# ── Email logs ─────────────────────────────────────────────────────────────────

@main_bp.route("/logs")
def logs():
    init_db()
    session = get_session()
    try:
        page = int(request.args.get("page", 1))
        per_page = 50
        query = session.query(EmailLog).order_by(EmailLog.sent_at.desc())
        total = query.count()
        email_logs = query.offset((page - 1) * per_page).limit(per_page).all()
        total_pages = max(1, (total + per_page - 1) // per_page)

        return render_template(
            "logs.html",
            logs=email_logs,
            page=page,
            total_pages=total_pages,
            total=total,
        )
    finally:
        session.close()


# ── Upload resume ──────────────────────────────────────────────────────────────

@main_bp.route("/upload/resume", methods=["GET", "POST"])
def upload_resume():
    if request.method == "POST":
        if "file" not in request.files:
            flash("No file selected.", "error")
            return redirect(request.url)
        file = request.files["file"]
        if not file.filename or not allowed_file(file.filename):
            flash("Please upload a PDF file.", "error")
            return redirect(request.url)

        ATTACHMENTS_DIR.mkdir(exist_ok=True)
        dest = ATTACHMENTS_DIR / "resume.pdf"
        file.save(dest)
        flash(f"✓ Resume uploaded: resume.pdf ({dest.stat().st_size // 1024} KB)", "success")
        return redirect(url_for("main.upload_resume"))

    # Check if resume exists
    resume_exists = (ATTACHMENTS_DIR / "resume.pdf").exists()
    return render_template("upload_resume.html", resume_exists=resume_exists)


# ── Upload thesis ──────────────────────────────────────────────────────────────

@main_bp.route("/upload/thesis", methods=["GET", "POST"])
def upload_thesis():
    init_db()
    session = get_session()

    if request.method == "POST":
        if "file" not in request.files:
            flash("No file selected.", "error")
            return redirect(request.url)

        file = request.files["file"]
        industry_label = request.form.get("industry_label", "").strip()

        if not file.filename or not allowed_file(file.filename):
            flash("Please upload a PDF file.", "error")
            return redirect(request.url)

        if not industry_label:
            flash("Please provide an industry label.", "error")
            return redirect(request.url)

        ATTACHMENTS_DIR.mkdir(exist_ok=True)
        safe_label = industry_label.lower().replace(" ", "_")
        filename = f"thesis_{safe_label}.pdf"
        dest = ATTACHMENTS_DIR / filename
        file.save(dest)

        # Upsert in DB
        existing = session.query(Thesis).filter_by(industry_label=industry_label).first()
        if existing:
            existing.filepath = str(dest)
            existing.filename = filename
        else:
            thesis = Thesis(filename=filename, industry_label=industry_label, filepath=str(dest))
            session.add(thesis)
        session.commit()
        flash(f"✓ Thesis uploaded: {filename}", "success")
        session.close()
        return redirect(url_for("main.upload_thesis"))

    theses = session.query(Thesis).order_by(Thesis.created_at.desc()).all()
    session.close()
    return render_template("upload_thesis.html", theses=theses)


# ── Manual run triggers ────────────────────────────────────────────────────────

@main_bp.route("/run/discovery")
def run_discovery_route():
    from scraper.orchestrator import run_discovery
    from classifier.lead_classifier import classify_all_unclassified
    count = run_discovery()
    session = get_session()
    try:
        classified = classify_all_unclassified(session)
    finally:
        session.close()
    flash(f"✓ Discovery complete: {count} new leads found, {classified} classified.", "success")
    return redirect(url_for("main.index"))


@main_bp.route("/run/send")
def run_send_route():
    from email_client.dispatcher import run_send_batch
    count = run_send_batch()
    dry = os.getenv("SFAO_DRY_RUN", "true").lower() == "true"
    mode = "(DRY RUN)" if dry else ""
    flash(f"✓ Send batch complete {mode}: {count} emails sent.", "success")
    return redirect(url_for("main.index"))


@main_bp.route("/run/followup")
def run_followup_route():
    from scheduler.followup_job import run_followup_job
    count = run_followup_job()
    flash(f"✓ Follow-up job complete: {count} follow-ups sent.", "success")
    return redirect(url_for("main.index"))


@main_bp.route("/run/poll")
def run_poll_route():
    dry = os.getenv("SFAO_DRY_RUN", "true").lower() == "true"
    if dry:
        flash("Response poll skipped — SFAO_DRY_RUN=true.", "info")
        return redirect(url_for("main.index"))
    from email_client.response_poller import poll_for_replies
    count = poll_for_replies()
    flash(f"✓ Reply poll complete: {count} new replies detected.", "success")
    return redirect(url_for("main.index"))
