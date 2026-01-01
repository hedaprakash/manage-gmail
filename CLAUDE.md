# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Two-phase Gmail cleanup system:**
1. **Phase 1:** Bulk delete emails matching criteria (delete_gmails.py)
2. **Phase 2:** Categorize remaining emails + interactive review dashboard (categorize_emails.py)

**Key files for understanding the system:**
- `SPEC.md` - Complete functional specification with flowcharts and decision matrices
- `SESSION_LOG.md` - Ongoing work tracker (read this first when resuming)

## Quick Start

```bash
# Activate virtual environment (Windows)
source venv/Scripts/activate

# Phase 1: Delete emails matching criteria
python delete_gmails.py

# Phase 2: Review remaining emails (opens browser dashboard)
python categorize_emails.py
```

## File Structure

```
gmail/
├── credentials.json          # Google OAuth2 (user provides)
├── token.json                # OAuth2 token (auto-generated)
├── criteria.json             # Delete immediately
├── criteria_1day_old.json    # Delete after 1 day (protects OTPs)
├── keep_criteria.json        # Safe list (NEVER delete)
├── delete_gmails.py          # Phase 1: Bulk delete
├── categorize_emails.py      # Phase 2: Categorize + review UI
├── email_classification.py   # Keyword classification rules
├── email_review_server.py    # Flask API for button handlers
├── SPEC.md                   # Full specification document
├── SESSION_LOG.md            # Ongoing work tracker
└── logs/                     # All output (git-ignored)
    ├── emails_categorized_*.json   # Cached email data
    ├── current_report.html         # Served by Flask
    └── *.log                       # Execution logs
```

## Commands

### Delete Emails (Phase 1)
```bash
python delete_gmails.py                    # Live deletion
python delete_gmails.py --dry-run          # Preview only
python delete_gmails.py --min-age 1        # Only emails >1 day old
python delete_gmails.py --filter domain.com  # Specific domain
python delete_gmails.py --criteria-file criteria_1day_old.json
```

### Categorize & Review (Phase 2)
```bash
python categorize_emails.py          # Uses cache (fast, <5 seconds)
python categorize_emails.py --refresh  # Force re-fetch from Gmail API
```

### Search/Count (Utility)
```bash
python search_gmail.py example.com    # Count by sender
python search_gmail.py --promotions   # Count promo emails
```

## Key Design Decisions

These are important nuances that must be preserved:

### 1. Caching Strategy
- **Default:** Always use cached JSON file (never fetch from Gmail by default)
- **Auto-refresh:** Only if cache is >5 hours old
- **Manual refresh:** `--refresh` flag forces Gmail API fetch
- **Rationale:** Gmail fetch takes 2+ minutes for 1000+ emails

### 2. PROMO Auto-Add
- PROMO/NEWSLETTER emails are automatically added to criteria.json
- User can override with "Keep" button (removes from criteria + adds to keep)
- Keep button does TWO things: removes from delete AND adds to safe list

### 3. Keep All Button Behavior
- Adds SINGLE domain-only entry (empty subject field)
- This protects ALL emails from that domain (current and future)
- Does NOT loop through patterns

### 4. Filtering Decided Emails
- Emails matching criteria.json or keep_criteria.json are HIDDEN from report
- Not collapsed, not strikethrough - completely removed from view
- Only undecided emails appear in the dashboard

### 5. Text Selection for Keep
- User can highlight text in subject line
- "Keep Selected" uses highlighted text as the pattern
- More precise than using full subject

### 6. Safe List Priority
- keep_criteria.json ALWAYS takes precedence over criteria.json
- Even if email matches both, it is KEPT (not deleted)

### 7. 1-Day Delay
- criteria_1day_old.json for patterns that should wait 1 day
- Protects recent OTPs, verification codes
- Use with: `python delete_gmails.py --criteria-file criteria_1day_old.json --min-age 1`

## Criteria File Format

```json
[
  {
    "email": "",
    "subdomain": "",
    "primaryDomain": "example.com",
    "subject": "Newsletter",
    "toEmails": "",
    "ccEmails": "",
    "excludeSubject": "Important,Urgent"
  }
]
```

- Empty string = ignored (not used in matching)
- All non-empty fields must match
- `excludeSubject`: comma-separated list of terms that PREVENT deletion

## Flask API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Serve HTML dashboard |
| `/api/add-criteria` | POST | Add to criteria.json |
| `/api/add-criteria-1d` | POST | Add to criteria_1day_old.json |
| `/api/mark-keep` | POST | Remove from delete + add to keep |
| `/api/stats` | GET | Get criteria counts |
| `/api/load-emails` | GET | Load emails & show filtering stats |

## Email Categories

| Category | Color | Action |
|----------|-------|--------|
| PROMO | Green | Auto-added to delete (can override) |
| NEWSLETTER | Teal | Auto-added to delete (can override) |
| ALERT, SECURITY | Red | Keep (important) |
| STATEMENT, RECEIPT | Blue | Keep (financial) |
| ORDER | Cyan | Keep (purchases) |
| UNKNOWN | Yellow | Needs manual review |

## When Resuming Work

1. **Read SESSION_LOG.md first** - Contains current status and pending tasks
2. **Check git status** - See what files have been modified
3. **Read SPEC.md** - Full system documentation if needed

## Common Issues

### Unicode errors on Windows console
- Already handled with UTF-8 reconfigure in logging setup
- If errors appear, they're logged but don't stop execution

### Slow script on first run
- First run fetches from Gmail API (2+ minutes for 1000+ emails)
- Subsequent runs use cache (instant)
- Use `--refresh` only when needed

### Button not working in dashboard
- Check if Flask server is running (localhost:5000)
- Check browser console for errors
- Verify criteria.json is valid JSON

## Skills

### /test-email-api
**Trigger phrases:** "run the test script", "test the email API", "run /test-email-api", "run tests", "test the API"

**Action:** Immediately run `python test_api.py` in the gmail directory. Do NOT ask any questions - just execute and show results.

Test all Email Review API endpoints. Runs 8 automated tests:
1. Delete button (add to criteria.json)
2. Keep button (removes from delete, adds to keep)
3. Del All (domain-level delete)
4. Del 1d (add to criteria_1day_old.json)
5. Keep after Del 1d (cross-file removal)
6. Keep All (domain-level protection)
7. Del 1d All (domain-level 1-day delete)
8. Load Emails (filtering statistics report)

Usage: Just ask "run /test-email-api" or "test the email API"

The skill automatically:
- Starts Flask server if needed
- Runs all tests with `test-skill-` prefixed domains
- Verifies file changes
- Shows email filtering report (total, deleted, protected, undecided)
- Cleans up test data
- Reports pass/fail for each test

### New API Endpoint: `/api/load-emails`
Returns filtering statistics for all cached emails:
```json
{
  "summary": {
    "total_emails": 1120,
    "will_delete_now": 172,
    "will_delete_1d": 173,
    "protected": 19,
    "need_review": 756
  }
}
```
