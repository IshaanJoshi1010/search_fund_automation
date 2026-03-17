.PHONY: setup auth dev db-init scheduler dashboard run-discovery run-send run-followups

# ── First-time setup ───────────────────────────────────────────────────────────
setup:
	python3 -m venv .venv && \
	.venv/bin/pip install --upgrade pip && \
	.venv/bin/pip install -r requirements.txt
	cp -n .env.example .env || true
	mkdir -p attachments
	@echo "✓ Setup complete."
	@echo "  Next steps:"
	@echo "  1. Edit .env and set SENDER_EMAIL"
	@echo "  2. Download credentials.json from Google Cloud Console"
	@echo "  3. Run: make auth"
	@echo "  4. Place resume at attachments/resume.pdf"
	@echo "  5. Run: make scheduler"

# ── Gmail OAuth (one-time) ─────────────────────────────────────────────────────
auth:
	.venv/bin/python main.py auth-gmail

# ── Init database ──────────────────────────────────────────────────────────────
db-init:
	.venv/bin/python main.py db-init

# ── Start background scheduler ─────────────────────────────────────────────────
scheduler:
	.venv/bin/python main.py scheduler

# ── Start admin dashboard ──────────────────────────────────────────────────────
dashboard:
	.venv/bin/python main.py dashboard

# ── Start both (scheduler + dashboard in background) ──────────────────────────
dev:
	.venv/bin/python main.py scheduler &
	.venv/bin/python main.py dashboard

# ── Manual one-shot jobs ───────────────────────────────────────────────────────
run-discovery:
	.venv/bin/python main.py run-discovery

run-send:
	SFAO_DRY_RUN=true .venv/bin/python main.py run-send

run-send-live:
	SFAO_DRY_RUN=false .venv/bin/python main.py run-send

run-followups:
	.venv/bin/python main.py run-followups

run-poll:
	.venv/bin/python main.py run-poll
