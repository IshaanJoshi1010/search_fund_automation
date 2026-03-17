# SearchFund Auto-Outreach (SFAO)

Automated cold-email system for Ishaan Joshi to reach search fund operators. Discovers active searchers, personalizes emails using proven templates, attaches resume + industry thesis, sends via Gmail, and follows up — fully automated.

---

## Quick Start

### 1. Install dependencies
```bash
make setup
```

### 2. Set up environment
```bash
# Edit .env — set your Gmail address:
nano .env
# SENDER_EMAIL=yourname@gmail.com
# SFAO_DRY_RUN=true  ← keep this true until testing is complete
```

### 3. Set up Gmail API credentials
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → Enable **Gmail API**
3. Create OAuth 2.0 Client ID (Desktop app type)
4. Download `credentials.json` → place it in the project root
5. Run the one-time auth flow:
```bash
make auth
```
A browser window will open. Complete the OAuth flow. `token.json` will be saved.

### 4. Add your resume
```bash
# Copy your resume PDF to:
cp /path/to/your/resume.pdf attachments/resume.pdf
```

### 5. Add a thesis PDF (optional but recommended)
```bash
cp /path/to/your/thesis.pdf attachments/thesis_general.pdf
```
Or upload via the dashboard (see below).

### 6. Initialize the database
```bash
make db-init
```

### 7. Test the pipeline (dry run)
```bash
# Discover leads (scrape + classify):
make run-discovery

# Preview emails that WOULD be sent:
make run-send   # SFAO_DRY_RUN=true by default
```

### 8. Go live
```bash
# In .env, change:
# SFAO_DRY_RUN=false

# Then send a real test to yourself first:
# Add yourself as a lead in the DB, then run:
make run-send-live
```

### 9. Start the scheduler (background daemon)
```bash
make scheduler
# Runs in foreground. Use systemd or screen/tmux for production.
```

### 10. Use the admin dashboard
```bash
make dashboard
# Open http://localhost:5050 in your browser
```

---

## Admin Dashboard Features

| Route | Description |
|---|---|
| `/` | Stats overview, pipeline bar, quick action buttons |
| `/leads` | All leads with status filters and pagination |
| `/logs` | Full email send history |
| `/upload/resume` | Replace your resume PDF |
| `/upload/thesis` | Add/replace industry thesis PDFs |
| `/run/discovery` | Manually trigger a scrape |
| `/run/send` | Manually trigger a send batch |
| `/run/followup` | Manually trigger follow-up checker |
| `/run/poll` | Manually poll Gmail for replies |

---

## File Structure

```
search_fund_automation/
├── main.py                  # CLI entry point
├── config.yaml              # Source URLs, send caps, keywords
├── models.py                # SQLAlchemy database models
├── database.py              # DB session management
├── templates/               # Email template .txt files
├── scraper/                 # Lead discovery scrapers
├── classifier/              # Sector, geo, education classifiers
├── engine/                  # Template rendering engine
├── email_client/            # Gmail API + dispatcher + poller
├── scheduler/               # Follow-up job + APScheduler runner
├── attachments/             # resume.pdf + thesis_*.pdf
└── dashboard/               # Flask admin UI
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `SENDER_EMAIL` | Your Gmail address |
| `SFAO_DRY_RUN` | `true` = log only, `false` = actually send |
| `GOOGLE_CREDENTIALS_FILE` | Path to credentials.json (default: `credentials.json`) |
| `GOOGLE_TOKEN_FILE` | Path to token.json (default: `token.json`) |
| `FLASK_SECRET_KEY` | Flask session key (generate a random string) |
| `DATABASE_URL` | SQLite URL (default: `sqlite:///sfao.db`) |
| `RESUME_PATH` | Path to resume PDF (default: `attachments/resume.pdf`) |

---

## Scheduled Jobs

| Job | Default Schedule | Description |
|---|---|---|
| Discovery + Classify | Daily 3 AM | Scrapes source URLs, extracts leads, classifies |
| Send Batch | Daily 9 AM | Sends up to 15 emails/day to new leads |
| Follow-up Checker | Daily 10 AM | Sends follow-up 1 (day 7) and 2 (day 14) |
| Response Poll | Every 4 hours | Checks Gmail threads for replies |

---

## Adding Custom Lead Sources

In `config.yaml`, add entries to `source_urls`:
```yaml
source_urls:
  - name: "My Custom Investor Page"
    url: "https://example.com/our-portfolio"
    type: "investor_directory"
```

---

## Safety Features

- **Daily cap**: Default 15 emails/day (configurable in `config.yaml`)
- **Polite delays**: 30–90 second random delay between sends
- **Max 2 follow-ups** per contact, then auto-closed
- **Dry-run mode**: All sends logged but never dispatched when `SFAO_DRY_RUN=true`
- **Deduplication**: Leads upserted by email — no duplicate sends
