import os
import json
import re
import argparse
import time
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://mail.google.com/']
USER_ID = 'me'

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


def parse_unsubscribe_header(header_value):
    """Parse the List-Unsubscribe header and extract URLs and mailto links."""
    links = []
    if not header_value:
        return links

    # Extract URLs and mailto links from angle brackets
    # Format: <https://example.com/unsub>, <mailto:unsub@example.com>
    matches = re.findall(r'<([^>]+)>', header_value)
    for match in matches:
        if match.startswith('http://') or match.startswith('https://'):
            links.append({'type': 'http', 'url': match})
        elif match.startswith('mailto:'):
            links.append({'type': 'mailto', 'url': match})

    return links


def get_unsubscribe_info(gmail_service, message_id):
    """Get unsubscribe information from a message's headers."""
    try:
        msg = gmail_service.users().messages().get(
            userId=USER_ID,
            id=message_id,
            format='metadata',
            metadataHeaders=['From', 'Subject', 'List-Unsubscribe', 'List-Unsubscribe-Post', 'Date']
        ).execute()

        headers = msg.get('payload', {}).get('headers', [])
        header_dict = {h['name'].lower(): h['value'] for h in headers}

        unsubscribe_header = header_dict.get('list-unsubscribe', '')
        unsubscribe_post = header_dict.get('list-unsubscribe-post', '')  # For one-click unsubscribe

        if unsubscribe_header:
            links = parse_unsubscribe_header(unsubscribe_header)
            return {
                'from': header_dict.get('from', 'Unknown'),
                'subject': header_dict.get('subject', 'No Subject'),
                'date': header_dict.get('date', ''),
                'links': links,
                'one_click': bool(unsubscribe_post),  # RFC 8058 one-click unsubscribe
                'message_id': message_id
            }
    except HttpError as e:
        print(f"  Error fetching message {message_id}: {e}")

    return None


def extract_unsubscribe_links(gmail_service, criteria, max_per_sender=5):
    """Extract unsubscribe links from emails matching the criteria."""
    unsubscribe_data = {}

    for i, criterion in enumerate(criteria):
        # Build a simple query for this sender
        query_parts = []
        sender_id = None

        if criterion.get('email'):
            query_parts.append(f"from:{criterion['email']}")
            sender_id = criterion['email']
        elif criterion.get('subdomain'):
            query_parts.append(f"from:*@{criterion['subdomain']}")
            sender_id = criterion['subdomain']
        elif criterion.get('primaryDomain'):
            query_parts.append(f"from:{criterion['primaryDomain']}")
            sender_id = criterion['primaryDomain']

        if not query_parts or not sender_id:
            continue

        # Skip if we already processed this sender
        if sender_id in unsubscribe_data:
            continue

        query = " ".join(query_parts)

        try:
            # Get a few recent messages from this sender
            response = gmail_service.users().messages().list(
                userId=USER_ID,
                q=query,
                maxResults=max_per_sender
            ).execute()

            messages = response.get('messages', [])

            if messages:
                print(f"Checking: {sender_id}")

                for msg in messages:
                    unsub_info = get_unsubscribe_info(gmail_service, msg['id'])
                    if unsub_info and unsub_info['links']:
                        # Store by sender domain/email
                        if sender_id not in unsubscribe_data:
                            unsubscribe_data[sender_id] = unsub_info
                            print(f"  Found unsubscribe link!")
                            break  # One link per sender is enough

                time.sleep(0.2)  # Rate limiting

        except HttpError as e:
            print(f"  Error searching for {sender_id}: {e}")
            continue

    return unsubscribe_data


def generate_html_report(unsubscribe_data, output_file):
    """Generate an HTML report with unsubscribe links."""

    # Separate by type
    one_click = []
    http_links = []
    mailto_links = []

    for sender_id, data in unsubscribe_data.items():
        entry = {
            'sender_id': sender_id,
            'from': data['from'],
            'subject': data['subject'],
            'links': data['links'],
            'one_click': data['one_click']
        }

        if data['one_click']:
            one_click.append(entry)

        for link in data['links']:
            if link['type'] == 'http':
                http_links.append({**entry, 'url': link['url']})
            elif link['type'] == 'mailto':
                mailto_links.append({**entry, 'url': link['url']})

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Unsubscribe Links Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; background: #f5f5f5; }}
        h1 {{ color: #333; }}
        h2 {{ color: #666; margin-top: 30px; }}
        .summary {{ background: #fff; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
        .summary span {{ display: inline-block; margin-right: 20px; padding: 5px 10px; border-radius: 4px; }}
        .one-click {{ background: #d4edda; color: #155724; }}
        .http {{ background: #cce5ff; color: #004085; }}
        .mailto {{ background: #fff3cd; color: #856404; }}
        table {{ border-collapse: collapse; width: 100%; background: #fff; border-radius: 8px; overflow: hidden; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #333; color: #fff; }}
        tr:hover {{ background: #f5f5f5; }}
        .sender {{ font-weight: bold; color: #333; }}
        .from {{ color: #666; font-size: 0.9em; }}
        a {{ color: #007bff; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .btn {{ display: inline-block; padding: 6px 12px; background: #007bff; color: #fff; border-radius: 4px; text-decoration: none; margin: 2px; }}
        .btn:hover {{ background: #0056b3; text-decoration: none; }}
        .btn-success {{ background: #28a745; }}
        .btn-warning {{ background: #ffc107; color: #333; }}
        .warning {{ background: #fff3cd; border: 1px solid #ffc107; padding: 10px; border-radius: 4px; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <h1>Unsubscribe Links Report</h1>
    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

    <div class="summary">
        <strong>Summary:</strong>
        <span class="one-click">One-Click: {len(one_click)}</span>
        <span class="http">HTTP Links: {len(http_links)}</span>
        <span class="mailto">Mailto Links: {len(mailto_links)}</span>
    </div>

    <div class="warning">
        <strong>Warning:</strong> Review each link before clicking. Only unsubscribe from senders you recognize.
    </div>
"""

    if one_click:
        html += """
    <h2>One-Click Unsubscribe (Safest)</h2>
    <p>These support RFC 8058 one-click unsubscribe - can be automated safely.</p>
    <table>
        <tr><th>Sender</th><th>From</th><th>Action</th></tr>
"""
        for entry in one_click:
            http_url = next((l['url'] for l in entry['links'] if l['type'] == 'http'), '#')
            html += f"""        <tr>
            <td class="sender">{entry['sender_id']}</td>
            <td class="from">{entry['from'][:60]}...</td>
            <td><a href="{http_url}" target="_blank" class="btn btn-success">Unsubscribe</a></td>
        </tr>
"""
        html += "    </table>\n"

    if http_links:
        html += """
    <h2>HTTP Unsubscribe Links</h2>
    <p>Click to open unsubscribe page in browser.</p>
    <table>
        <tr><th>Sender</th><th>From</th><th>Action</th></tr>
"""
        seen = set()
        for entry in http_links:
            if entry['sender_id'] in seen:
                continue
            seen.add(entry['sender_id'])
            html += f"""        <tr>
            <td class="sender">{entry['sender_id']}</td>
            <td class="from">{entry['from'][:60]}...</td>
            <td><a href="{entry['url']}" target="_blank" class="btn">Unsubscribe</a></td>
        </tr>
"""
        html += "    </table>\n"

    if mailto_links:
        html += """
    <h2>Mailto Unsubscribe Links</h2>
    <p>These require sending an email to unsubscribe.</p>
    <table>
        <tr><th>Sender</th><th>From</th><th>Action</th></tr>
"""
        seen = set()
        for entry in mailto_links:
            if entry['sender_id'] in seen:
                continue
            seen.add(entry['sender_id'])
            html += f"""        <tr>
            <td class="sender">{entry['sender_id']}</td>
            <td class="from">{entry['from'][:60]}...</td>
            <td><a href="{entry['url']}" class="btn btn-warning">Send Unsubscribe Email</a></td>
        </tr>
"""
        html += "    </table>\n"

    html += """
</body>
</html>
"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    return len(unsubscribe_data)


def main():
    parser = argparse.ArgumentParser(description='Extract unsubscribe links from emails.')
    parser.add_argument('--max-per-sender', type=int, default=3, help='Max emails to check per sender')
    args = parser.parse_args()

    print("Starting unsubscribe link extraction...")

    # Ensure output directory exists
    if not os.path.exists('output'):
        os.makedirs('output')

    try:
        creds = get_credentials()
        gmail_service = build('gmail', 'v1', credentials=creds)
        print("Gmail authentication successful.")

        # Load criteria
        if not os.path.exists('criteria.json'):
            print("Error: criteria.json not found.")
            return

        with open('criteria.json', 'r') as f:
            criteria = json.load(f)

        print(f"Loaded {len(criteria)} criteria from criteria.json")
        print("Extracting unsubscribe links (this may take a few minutes)...\n")

        # Extract unsubscribe links
        unsubscribe_data = extract_unsubscribe_links(gmail_service, criteria, args.max_per_sender)

        if not unsubscribe_data:
            print("\nNo unsubscribe links found.")
            return

        # Save JSON data
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_file = f"output/unsubscribe_links_{timestamp}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(unsubscribe_data, f, indent=2)
        print(f"\nSaved JSON data to: {json_file}")

        # Generate HTML report
        html_file = f"output/unsubscribe_report_{timestamp}.html"
        count = generate_html_report(unsubscribe_data, html_file)
        print(f"Generated HTML report: {html_file}")
        print(f"\nFound unsubscribe links for {count} senders.")
        print("Open the HTML report to review and click unsubscribe links.")

    except HttpError as error:
        print(f'An API error occurred: {error}')
    except Exception as e:
        print(f'An unexpected error occurred: {e}')


if __name__ == '__main__':
    main()
