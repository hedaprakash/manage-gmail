# Email Cleanup System - Functional Specification

**Version:** 1.0
**Last Updated:** 2026-01-01
**Author:** Claude Code

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture](#2-architecture)
3. [Data Files](#3-data-files)
4. [Phase 1: Bulk Delete](#4-phase-1-bulk-delete)
5. [Phase 2: Categorize & Review](#5-phase-2-categorize--review)
6. [Flask API Server](#6-flask-api-server)
7. [Email Classification Logic](#7-email-classification-logic)
8. [Decision Matrix](#8-decision-matrix)
9. [User Workflow](#9-user-workflow)
10. [Key Design Decisions](#10-key-design-decisions)

---

## 1. System Overview

### Purpose
A two-phase email cleanup system for Gmail that:
1. Bulk deletes emails matching predefined criteria
2. Categorizes remaining emails and provides an interactive review dashboard

### Goals
- Reduce email clutter with minimal manual effort
- Protect important emails (bank statements, receipts, security alerts)
- Allow one-time fetch from Gmail API, then work offline from cache
- Provide interactive UI for reviewing and categorizing emails

### Non-Goals
- Email content analysis (only uses subject line and sender)
- Permanent deletion (emails go to Trash, not permanently deleted)
- Multi-account support

---

## 2. Architecture

```
+------------------+     +------------------+     +------------------+
|  Gmail Account   |     |  Python Scripts  |     |  Flask Server    |
|                  |     |                  |     |                  |
|  - Unread emails | --> |  delete_gmails   | --> |  localhost:5000  |
|  - OAuth2 auth   |     |  categorize      |     |  Button handlers |
+------------------+     +------------------+     +------------------+
                                  |                        |
                                  v                        v
                         +------------------+     +------------------+
                         |  JSON Files      |     |  HTML Dashboard  |
                         |                  |     |                  |
                         |  - criteria.json |     |  - Action buttons|
                         |  - keep_criteria |     |  - Text selection|
                         |  - cached emails |     |  - Category filter|
                         +------------------+     +------------------+
```

### File Structure

```
gmail/
├── credentials.json          # Google OAuth2 credentials (user provides)
├── token.json                # OAuth2 access token (auto-generated)
├── criteria.json             # Delete criteria (immediate)
├── criteria_1day_old.json    # Delete criteria (after 1 day)
├── keep_criteria.json        # Safe list (never delete)
├── delete_gmails.py          # Phase 1: Bulk delete script
├── categorize_emails.py      # Phase 2: Categorize & review
├── email_classification.py   # Keyword classification rules
├── email_review_server.py    # Flask API server
└── logs/                     # All output files (git-ignored)
    ├── emails_categorized_*.json   # Cached email data
    ├── email_report_*.html         # Generated reports
    ├── current_report.html         # Served by Flask
    ├── keep_list.json              # Log of keep decisions
    └── delete_gmails_*.log         # Deletion logs
```

---

## 3. Data Files

### 3.1 criteria.json
**Purpose:** Emails matching these patterns are deleted immediately.

```json
[
  {
    "email": "",
    "subdomain": "",
    "primaryDomain": "example.com",
    "subject": "Weekly Newsletter",
    "toEmails": "",
    "ccEmails": "",
    "excludeSubject": "Important,Urgent"
  }
]
```

| Field | Description |
|-------|-------------|
| `email` | Exact sender email (e.g., `promo@example.com`) |
| `subdomain` | Subdomain match (e.g., `mail.example.com`) |
| `primaryDomain` | Primary domain match (e.g., `example.com`) |
| `subject` | Subject contains this text |
| `toEmails` | Recipient filter |
| `ccEmails` | CC filter |
| `excludeSubject` | Comma-separated exclusions (emails with these words are NOT deleted) |

**Matching Logic:** All non-empty fields must match. Empty fields are ignored.

### 3.2 criteria_1day_old.json
**Purpose:** Same format as criteria.json, but only deletes emails older than 1 day.

**Use Case:** Protects recent OTP codes, verification emails, etc.

### 3.3 keep_criteria.json
**Purpose:** Safe list - emails matching these patterns are NEVER deleted.

```json
[
  {
    "email": "",
    "subdomain": "",
    "primaryDomain": "icicibank.com",
    "subject": "ICICI Bank Statement",
    "toEmails": "",
    "ccEmails": "",
    "excludeSubject": ""
  }
]
```

**Priority:** Keep criteria takes precedence over delete criteria.

### 3.4 Cached Emails (logs/emails_categorized_*.json)
**Purpose:** One-time fetch from Gmail, reused for subsequent runs.

```json
[
  {
    "id": "abc123",
    "email": "sender@example.com",
    "from": "Sender Name <sender@example.com>",
    "subdomain": "example.com",
    "primaryDomain": "example.com",
    "subject": "Your order has shipped",
    "toEmails": "me@gmail.com",
    "ccEmails": "",
    "date": "Mon, 1 Jan 2026 10:00:00 +0000",
    "category": "ORDER",
    "category_icon": "📦",
    "category_color": "#17a2b8",
    "category_bg": "#d1ecf1",
    "matched_keyword": "shipped"
  }
]
```

---

## 4. Phase 1: Bulk Delete

### Script: `delete_gmails.py`

### Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                      START: delete_gmails.py                     │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. Authenticate with Gmail API (OAuth2)                        │
│     - Uses credentials.json + token.json                        │
│     - Scope: https://mail.google.com/ (full access)             │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. Load criteria files                                         │
│     - criteria.json (or --criteria-file custom.json)            │
│     - keep_criteria.json (safe list)                            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. For each criterion in criteria.json:                        │
│     a. Build Gmail search query                                 │
│     b. Add age filter if --min-age specified                    │
│     c. Search for matching emails                               │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. For each matching email:                                    │
│     a. Fetch email metadata (From, Subject)                     │
│     b. Check against keep_criteria.json                         │
│     c. If matches keep criteria → SKIP (protected)              │
│     d. If not protected → Move to Trash                         │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  5. Log results to logs/delete_gmails_*.log                     │
└─────────────────────────────────────────────────────────────────┘
```

### Command Line Options

```bash
python delete_gmails.py [OPTIONS]

Options:
  --dry-run              Show what would be deleted without actually deleting
  --criteria-file FILE   Use custom criteria file (default: criteria.json)
  --min-age DAYS         Only delete emails older than N days (default: 0)
  --filter TEXT          Only process criteria containing this text in sender
```

### Gmail Query Builder

| Criterion Field | Gmail Query |
|-----------------|-------------|
| `email` | `from:email@example.com` |
| `subdomain` | `from:*@subdomain.example.com` |
| `primaryDomain` | `from:example.com` |
| `subject` | `subject:("exact text")` |
| `excludeSubject` | `-subject:("excluded text")` |
| `min_age_days` | `older_than:Nd` |

**Always added:** `is:unread`

### Protection Flow

```
                    Email Found
                         │
                         ▼
              ┌──────────────────────┐
              │ Match keep_criteria? │
              └──────────────────────┘
                    │         │
                   YES        NO
                    │         │
                    ▼         ▼
              ┌─────────┐ ┌─────────┐
              │  SKIP   │ │ DELETE  │
              │(protected)│ │(to trash)│
              └─────────┘ └─────────┘
```

---

## 5. Phase 2: Categorize & Review

### Script: `categorize_emails.py`

### Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                   START: categorize_emails.py                    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. Check for cached data                                       │
│     - Look for logs/emails_categorized_*.json                   │
│     - Check cache age                                           │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
              ┌─────────────────────────────────┐
              │     Cache Decision Matrix       │
              ├─────────────────────────────────┤
              │ --refresh flag?     → FETCH     │
              │ No cache exists?    → FETCH     │
              │ Cache > 5 hours?    → FETCH     │
              │ Cache <= 5 hours?   → USE CACHE │
              └─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. If FETCH: Query Gmail API                                   │
│     - Get ALL unread emails (with pagination)                   │
│     - Extract: From, Subject, Date, To, Cc                      │
│     - Classify each email by subject keywords                   │
│     - Save to logs/emails_categorized_*.json                    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. Group emails by domain + subject pattern                    │
│     - Key: primaryDomain                                        │
│     - Sub-key: category:subject_first_50_chars                  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. Auto-add PROMO/NEWSLETTER to criteria.json                  │
│     - Skip if already exists                                    │
│     - User can override with "Keep" button                      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  5. Filter out already-decided emails                           │
│     - Load criteria.json and keep_criteria.json                 │
│     - Remove patterns that match existing criteria              │
│     - Only show undecided emails in report                      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  6. Generate interactive HTML report                            │
│     - Domain sections with email counts                         │
│     - Pattern rows with category badges                         │
│     - Action buttons (Keep, Delete, Del 1d)                     │
│     - Text selection for custom Keep patterns                   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  7. Start Flask server + Open browser                           │
│     - Serve report at http://localhost:5000                     │
│     - Handle button click API calls                             │
└─────────────────────────────────────────────────────────────────┘
```

### Command Line Options

```bash
python categorize_emails.py [OPTIONS]

Options:
  --refresh    Force re-fetch from Gmail API (ignore cache)
```

### Caching Logic

```
                    Script Start
                         │
                         ▼
              ┌──────────────────────┐
              │   --refresh flag?    │
              └──────────────────────┘
                   YES │      │ NO
                       │      ▼
                       │ ┌──────────────────────┐
                       │ │   Cache exists?      │
                       │ └──────────────────────┘
                       │      NO │      │ YES
                       │         │      ▼
                       │         │ ┌──────────────────────┐
                       │         │ │  Cache age > 5h?     │
                       │         │ └──────────────────────┘
                       │         │      YES │      │ NO
                       ▼         ▼          ▼      ▼
                  ┌─────────────────┐  ┌─────────────────┐
                  │  FETCH FROM     │  │  USE CACHED     │
                  │  GMAIL API      │  │  JSON FILE      │
                  └─────────────────┘  └─────────────────┘
```

---

## 6. Flask API Server

### Script: `email_review_server.py`

### Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Serve the HTML report |
| `/api/add-criteria` | POST | Add to criteria.json |
| `/api/add-criteria-1d` | POST | Add to criteria_1day_old.json |
| `/api/mark-keep` | POST | Remove from delete + add to keep |
| `/api/stats` | GET | Get criteria statistics |
| `/api/undo-last` | POST | Remove last added criteria |

### API Request/Response

#### POST /api/add-criteria
```json
// Request
{
  "domain": "example.com",
  "subject_pattern": "Newsletter",
  "exclude_subject": ""
}

// Response
{
  "success": true,
  "message": "Added to criteria.json",
  "entry": { ... },
  "total_criteria": 42
}
```

#### POST /api/mark-keep (The Most Complex Endpoint)
```json
// Request
{
  "domain": "icicibank.com",
  "subject_pattern": "Bank Statement",
  "category": "STATEMENT"
}

// Response
{
  "success": true,
  "message": "Removed 2 from delete criteria | Added to safe list (4 protected)",
  "entry": { ... },
  "total_protected": 4,
  "removed_from_delete": 2
}
```

### Mark-Keep Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    POST /api/mark-keep                          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: Remove from BOTH delete criteria files (if present)    │
│                                                                 │
│  - Load criteria.json, remove matching entries, save            │
│  - Load criteria_1day_old.json, remove matching entries, save   │
│  - Log: "Removed X entries from criteria.json"                  │
│  - Log: "Removed X entries from criteria_1day_old.json"         │
│                                                                 │
│  Purpose: UNDO any previous Delete/Del 1d actions               │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 2: Add to keep_criteria.json                              │
│                                                                 │
│  - Load keep_criteria.json                                      │
│  - Check for duplicates                                         │
│  - If not duplicate: add entry and save                         │
│  - Log: "Added to safe list"                                    │
│                                                                 │
│  Purpose: Permanently protect this pattern                      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 3: Log to keep_list.json (audit trail)                    │
│                                                                 │
│  - Append entry with timestamp                                  │
│  - Include category and removal count                           │
│                                                                 │
│  Purpose: Track when and why patterns were kept                 │
└─────────────────────────────────────────────────────────────────┘
```

### Complete Button Workflow Reference

| Button | Location | API Endpoint | Request Body | Files Modified |
|--------|----------|--------------|--------------|----------------|
| **Keep** | Per-pattern | `/api/mark-keep` | `{domain, subject_pattern, category}` | Removes from `criteria.json` + `criteria_1day_old.json`, adds to `keep_criteria.json` |
| **Keep All** | Domain header | `/api/mark-keep` | `{domain, subject_pattern: "", category: "DOMAIN"}` | Same as Keep but with empty subject (protects ALL from domain) |
| **Keep Selected** | Text selection popup | `/api/mark-keep` | `{domain, subject_pattern: "selected text", category: "SELECTED"}` | Same as Keep but uses selected text as pattern |
| **Delete** | Per-pattern | `/api/add-criteria` | `{domain, subject_pattern}` | Adds to `criteria.json` |
| **Del All** | Domain header | `/api/add-criteria` | `{domain, subject_pattern: ""}` | Adds domain-only entry to `criteria.json` (deletes ALL from domain) |
| **Del 1d** | Per-pattern | `/api/add-criteria-1d` | `{domain, subject_pattern}` | Adds to `criteria_1day_old.json` |
| **Del 1d All** | Domain header | `/api/add-criteria-1d` | `{domain, subject_pattern: ""}` | Adds domain-only entry to `criteria_1day_old.json` |

### API Test Results (Verified 2026-01-01)

```
TEST 1: Delete button
  curl -X POST /api/add-criteria -d '{"domain":"test.com","subject_pattern":"Newsletter"}'
  ✓ Added to criteria.json
  ✓ Response: {"success":true,"message":"Added to criteria.json","total_criteria":437}

TEST 2: Keep after Delete (UNDO scenario)
  curl -X POST /api/mark-keep -d '{"domain":"test.com","subject_pattern":"Newsletter"}'
  ✓ REMOVED from criteria.json
  ✓ Added to keep_criteria.json
  ✓ Response: {"removed_from_delete":1,"message":"Removed 1 from delete criteria | Added to safe list"}

TEST 3: Del All (domain-level)
  curl -X POST /api/add-criteria -d '{"domain":"test.com","subject_pattern":""}'
  ✓ Added domain-only entry to criteria.json (subject:"")
  ✓ This will delete ALL emails from test.com

TEST 4: Del 1d (single pattern)
  curl -X POST /api/add-criteria-1d -d '{"domain":"test.com","subject_pattern":"Daily Digest"}'
  ✓ Added to criteria_1day_old.json
  ✓ Emails will only be deleted after 1 day (protects recent OTPs)

TEST 5: Keep after Del 1d (cross-file removal)
  curl -X POST /api/add-criteria-1d -d '{"domain":"test.com","subject_pattern":"Promo"}'
  curl -X POST /api/mark-keep -d '{"domain":"test.com","subject_pattern":"Promo"}'
  ✓ REMOVED from criteria_1day_old.json
  ✓ Added to keep_criteria.json
  ✓ Response: {"removed_from_delete":1,"message":"Removed 1 from delete criteria | ..."}

TEST 6: Keep All (domain-level protection)
  curl -X POST /api/mark-keep -d '{"domain":"test.com","subject_pattern":"","category":"DOMAIN"}'
  ✓ Added domain-only entry to keep_criteria.json (subject:"")
  ✓ This protects ALL emails from test.com (current and future)
```

---

## 7. Email Classification Logic

### Script: `email_classification.py`

### Category Definitions

| Category | Icon | Color | Description |
|----------|------|-------|-------------|
| PROMO | :green_circle: | Green | Promotional emails - safe to delete |
| NEWSLETTER | :newspaper: | Teal | Newsletters - usually safe to delete |
| ALERT | :bell: | Red | Account alerts - keep |
| SECURITY | :lock: | Red | Security notices - keep |
| STATEMENT | :page_facing_up: | Blue | Bank statements - keep |
| RECEIPT | :receipt: | Blue | Purchase receipts - keep |
| ORDER | :package: | Cyan | Order confirmations - keep |
| TRAVEL | :airplane: | Purple | Travel bookings - keep |
| MEDICAL | :hospital: | Red | Medical records - keep |
| MORTGAGE | :house: | Brown | Mortgage/property - keep |
| UNKNOWN | :yellow_circle: | Yellow | Needs manual review |

### Keyword Matching

```python
CATEGORIES = {
    'PROMO': {
        'keywords': [
            'sale', 'off', '%', 'deal', 'save', 'free', 'discount',
            'offer', 'promo', 'limited time', 'expires', 'flash',
            'clearance', 'exclusive', 'special', 'bonus', 'reward',
            'webinar', 'invite you', 'join us', 'register now',
            'unsubscribe', 'treat yourself', 'don\'t miss'
        ],
        'icon': '🟢',
        'color': '#28a745',
        'bg_color': '#d4edda'
    },
    'ALERT': {
        'keywords': [
            'alert', 'notification', 'notice', 'important',
            'action required', 'attention', 'urgent', 'reminder',
            'expiring', 'due', 'overdue', 'failed', 'declined'
        ],
        'icon': '🔔',
        'color': '#dc3545',
        'bg_color': '#f8d7da'
    },
    # ... more categories
}
```

### Classification Algorithm

```
                    Email Subject
                         │
                         ▼
              ┌──────────────────────┐
              │ For each category:   │
              │   For each keyword:  │
              │     if keyword in    │
              │     subject.lower()  │
              └──────────────────────┘
                         │
            ┌────────────┴────────────┐
            │                         │
         MATCH                     NO MATCH
            │                         │
            ▼                         ▼
    Return category           Return 'UNKNOWN'
    with first match          (needs review)
```

### Priority Order
Categories are checked in this order (first match wins):
1. SECURITY (highest priority - OTPs, verification)
2. ALERT
3. STATEMENT
4. RECEIPT
5. ORDER
6. MEDICAL
7. MORTGAGE
8. TRAVEL
9. NEWSLETTER
10. PROMO (lowest priority)

---

## 8. Decision Matrix

### What Happens When User Clicks a Button

| Button | Domain Level | Pattern Level | Effect |
|--------|--------------|---------------|--------|
| **Keep** | Adds domain-only entry to keep_criteria.json | Adds domain+subject entry to keep_criteria.json | Protected forever |
| **Keep** (on PROMO) | Same + removes from criteria.json | Same + removes from criteria.json | Undoes auto-add |
| **Delete** | Adds domain-only entry to criteria.json | Adds domain+subject entry to criteria.json | Deleted on next run |
| **Del 1d** | Adds to criteria_1day_old.json | Adds to criteria_1day_old.json | Deleted after 1 day |

### Visual Feedback After Click

| Action | Button State | Section State |
|--------|--------------|---------------|
| Keep (pattern) | "✓ Kept" + green | No change |
| Keep All (domain) | "✓ Kept All" + green | Opacity 0.5, all buttons disabled |
| Delete (pattern) | "✓ Added" + green | No change |
| Del All (domain) | "✓ Del All" + green | Opacity 0.5, all buttons disabled |

### Email Visibility in Report

| Email Status | Shown in Report? |
|--------------|------------------|
| Matches criteria.json | NO (filtered out) |
| Matches keep_criteria.json | NO (filtered out) |
| PROMO (auto-added) | NO (filtered out after auto-add) |
| Undecided | YES |

---

## 9. User Workflow

### Recommended Daily Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: Run bulk delete                                        │
│  $ python delete_gmails.py                                      │
│                                                                 │
│  - Deletes emails matching criteria.json                        │
│  - Respects keep_criteria.json (safe list)                      │
│  - Takes ~1-2 minutes                                           │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 2: Review remaining emails                                │
│  $ python categorize_emails.py                                  │
│                                                                 │
│  - Uses cached data (fast, <5 seconds)                          │
│  - Opens dashboard at localhost:5000                            │
│  - Shows only undecided emails                                  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 3: Make decisions in dashboard                            │
│                                                                 │
│  For each domain:                                               │
│  - "Keep All" if you want ALL emails from this sender           │
│  - "Del All" if you want to delete ALL from this sender         │
│                                                                 │
│  For specific patterns:                                         │
│  - "Keep" to protect that subject pattern                       │
│  - "Delete" to add to delete criteria                           │
│  - Highlight text + "Keep Selected" for partial subject match   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 4: Run delete again to apply new criteria                 │
│  $ python delete_gmails.py                                      │
└─────────────────────────────────────────────────────────────────┘
```

### First-Time Setup

```bash
# 1. Get Google OAuth2 credentials
#    - Go to Google Cloud Console
#    - Create OAuth2 credentials
#    - Download as credentials.json

# 2. First run (will open browser for auth)
python delete_gmails.py --dry-run

# 3. Categorize emails (first run fetches from Gmail)
python categorize_emails.py
```

---

## 10. Key Design Decisions

### 10.1 Caching Strategy
**Decision:** Default to cached JSON, never fetch by default

**Rationale:**
- Gmail API fetch takes 2+ minutes for 1000+ emails
- Users review incrementally, don't need fresh data every time
- Cache auto-refreshes if >5 hours old
- `--refresh` flag available for manual refresh

### 10.2 PROMO Auto-Add
**Decision:** Automatically add PROMO/NEWSLETTER patterns to criteria.json

**Rationale:**
- Most PROMO emails are safe to delete
- Reduces manual clicking
- User can override with "Keep" button

**Important:** Keep button removes from criteria.json AND adds to keep_criteria.json

### 10.3 Keep All Behavior
**Decision:** Add single domain-only entry (empty subject)

**Rationale:**
- Protects ALL current and future emails from that domain
- Simpler than looping through all patterns
- One entry covers everything

**Example:**
```json
{
  "primaryDomain": "icicibank.com",
  "subject": ""  // Empty = match all subjects
}
```

### 10.4 Filtering Decided Emails
**Decision:** Completely hide emails that match existing criteria

**Rationale:**
- Reduces clutter - only show what needs decisions
- User asked for this specifically (not collapsed, but hidden)
- Can always re-run with `--refresh` to see everything

### 10.5 Text Selection for Keep
**Decision:** Allow highlighting text in subject to use as pattern

**Rationale:**
- More precise than using full subject
- Example: Highlight "ICICI Bank Statement" instead of "ICICI Bank Statement from November 01, 2025 to..."
- Works with partial matches

### 10.6 Safe List Priority
**Decision:** keep_criteria.json always takes precedence

**Rationale:**
- Prevents accidental deletion of protected emails
- Even if email matches both delete and keep criteria, it's kept
- Defense in depth

### 10.7 Trash, Not Delete
**Decision:** Move to Trash instead of permanent delete

**Rationale:**
- Recoverable for 30 days
- Less risky
- Gmail API supports both, but Trash is safer

### 10.8 1-Day Delay Option
**Decision:** criteria_1day_old.json for delayed deletion

**Rationale:**
- Protects recent OTP codes and verification emails
- User can read email within 24 hours if needed
- Common for transactional emails that become useless after a day

---

## Appendix A: Error Handling

### Gmail API Rate Limits
- 429 Too Many Requests: Exponential backoff (5s, 10s, 20s, 40s, 80s)
- Max 5 retry attempts per criterion

### Unicode in Subjects
- Console handler uses UTF-8 with 'replace' error handling
- File handler uses UTF-8 encoding
- HTML escapes special characters

### Missing Files
- credentials.json missing: Error with instructions
- criteria.json missing: Error
- keep_criteria.json missing: Empty list (no protection)
- Cache missing: Fetch from Gmail

---

## Appendix B: Security Considerations

### OAuth2 Scope
- Uses `https://mail.google.com/` (full access)
- Required for Trash operation
- Token stored in token.json (keep secure, add to .gitignore)

### Sensitive Data
- credentials.json: OAuth2 client secrets
- token.json: Access/refresh tokens
- logs/*.json: Contains email metadata (subjects, senders)

### Recommendations
- Add to .gitignore: `token.json`, `credentials.json`, `logs/`
- Don't commit criteria files with sensitive patterns
- Run on trusted machine only

---

## Appendix C: Testing

### Dry Run
```bash
python delete_gmails.py --dry-run
```
Shows what would be deleted without actually deleting.

### Test Specific Domain
```bash
python delete_gmails.py --filter "example.com" --dry-run
```

### Force Cache Refresh
```bash
python categorize_emails.py --refresh
```

---

*End of Specification*
