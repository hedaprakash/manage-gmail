"""
Email Categorization Script with Interactive Review

This script:
1. Fetches ALL unread emails from Gmail (with pagination)
2. Classifies each by subject using keyword rules
3. Generates an interactive HTML report with action buttons
4. Starts a local server for button functionality
"""

import os
import sys
import time
import json
import glob
import logging
import argparse
import webbrowser
import threading
from datetime import datetime, timedelta
from collections import defaultdict
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from email_classification import classify_email, get_all_categories, CATEGORIES

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://mail.google.com/']
USER_ID = 'me'

# Processing constants
BATCH_SIZE = 100  # Messages to fetch per API call (max 500)


def get_credentials():
    """Gets valid user credentials from storage or initiates the authorization flow."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing token: {e}, re-authenticating...")
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds


def extract_email_address(header_value):
    """Extracts email address from a header like 'Name <email@domain.com>'."""
    import re
    if not header_value:
        return ""
    match = re.search(r'<(.+?)>', header_value)
    if match:
        return match.group(1)
    return header_value.strip()


def extract_domain_info(email):
    """Extracts subdomain and primary domain from email address."""
    if '@' not in email:
        return "", ""
    subdomain = email.split('@')[1]
    parts = subdomain.split('.')
    primary_domain = '.'.join(parts[-2:]) if len(parts) >= 2 else subdomain
    return subdomain, primary_domain


def get_header_value(headers, name):
    """Gets a header value by name from message headers."""
    for header in headers:
        if header['name'].lower() == name.lower():
            return header['value']
    return ""


def fetch_all_unread_emails(logger, gmail_service, max_emails=None):
    """
    Fetches ALL unread emails using pagination.

    Args:
        logger: Logger instance
        gmail_service: Gmail API service
        max_emails: Optional limit (None = fetch all)

    Returns:
        List of email details
    """
    email_details = []
    page_token = None
    total_fetched = 0

    try:
        logger.info("Searching for ALL unread emails (with pagination)...")

        while True:
            # Fetch a batch of message IDs
            request_params = {
                'userId': USER_ID,
                'q': 'is:unread',
                'maxResults': BATCH_SIZE
            }
            if page_token:
                request_params['pageToken'] = page_token

            response = gmail_service.users().messages().list(**request_params).execute()

            messages = response.get('messages', [])
            if not messages:
                break

            logger.info(f"Fetched batch of {len(messages)} message IDs...")

            # Process each message
            for msg_info in messages:
                if max_emails and total_fetched >= max_emails:
                    logger.info(f"Reached max limit of {max_emails} emails.")
                    return email_details

                try:
                    # Get message metadata
                    message = gmail_service.users().messages().get(
                        userId=USER_ID,
                        id=msg_info['id'],
                        format='metadata',
                        metadataHeaders=['From', 'To', 'Cc', 'Subject', 'Date']
                    ).execute()

                    headers = message.get('payload', {}).get('headers', [])

                    from_header = get_header_value(headers, 'From')
                    email = extract_email_address(from_header)
                    subdomain, primary_domain = extract_domain_info(email)

                    to_header = get_header_value(headers, 'To')
                    to_emails = ', '.join([extract_email_address(e.strip()) for e in to_header.split(',')]) if to_header else ""

                    cc_header = get_header_value(headers, 'Cc')
                    cc_emails = ', '.join([extract_email_address(e.strip()) for e in cc_header.split(',')]) if cc_header else ""

                    subject = get_header_value(headers, 'Subject')
                    date = get_header_value(headers, 'Date')

                    # Classify the email by subject
                    classification = classify_email(subject)

                    email_details.append({
                        'id': msg_info['id'],
                        'email': email,
                        'from': from_header,
                        'subdomain': subdomain,
                        'primaryDomain': primary_domain,
                        'subject': subject,
                        'toEmails': to_emails,
                        'ccEmails': cc_emails,
                        'date': date,
                        'category': classification['category'],
                        'category_icon': classification['icon'],
                        'category_color': classification['color'],
                        'category_bg': classification['bg_color'],
                        'matched_keyword': classification['matched_keyword']
                    })

                    total_fetched += 1

                    if total_fetched % 100 == 0:
                        logger.info(f"Processed {total_fetched} emails...")

                except HttpError as e:
                    logger.warning(f"Error fetching message {msg_info['id']}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"Unexpected error processing message: {e}")
                    continue

            # Check for next page
            page_token = response.get('nextPageToken')
            if not page_token:
                break

        logger.info(f"Successfully extracted details for {len(email_details)} emails.")
        return email_details

    except HttpError as error:
        logger.error(f"Gmail API error: {error}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise


def group_emails_by_pattern(email_details):
    """
    Groups emails by domain and subject pattern.

    Returns a structure like:
    {
        'domain.com': {
            'pattern_key': {
                'subject_sample': 'First 50 chars...',
                'category': 'PROMO',
                'count': 5,
                'emails': [...]
            }
        }
    }
    """
    grouped = defaultdict(lambda: defaultdict(lambda: {
        'subject_sample': '',
        'category': 'UNKNOWN',
        'category_icon': '🟡',
        'category_color': '#ffc107',
        'category_bg': '#fff3cd',
        'count': 0,
        'emails': []
    }))

    for email in email_details:
        domain = email.get('primaryDomain', 'unknown')
        subject = email.get('subject', '')[:50]  # First 50 chars as pattern key
        category = email.get('category', 'UNKNOWN')

        # Create a unique key based on subject pattern
        pattern_key = f"{category}:{subject}"

        group = grouped[domain][pattern_key]
        group['subject_sample'] = subject if not group['subject_sample'] else group['subject_sample']
        group['category'] = category
        group['category_icon'] = email.get('category_icon', '🟡')
        group['category_color'] = email.get('category_color', '#ffc107')
        group['category_bg'] = email.get('category_bg', '#fff3cd')
        group['count'] += 1
        group['emails'].append(email)

    return grouped


def auto_add_promo_to_criteria(logger, grouped):
    """
    Auto-add PROMO and NEWSLETTER patterns to criteria.json.

    Returns the count of patterns added.
    """
    CRITERIA_FILE = 'criteria.json'

    # Load existing criteria
    if os.path.exists(CRITERIA_FILE):
        with open(CRITERIA_FILE, 'r', encoding='utf-8') as f:
            criteria = json.load(f)
    else:
        criteria = []

    # Helper to check if criteria already exists
    def is_duplicate(domain, subject):
        domain_lower = domain.lower()
        subject_lower = subject.lower() if subject else ''
        for entry in criteria:
            if (entry.get('primaryDomain', '').lower() == domain_lower and
                entry.get('subject', '').lower() == subject_lower):
                return True
        return False

    # Helper to create criteria entry
    def create_entry(domain, subject):
        return {
            "email": "",
            "subdomain": "",
            "primaryDomain": domain,
            "subject": subject,
            "toEmails": "",
            "ccEmails": "",
            "excludeSubject": ""
        }

    added_count = 0
    promo_categories = ['PROMO', 'NEWSLETTER']

    for domain, patterns in grouped.items():
        for pattern_key, pattern_data in patterns.items():
            category = pattern_data.get('category', 'UNKNOWN')

            if category in promo_categories:
                subject = pattern_data.get('subject_sample', '')

                if not is_duplicate(domain, subject):
                    criteria.append(create_entry(domain, subject))
                    added_count += 1
                    logger.debug(f"Auto-added PROMO: {domain} - {subject[:30]}...")

    if added_count > 0:
        with open(CRITERIA_FILE, 'w', encoding='utf-8') as f:
            json.dump(criteria, f, indent=2, ensure_ascii=False)
        logger.info(f"Auto-added {added_count} PROMO/NEWSLETTER patterns to criteria.json")

    return added_count


def find_cached_json():
    """
    Find the most recent cached JSON file and check its age.

    Returns:
        tuple: (filepath, age_hours) or (None, None) if no cache exists
    """
    cache_files = glob.glob('logs/emails_categorized_*.json')
    if not cache_files:
        return None, None

    # Sort by modification time (most recent first)
    cache_files.sort(key=os.path.getmtime, reverse=True)
    most_recent = cache_files[0]

    # Calculate age in hours
    file_mtime = os.path.getmtime(most_recent)
    age_seconds = time.time() - file_mtime
    age_hours = age_seconds / 3600

    return most_recent, age_hours


def load_cached_emails(logger, cache_path):
    """Load emails from cached JSON file."""
    logger.info(f"Loading cached data from {cache_path}")
    with open(cache_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_existing_criteria():
    """Load existing criteria.json and keep_criteria.json for filtering."""
    criteria = []
    keep_criteria = []

    if os.path.exists('criteria.json'):
        with open('criteria.json', 'r', encoding='utf-8') as f:
            criteria = json.load(f)

    if os.path.exists('keep_criteria.json'):
        with open('keep_criteria.json', 'r', encoding='utf-8') as f:
            keep_criteria = json.load(f)

    return criteria, keep_criteria


def matches_any_criteria(domain, subject, criteria_list):
    """Check if domain/subject matches any criteria in the list."""
    domain_lower = domain.lower() if domain else ''
    subject_lower = subject.lower() if subject else ''

    for c in criteria_list:
        c_domain = c.get('primaryDomain', '').lower()
        c_subject = c.get('subject', '').lower()

        if c_domain and c_domain in domain_lower:
            # Domain matches
            if not c_subject:
                # No subject filter = matches all from domain
                return True
            if c_subject in subject_lower:
                # Subject also matches
                return True

    return False


def filter_decided_emails(grouped, criteria, keep_criteria):
    """
    Remove patterns that already have a decision (in criteria or keep_criteria).

    Returns filtered grouped dict and count of removed patterns.
    """
    filtered = defaultdict(dict)
    removed_count = 0

    for domain, patterns in grouped.items():
        for pattern_key, pattern_data in patterns.items():
            subject = pattern_data.get('subject_sample', '')

            # Check if this pattern is already decided
            in_delete = matches_any_criteria(domain, subject, criteria)
            in_keep = matches_any_criteria(domain, subject, keep_criteria)

            if in_delete or in_keep:
                removed_count += pattern_data.get('count', 1)
            else:
                filtered[domain][pattern_key] = pattern_data

    return dict(filtered), removed_count


def generate_interactive_html(email_details, grouped, output_path):
    """Generates an interactive HTML report with action buttons."""

    # Calculate stats
    total_emails = len(email_details)
    total_domains = len(grouped)

    # Count by category
    category_counts = defaultdict(int)
    for email in email_details:
        category_counts[email.get('category', 'UNKNOWN')] += 1

    # Sort domains by email count
    sorted_domains = sorted(grouped.items(), key=lambda x: sum(p['count'] for p in x[1].values()), reverse=True)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Email Review Dashboard</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f0f2f5;
            padding: 20px;
            color: #333;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{ text-align: center; margin-bottom: 10px; color: #1a73e8; }}
        .subtitle {{ text-align: center; color: #666; margin-bottom: 20px; }}

        .stats {{
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }}
        .stat-card {{
            background: white;
            padding: 15px 25px;
            border-radius: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .stat-number {{ font-size: 1.8em; font-weight: bold; color: #1a73e8; }}
        .stat-label {{ color: #666; font-size: 0.9em; }}

        .filters {{
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }}
        .filter-btn {{
            padding: 8px 16px;
            border: 2px solid #ddd;
            border-radius: 20px;
            background: white;
            cursor: pointer;
            font-size: 0.9em;
            transition: all 0.2s;
        }}
        .filter-btn:hover {{ border-color: #1a73e8; }}
        .filter-btn.active {{ background: #1a73e8; color: white; border-color: #1a73e8; }}

        .domain-section {{
            background: white;
            margin-bottom: 15px;
            border-radius: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .domain-header {{
            background: #1a73e8;
            color: white;
            padding: 12px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 10px;
        }}
        .domain-header:hover {{ background: #1557b0; }}
        .domain-info {{
            display: flex;
            align-items: center;
            gap: 10px;
            cursor: pointer;
            flex: 1;
        }}
        .domain-name {{ font-weight: bold; font-size: 1.1em; }}
        .domain-count {{
            background: rgba(255,255,255,0.2);
            padding: 4px 12px;
            border-radius: 15px;
            font-size: 0.9em;
        }}
        .domain-actions {{
            display: flex;
            gap: 6px;
        }}
        .domain-actions .action-btn {{
            padding: 4px 8px;
            font-size: 0.75em;
        }}

        .pattern-list {{ display: none; }}
        .pattern-list.active {{ display: block; }}

        .pattern-item {{
            padding: 12px 20px;
            border-bottom: 1px solid #eee;
            display: flex;
            align-items: center;
            gap: 15px;
        }}
        .pattern-item:last-child {{ border-bottom: none; }}

        .category-badge {{
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: 500;
            white-space: nowrap;
        }}

        .pattern-info {{ flex: 1; min-width: 0; }}
        .pattern-subject {{
            font-size: 0.95em;
            color: #333;
            margin-bottom: 3px;
            user-select: text;
            cursor: text;
        }}
        .pattern-count {{ font-size: 0.85em; color: #666; }}

        /* Selection indicator */
        .selection-indicator {{
            position: fixed;
            bottom: 70px;
            right: 20px;
            background: #1a73e8;
            color: white;
            padding: 10px 15px;
            border-radius: 8px;
            display: none;
            z-index: 1001;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            max-width: 300px;
        }}
        .selection-indicator.show {{ display: block; }}
        .selection-text {{
            font-size: 0.85em;
            margin-bottom: 8px;
            word-break: break-word;
        }}
        .selection-btn {{
            background: white;
            color: #1a73e8;
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 500;
        }}
        .selection-btn:hover {{ background: #e8f0fe; }}

        .action-buttons {{ display: flex; gap: 8px; flex-shrink: 0; }}
        .action-btn {{
            padding: 6px 12px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.85em;
            transition: all 0.2s;
        }}
        .btn-keep {{ background: #6c757d; color: white; }}
        .btn-keep:hover {{ background: #5a6268; }}
        .btn-delete {{ background: #dc3545; color: white; }}
        .btn-delete:hover {{ background: #c82333; }}
        .btn-delete-1d {{ background: #fd7e14; color: white; }}
        .btn-delete-1d:hover {{ background: #e96b02; }}

        .action-btn:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
        }}
        .action-btn.done {{
            background: #28a745 !important;
        }}

        .legend {{
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 0.9em;
        }}
        .legend-dot {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
        }}

        .toast {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #333;
            color: white;
            padding: 15px 25px;
            border-radius: 8px;
            display: none;
            z-index: 1000;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }}
        .toast.show {{ display: block; animation: fadeIn 0.3s; }}
        @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}

        .timestamp {{
            text-align: center;
            color: #999;
            margin-top: 30px;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Email Review Dashboard</h1>
        <p class="subtitle">Interactive email categorization with action buttons</p>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-number">{total_emails}</div>
                <div class="stat-label">Total Unread</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{total_domains}</div>
                <div class="stat-label">Domains</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{category_counts.get('PROMO', 0) + category_counts.get('NEWSLETTER', 0)}</div>
                <div class="stat-label">Safe to Delete</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{category_counts.get('UNKNOWN', 0)}</div>
                <div class="stat-label">Need Review</div>
            </div>
        </div>

        <div class="legend">
            <div class="legend-item"><span class="legend-dot" style="background:#28a745"></span> PROMO - Safe to delete</div>
            <div class="legend-item"><span class="legend-dot" style="background:#17a2b8"></span> NEWSLETTER - Usually safe</div>
            <div class="legend-item"><span class="legend-dot" style="background:#dc3545"></span> IMPORTANT - Keep</div>
            <div class="legend-item"><span class="legend-dot" style="background:#ffc107"></span> UNKNOWN - Review</div>
        </div>

        <div class="filters">
            <button class="filter-btn active" onclick="filterCategory('all')">All</button>
            <button class="filter-btn" onclick="filterCategory('PROMO')">🟢 PROMO</button>
            <button class="filter-btn" onclick="filterCategory('NEWSLETTER')">📰 NEWSLETTER</button>
            <button class="filter-btn" onclick="filterCategory('UNKNOWN')">🟡 UNKNOWN</button>
            <button class="filter-btn" onclick="filterCategory('important')">🔴 IMPORTANT</button>
        </div>

        <div id="domains">
'''

    for domain, patterns in sorted_domains:
        domain_count = sum(p['count'] for p in patterns.values())

        # Sort patterns by category priority (PROMO first, then UNKNOWN, then others)
        sorted_patterns = sorted(patterns.items(), key=lambda x: (
            0 if x[1]['category'] == 'PROMO' else
            1 if x[1]['category'] == 'NEWSLETTER' else
            2 if x[1]['category'] == 'UNKNOWN' else 3,
            -x[1]['count']
        ))

        pattern_items = ""
        for pattern_key, pattern in sorted_patterns:
            subject = pattern['subject_sample'] or '(No Subject)'
            # Escape HTML
            subject_escaped = subject.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", "&#39;")
            category = pattern['category']
            icon = pattern['category_icon']
            bg_color = pattern['category_bg']
            count = pattern['count']

            # Determine if this is an "important" category
            important_cats = ['ALERT', 'RECEIPT', 'STATEMENT', 'SECURITY', 'MEDICAL', 'ORDER', 'TRAVEL', 'MORTGAGE']
            data_important = 'true' if category in important_cats else 'false'

            pattern_items += f'''
            <div class="pattern-item" data-category="{category}" data-important="{data_important}">
                <span class="category-badge" style="background:{bg_color}; color:#333;">{icon} {category}</span>
                <div class="pattern-info">
                    <div class="pattern-subject" title="{subject_escaped}">{subject_escaped}</div>
                    <div class="pattern-count">{count} email{"s" if count > 1 else ""}</div>
                </div>
                <div class="action-buttons">
                    <button class="action-btn btn-keep" onclick="markKeep(this, '{domain}', '{subject_escaped}', '{category}')">Keep</button>
                    <button class="action-btn btn-delete" onclick="addCriteria(this, '{domain}', '{subject_escaped}')">Delete</button>
                    <button class="action-btn btn-delete-1d" onclick="addCriteria1d(this, '{domain}', '{subject_escaped}')">Del 1d</button>
                </div>
            </div>
'''

        # Escape domain for use in JavaScript (handle quotes)
        domain_escaped = domain.replace("\\", "\\\\").replace("'", "\\'")

        html += f'''
        <div class="domain-section" data-domain="{domain}">
            <div class="domain-header">
                <div class="domain-info" onclick="toggleSection(this.parentElement)">
                    <span class="domain-name">{domain}</span>
                    <span class="domain-count">{domain_count} emails</span>
                </div>
                <div class="domain-actions">
                    <button class="action-btn btn-keep" onclick="event.stopPropagation(); keepAllDomain(this, '{domain_escaped}')">Keep All</button>
                    <button class="action-btn btn-delete" onclick="event.stopPropagation(); deleteAllDomain(this, '{domain_escaped}')">Del All</button>
                    <button class="action-btn btn-delete-1d" onclick="event.stopPropagation(); deleteAllDomain1d(this, '{domain_escaped}')">Del 1d All</button>
                </div>
            </div>
            <div class="pattern-list">
                {pattern_items}
            </div>
        </div>
'''

    html += f'''
        </div>

        <p class="timestamp">Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    </div>

    <div id="toast" class="toast"></div>
    <div id="selectionIndicator" class="selection-indicator">
        <div class="selection-text">Keep: "<span id="selectedText"></span>"</div>
        <button class="selection-btn" onclick="keepSelectedText()">Keep Selected</button>
    </div>

    <script>
        // Selection state (attached to window for testing accessibility)
        window.currentSelectionDomain = null;
        window.currentSelectionSubject = null;
        const API_BASE = 'http://localhost:5000';

        function toggleSection(header) {{
            // header is domain-header, pattern-list is its next sibling
            const patternList = header.nextElementSibling;
            if (patternList) {{
                patternList.classList.toggle('active');
            }}
        }}

        function showToast(message, isError = false) {{
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.style.background = isError ? '#dc3545' : '#28a745';
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 3000);
        }}

        function markKeep(btn, domain, subject, category) {{
            // Check for text selection: first from mouseup capture, then live selection
            let subjectToUse = subject;
            if (window.currentSelectionSubject && window.currentSelectionSubject.length > 3) {{
                subjectToUse = window.currentSelectionSubject;
            }} else {{
                // Fallback: check current live selection
                const liveSelection = window.getSelection().toString().trim();
                if (liveSelection.length > 3) {{
                    subjectToUse = liveSelection;
                }}
            }}

            fetch(API_BASE + '/api/mark-keep', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{domain, subject_pattern: subjectToUse, category}})
            }})
            .then(r => r.json())
            .then(data => {{
                if (data.success) {{
                    btn.classList.add('done');
                    btn.textContent = '✓ Kept';
                    btn.disabled = true;
                    // Show what was saved
                    const savedText = subjectToUse.length > 30 ? subjectToUse.substring(0, 30) + '...' : subjectToUse;
                    showToast(`Kept: "${{savedText}}"`);
                    // Clear selection state
                    window.getSelection().removeAllRanges();
                    document.getElementById('selectionIndicator').classList.remove('show');
                    window.currentSelectionSubject = null;
                    window.currentSelectionDomain = null;
                }} else {{
                    showToast(data.error || 'Error', true);
                }}
            }})
            .catch(e => showToast('Server error - is the server running?', true));
        }}

        function addCriteria(btn, domain, subject) {{
            const subjectPattern = extractPattern(subject);
            fetch(API_BASE + '/api/add-criteria', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{domain, subject_pattern: subjectPattern}})
            }})
            .then(r => r.json())
            .then(data => {{
                if (data.success) {{
                    btn.classList.add('done');
                    btn.textContent = '✓ Added';
                    btn.disabled = true;
                    showToast('Added to criteria.json');
                }} else {{
                    showToast(data.error || 'Error', true);
                }}
            }})
            .catch(e => showToast('Server error - is the server running?', true));
        }}

        function addCriteria1d(btn, domain, subject) {{
            const subjectPattern = extractPattern(subject);
            fetch(API_BASE + '/api/add-criteria-1d', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{domain, subject_pattern: subjectPattern}})
            }})
            .then(r => r.json())
            .then(data => {{
                if (data.success) {{
                    btn.classList.add('done');
                    btn.textContent = '✓ Added';
                    btn.disabled = true;
                    showToast('Added to criteria_1day_old.json');
                }} else {{
                    showToast(data.error || 'Error', true);
                }}
            }})
            .catch(e => showToast('Server error - is the server running?', true));
        }}

        function extractPattern(subject) {{
            // Extract the first few significant words as a pattern
            // Remove numbers that look like order numbers, dates, etc.
            let pattern = subject.replace(/\\d{{5,}}/g, '').replace(/\\s+/g, ' ').trim();
            // Take first 30 chars as pattern
            return pattern.substring(0, 30).trim();
        }}

        function filterCategory(category) {{
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');

            document.querySelectorAll('.pattern-item').forEach(item => {{
                const itemCat = item.dataset.category;
                const isImportant = item.dataset.important === 'true';

                if (category === 'all') {{
                    item.style.display = 'flex';
                }} else if (category === 'important') {{
                    item.style.display = isImportant ? 'flex' : 'none';
                }} else {{
                    item.style.display = itemCat === category ? 'flex' : 'none';
                }}
            }});

            // Hide empty domain sections
            document.querySelectorAll('.domain-section').forEach(section => {{
                const visibleItems = section.querySelectorAll('.pattern-item[style*="flex"]').length;
                const hiddenItems = section.querySelectorAll('.pattern-item[style*="none"]').length;
                section.style.display = (visibleItems === 0 && hiddenItems > 0) ? 'none' : 'block';
            }});
        }}

        // Domain-level actions
        function keepAllDomain(btn, domain) {{
            btn.disabled = true;
            btn.textContent = 'Keeping...';

            // Add single domain-only entry (protects ALL from this domain)
            fetch(API_BASE + '/api/mark-keep', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{domain, subject_pattern: '', category: 'DOMAIN'}})
            }})
            .then(r => r.json())
            .then(data => {{
                if (data.success) {{
                    btn.classList.add('done');
                    btn.textContent = '✓ Kept All';
                    showToast(`Protected all emails from ${{domain}}`);
                    // Hide this domain section since it's now decided
                    const section = btn.closest('.domain-section');
                    if (section) {{
                        section.style.opacity = '0.5';
                        section.querySelectorAll('.action-btn').forEach(b => b.disabled = true);
                    }}
                }} else {{
                    btn.disabled = false;
                    btn.textContent = 'Keep All';
                    showToast(data.error || 'Error', true);
                }}
            }})
            .catch(e => {{
                btn.disabled = false;
                btn.textContent = 'Keep All';
                showToast('Server error', true);
            }});
        }}

        function deleteAllDomain(btn, domain) {{
            btn.disabled = true;
            btn.textContent = 'Adding...';

            fetch(API_BASE + '/api/add-criteria', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{domain, subject_pattern: ''}})  // Empty = all from domain
            }})
            .then(r => r.json())
            .then(data => {{
                if (data.success) {{
                    btn.classList.add('done');
                    btn.textContent = '✓ Del All';
                    showToast(`Added ${{domain}} to delete criteria`);
                    // Dim section since it's decided
                    const section = btn.closest('.domain-section');
                    if (section) {{
                        section.style.opacity = '0.5';
                        section.querySelectorAll('.action-btn').forEach(b => b.disabled = true);
                    }}
                }} else {{
                    btn.disabled = false;
                    btn.textContent = 'Del All';
                    showToast(data.error || 'Error', true);
                }}
            }})
            .catch(e => {{
                btn.disabled = false;
                btn.textContent = 'Del All';
                showToast('Server error', true);
            }});
        }}

        function deleteAllDomain1d(btn, domain) {{
            btn.disabled = true;
            btn.textContent = 'Adding...';

            fetch(API_BASE + '/api/add-criteria-1d', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{domain, subject_pattern: ''}})  // Empty = all from domain
            }})
            .then(r => r.json())
            .then(data => {{
                if (data.success) {{
                    btn.classList.add('done');
                    btn.textContent = '✓ Del 1d';
                    showToast(`Added ${{domain}} to 1-day delete criteria`);
                    // Dim section since it's decided
                    const section = btn.closest('.domain-section');
                    if (section) {{
                        section.style.opacity = '0.5';
                        section.querySelectorAll('.action-btn').forEach(b => b.disabled = true);
                    }}
                }} else {{
                    btn.disabled = false;
                    btn.textContent = 'Del 1d All';
                    showToast(data.error || 'Error', true);
                }}
            }})
            .catch(e => {{
                btn.disabled = false;
                btn.textContent = 'Del 1d All';
                showToast('Server error', true);
            }});
        }}

        // Text selection handling
        document.addEventListener('mouseup', function(e) {{
            const selection = window.getSelection().toString().trim();
            const indicator = document.getElementById('selectionIndicator');

            if (selection.length > 3) {{
                // Find which pattern-item this selection is in
                const patternItem = e.target.closest('.pattern-item');
                if (patternItem) {{
                    const domain = patternItem.closest('.domain-section').dataset.domain;
                    window.currentSelectionDomain = domain;
                    window.currentSelectionSubject = selection;

                    document.getElementById('selectedText').textContent =
                        selection.length > 40 ? selection.substring(0, 40) + '...' : selection;
                    indicator.classList.add('show');
                }}
            }} else {{
                indicator.classList.remove('show');
            }}
        }});

        // Hide selection indicator when clicking elsewhere
        document.addEventListener('mousedown', function(e) {{
            if (!e.target.closest('.selection-indicator') && !e.target.closest('.pattern-subject')) {{
                document.getElementById('selectionIndicator').classList.remove('show');
            }}
        }});

        function keepSelectedText() {{
            if (!window.currentSelectionDomain || !window.currentSelectionSubject) return;

            fetch(API_BASE + '/api/mark-keep', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{
                    domain: window.currentSelectionDomain,
                    subject_pattern: window.currentSelectionSubject,
                    category: 'SELECTED'
                }})
            }})
            .then(r => r.json())
            .then(data => {{
                if (data.success) {{
                    showToast(`Kept pattern: "${{window.currentSelectionSubject.substring(0, 30)}}..."`);
                    document.getElementById('selectionIndicator').classList.remove('show');
                    window.getSelection().removeAllRanges();
                }} else {{
                    showToast(data.error || 'Error', true);
                }}
            }})
            .catch(e => showToast('Server error', true));
        }}

        // Expand first few domains by default
        document.querySelectorAll('.pattern-list').forEach((el, i) => {{
            if (i < 5) el.classList.add('active');
        }});
    </script>
</body>
</html>
'''

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    # Also save to current_report.html for the server
    with open('logs/current_report.html', 'w', encoding='utf-8') as f:
        f.write(html)

    return output_path


def start_server_background():
    """Start the Flask server in a background thread."""
    try:
        from email_review_server import run_server
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        time.sleep(1)  # Give server time to start
        return True
    except Exception as e:
        print(f"Warning: Could not start server: {e}")
        return False


def main():
    """Main function to run the email categorization script."""
    # Parse arguments
    parser = argparse.ArgumentParser(description='Categorize and review Gmail emails.')
    parser.add_argument('--refresh', action='store_true',
                        help='Force refresh from Gmail API (ignore cache)')
    args = parser.parse_args()

    # Setup logging - all output goes to logs folder
    if not os.path.exists('logs'):
        os.makedirs('logs')

    log_filename = f"logs/categorize_emails_{time.strftime('%Y-%m-%d_%H-%M-%S')}.log"

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Clear existing handlers
    logger.handlers = []

    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    # Use UTF-8 encoding for console to handle emojis in email subjects
    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    # Set encoding to handle Unicode (Windows fix)
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass  # Ignore if reconfigure fails

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info("Starting email categorization with classification...")

    try:
        # Check for cached data first (unless --refresh is specified)
        cache_path, cache_age = find_cached_json()
        use_cache = False

        if args.refresh:
            logger.info("--refresh flag specified, fetching from Gmail API...")
        elif cache_path is None:
            logger.info("No cached data found, fetching from Gmail API...")
        elif cache_age > 5:
            logger.info(f"Cache is {cache_age:.1f} hours old (>5h), refreshing from Gmail API...")
        else:
            use_cache = True
            logger.info(f"Using cached data from {os.path.basename(cache_path)} ({cache_age:.1f} hours old)")

        if use_cache:
            # Load from cache
            email_details = load_cached_emails(logger, cache_path)
            logger.info(f"Loaded {len(email_details)} emails from cache.")
        else:
            # Fetch from Gmail API
            creds = get_credentials()
            gmail_service = build('gmail', 'v1', credentials=creds)
            logger.info("Gmail authentication successful.")

            email_details = fetch_all_unread_emails(logger, gmail_service)

            if not email_details:
                logger.info("No unread emails found.")
                return

            # Save raw JSON data to logs folder
            json_path = f"logs/emails_categorized_{time.strftime('%Y%m%d_%H%M%S')}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(email_details, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved raw data to {json_path}")

        # Group emails by domain and subject pattern
        grouped = group_emails_by_pattern(email_details)
        logger.info(f"Grouped emails into {len(grouped)} domains.")

        # Log category breakdown
        category_counts = defaultdict(int)
        for email in email_details:
            category_counts[email.get('category', 'UNKNOWN')] += 1
        logger.info(f"Category breakdown: {dict(category_counts)}")

        # Auto-add PROMO/NEWSLETTER patterns to delete criteria
        promo_count = category_counts.get('PROMO', 0) + category_counts.get('NEWSLETTER', 0)
        if promo_count > 0:
            added = auto_add_promo_to_criteria(logger, grouped)
            if added > 0:
                logger.info(f"PROMO emails will be deleted unless you click 'Keep' to override.")

        # Filter out already-decided emails (in criteria.json or keep_criteria.json)
        criteria, keep_criteria = load_existing_criteria()
        grouped, removed_count = filter_decided_emails(grouped, criteria, keep_criteria)

        if removed_count > 0:
            logger.info(f"Filtered out {removed_count} emails with existing decisions.")

        # Count remaining undecided emails
        remaining_emails = sum(
            sum(p['count'] for p in patterns.values())
            for patterns in grouped.values()
        )
        logger.info(f"Showing {remaining_emails} undecided emails in {len(grouped)} domains.")

        if not grouped:
            logger.info("All emails have been categorized! No undecided emails remaining.")
            return

        # Generate interactive HTML report
        html_path = f"logs/email_report_{time.strftime('%Y%m%d_%H%M%S')}.html"
        generate_interactive_html(email_details, grouped, html_path)
        logger.info(f"Generated interactive HTML report: {html_path}")

        # Start the Flask server in background
        logger.info("Starting review server...")
        server_started = start_server_background()

        # Open in browser
        if server_started:
            logger.info("Opening http://localhost:5000 in browser...")
            webbrowser.open('http://localhost:5000')
            logger.info("Server running. Press Ctrl+C to stop.")

            # Keep the main thread alive
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Server stopped.")
        else:
            # Fallback to static HTML
            abs_path = os.path.abspath(html_path)
            logger.info(f"Opening static report in browser...")
            webbrowser.open(f'file://{abs_path}')

        logger.info("Email categorization complete!")

    except HttpError as error:
        logger.error(f"Gmail API error: {error}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise


if __name__ == '__main__':
    main()
