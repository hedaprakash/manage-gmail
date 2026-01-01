import os
import time
import json
import logging
import webbrowser
from datetime import datetime
from collections import defaultdict
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://mail.google.com/']
USER_ID = 'me'

# Processing constants
BATCH_SIZE = 100
MAX_RESULTS = 500

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


def fetch_unread_emails(logger, gmail_service):
    """Fetches unread emails and extracts their details."""
    email_details = []

    try:
        logger.info("Searching for unread emails...")
        response = gmail_service.users().messages().list(
            userId=USER_ID,
            q='is:unread',
            maxResults=MAX_RESULTS
        ).execute()

        messages = response.get('messages', [])
        total_messages = len(messages)
        logger.info(f"Found {total_messages} unread emails to process.")

        if not messages:
            return email_details

        # Process messages in batches
        for i, msg_info in enumerate(messages):
            try:
                # Get full message details
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

                email_details.append({
                    'id': msg_info['id'],
                    'email': email,
                    'from': from_header,
                    'subdomain': subdomain,
                    'primaryDomain': primary_domain,
                    'subject': subject,
                    'toEmails': to_emails,
                    'ccEmails': cc_emails,
                    'date': date
                })

                if (i + 1) % 50 == 0:
                    logger.info(f"Processed {i + 1}/{total_messages} emails...")

            except HttpError as e:
                logger.warning(f"Error fetching message {msg_info['id']}: {e}")
                continue
            except Exception as e:
                logger.warning(f"Unexpected error processing message: {e}")
                continue

        logger.info(f"Successfully extracted details for {len(email_details)} emails.")
        return email_details

    except HttpError as error:
        logger.error(f"Gmail API error: {error}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise


def categorize_by_domain(email_details):
    """Categorizes emails by primary domain."""
    categorized = defaultdict(list)
    for email in email_details:
        domain = email.get('primaryDomain', 'unknown')
        categorized[domain].append(email)
    return dict(categorized)


def generate_html_report(email_details, categorized, output_path):
    """Generates an HTML report of categorized emails."""

    # Sort domains by email count (descending)
    sorted_domains = sorted(categorized.items(), key=lambda x: len(x[1]), reverse=True)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Email Categorization Report</title>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #f5f5f5;
            padding: 20px;
            color: #333;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1 {{
            text-align: center;
            margin-bottom: 10px;
            color: #1a73e8;
        }}
        .summary {{
            text-align: center;
            margin-bottom: 30px;
            color: #666;
        }}
        .stats {{
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }}
        .stat-card {{
            background: white;
            padding: 20px 30px;
            border-radius: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            color: #1a73e8;
        }}
        .stat-label {{
            color: #666;
            margin-top: 5px;
        }}
        .domain-section {{
            background: white;
            margin-bottom: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .domain-header {{
            background: #1a73e8;
            color: white;
            padding: 15px 20px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .domain-header:hover {{
            background: #1557b0;
        }}
        .domain-name {{
            font-weight: bold;
            font-size: 1.1em;
        }}
        .domain-count {{
            background: rgba(255,255,255,0.2);
            padding: 5px 15px;
            border-radius: 20px;
        }}
        .email-list {{
            display: none;
            padding: 0;
        }}
        .email-list.active {{
            display: block;
        }}
        .email-item {{
            padding: 15px 20px;
            border-bottom: 1px solid #eee;
        }}
        .email-item:last-child {{
            border-bottom: none;
        }}
        .email-item:hover {{
            background: #f9f9f9;
        }}
        .email-from {{
            font-weight: 500;
            color: #1a73e8;
            margin-bottom: 5px;
        }}
        .email-subject {{
            color: #333;
            margin-bottom: 5px;
        }}
        .email-meta {{
            font-size: 0.85em;
            color: #999;
        }}
        .checkbox-col {{
            margin-right: 15px;
        }}
        .email-row {{
            display: flex;
            align-items: flex-start;
        }}
        .email-content {{
            flex: 1;
        }}
        .actions {{
            text-align: center;
            margin: 30px 0;
        }}
        .btn {{
            background: #1a73e8;
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 1em;
            margin: 0 10px;
        }}
        .btn:hover {{
            background: #1557b0;
        }}
        .btn-danger {{
            background: #dc3545;
        }}
        .btn-danger:hover {{
            background: #c82333;
        }}
        .btn-success {{
            background: #28a745;
        }}
        .btn-success:hover {{
            background: #218838;
        }}
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
        <h1>Email Categorization Report</h1>
        <p class="summary">Unread emails categorized by sender domain</p>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-number">{len(email_details)}</div>
                <div class="stat-label">Total Emails</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{len(categorized)}</div>
                <div class="stat-label">Unique Domains</div>
            </div>
        </div>

        <div class="actions">
            <button class="btn" onclick="expandAll()">Expand All</button>
            <button class="btn" onclick="collapseAll()">Collapse All</button>
            <button class="btn btn-success" onclick="exportSelected()">Export Selected to JSON</button>
        </div>

        <div id="domains">
'''

    for domain, emails in sorted_domains:
        email_items = ""
        for email in emails:
            subject = email.get('subject', '(No Subject)')
            # Escape HTML
            subject = subject.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            from_addr = email.get('from', '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            date = email.get('date', '')

            email_items += f'''
            <div class="email-item">
                <div class="email-row">
                    <div class="checkbox-col">
                        <input type="checkbox" class="email-checkbox" data-domain="{domain}" data-email='{json.dumps(email).replace("'", "&#39;")}'>
                    </div>
                    <div class="email-content">
                        <div class="email-from">{from_addr}</div>
                        <div class="email-subject">{subject}</div>
                        <div class="email-meta">{date}</div>
                    </div>
                </div>
            </div>
'''

        html += f'''
        <div class="domain-section">
            <div class="domain-header" onclick="toggleSection(this)">
                <span class="domain-name">{domain}</span>
                <span class="domain-count">{len(emails)} emails</span>
            </div>
            <div class="email-list">
                {email_items}
            </div>
        </div>
'''

    html += f'''
        </div>

        <p class="timestamp">Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    </div>

    <script>
        function toggleSection(header) {{
            const emailList = header.nextElementSibling;
            emailList.classList.toggle('active');
        }}

        function expandAll() {{
            document.querySelectorAll('.email-list').forEach(el => el.classList.add('active'));
        }}

        function collapseAll() {{
            document.querySelectorAll('.email-list').forEach(el => el.classList.remove('active'));
        }}

        function exportSelected() {{
            const selected = [];
            document.querySelectorAll('.email-checkbox:checked').forEach(cb => {{
                selected.push(JSON.parse(cb.dataset.email));
            }});

            if (selected.length === 0) {{
                alert('No emails selected. Please select emails to export.');
                return;
            }}

            const blob = new Blob([JSON.stringify(selected, null, 2)], {{type: 'application/json'}});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'selected_emails.json';
            a.click();
            URL.revokeObjectURL(url);
        }}
    </script>
</body>
</html>
'''

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return output_path


def main():
    """Main function to run the email categorization script."""
    # Setup logging
    if not os.path.exists('logs'):
        os.makedirs('logs')

    if not os.path.exists('output'):
        os.makedirs('output')

    log_filename = f"logs/categorize_emails_{time.strftime('%Y-%m-%d_%H-%M-%S')}.log"

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info("Starting email categorization...")

    try:
        # Authenticate
        creds = get_credentials()
        gmail_service = build('gmail', 'v1', credentials=creds)
        logger.info("Gmail authentication successful.")

        # Fetch and extract email details
        email_details = fetch_unread_emails(logger, gmail_service)

        if not email_details:
            logger.info("No unread emails found.")
            return

        # Save raw JSON data
        json_path = f"output/emails_categorized_{time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(email_details, f, indent=2)
        logger.info(f"Saved raw data to {json_path}")

        # Categorize by domain
        categorized = categorize_by_domain(email_details)
        logger.info(f"Categorized emails into {len(categorized)} domains.")

        # Generate HTML report
        html_path = f"output/email_report_{time.strftime('%Y%m%d_%H%M%S')}.html"
        generate_html_report(email_details, categorized, html_path)
        logger.info(f"Generated HTML report: {html_path}")

        # Open HTML in browser
        abs_path = os.path.abspath(html_path)
        logger.info(f"Opening report in browser...")
        webbrowser.open(f'file://{abs_path}')

        logger.info("Email categorization complete!")

    except HttpError as error:
        logger.error(f"Gmail API error: {error}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise


if __name__ == '__main__':
    main()
