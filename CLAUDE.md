# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Gmail automation tools for managing unread emails - bulk deletion based on sender criteria and email categorization/reporting.

## Setup

```bash
# Activate virtual environment (Windows)
source venv/Scripts/activate

# Install dependencies
pip install -r requirements.txt
```

**Required files:**
- `credentials.json` - Google Cloud OAuth credentials (get from Google Cloud Console)
- `token.json` - Auto-generated after first authentication
- `criteria.json` - Deletion criteria (array of sender filters)

## Commands

### Delete emails by criteria
```bash
# Dry run (preview what would be deleted)
python delete_gmails.py --dry-run

# Live deletion (moves to trash)
python delete_gmails.py

# Filter to specific sender
python delete_gmails.py --filter linkedin.com

# Only delete emails older than N days
python delete_gmails.py --min-age 2

# Use alternate criteria file
python delete_gmails.py --criteria-file criteria_1day_old.json
```

### Search/count emails
```bash
python search_gmail.py example.com           # Count by sender
python search_gmail.py --promotions          # Count promo emails
python search_gmail.py --social              # Count social emails
```

### Categorize unread emails
```bash
python categorize_emails.py    # Generates HTML report in logs/
```

## Architecture

**Core scripts:**
- `delete_gmails.py` - Bulk email deletion with rate limiting, retry logic, dry-run mode
- `search_gmail.py` - Quick email counting by sender or Gmail category
- `categorize_emails.py` - Fetches unread emails, groups by domain, generates interactive HTML report

**Criteria format** (`criteria.json`):
```json
[
  {"email": "alerts@example.com"},
  {"primaryDomain": "newsletter.com"},
  {"subdomain": "mail.company.com", "excludeSubject": "Order,Receipt"}
]
```

**Logging:** All scripts log to `logs/` directory. Console shows only matches; file logs include all queries (DEBUG level).

## Gmail API Query Building

Queries use Gmail search syntax. Key patterns in `build_query()`:
- `is:unread` - Always included
- `from:email` / `from:*@subdomain` / `from:domain`
- `older_than:Nd` - Age filter
- `-subject:("text")` - Exclusions (comma-separated in criteria)
