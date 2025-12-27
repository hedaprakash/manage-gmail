import os
import argparse
import time
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/gmail.modify']
SHEET_ID = '1irHlPSUhhJMiy0cRd-X9MxgHG3IWMcodV0saY-36F3o'
PARAMETERS_SHEET_NAME = 'Parameters'
USER_ID = 'me' # Special value for the authenticated user

# Rate limit handling constants
RETRY_ATTEMPTS = 5
INITIAL_RETRY_DELAY = 5 # seconds

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

def fetch_parameters(sheets_service):
    """Fetches configuration parameters from the 'Parameters' sheet."""
    try:
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range=PARAMETERS_SHEET_NAME
        ).execute()
        values = result.get('values', [])
        if not values or len(values) < 2:
            return {}
        parameters = {row[0]: row[1] for row in values[1:] if len(row) > 1}
        return parameters
    except HttpError as error:
        print(f'An API error occurred while fetching parameters: {error}')
        raise

def get_deletion_criteria(sheets_service, sheet_name):
    """Fetches the deletion criteria from the specified sheet."""
    try:
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range=sheet_name
        ).execute()
        values = result.get('values', [])
        if not values:
            return [], []
        
        header = values[0]
        # These are the expected column headers from the original Apps Script
        # They will be used to map the sheet columns to the criterion dictionary keys
        expected_headers = [
            'email', 'subdomain', 'primaryDomain', 'subject', 'toEmails', 'ccEmails', 'excludeSubject'
        ]
        
        column_indices = {}
        for expected_header in expected_headers:
            try:
                column_indices[expected_header] = header.index(expected_header)
            except ValueError:
                print(f"Warning: Column '{expected_header}' not found in sheet header. It will be ignored.")
                column_indices[expected_header] = -1 # Indicate not found

        criteria = []
        for row in values[1:]: # Skip header row
            criterion = {}
            for key, index in column_indices.items():
                if index != -1 and index < len(row):
                    criterion[key] = str(row[index]).strip()
                else:
                    criterion[key] = ''
            # Only add criteria that are not completely empty
            if any(criterion.values()):
                criteria.append(criterion)

        return header, criteria
    except HttpError as error:
        print(f'An API error occurred while fetching deletion criteria: {error}')
        raise
    except ValueError as e:
        print(f"Error processing sheet '{sheet_name}': {e}")
        raise

def build_query(criterion):
    """Builds a Gmail API search query string from a criterion dictionary."""
    query_parts = ['is:unread'] # Always search unread as per original script

    if criterion.get('email'):
        query_parts.append(f"from:{criterion['email']}")
    if criterion.get('subdomain'):
        query_parts.append(f"from:*@{criterion['subdomain']}")
    if criterion.get('primaryDomain'):
        query_parts.append(f"from:*@{criterion['primaryDomain']}")
    if criterion.get('subject'):
        query_parts.append(f"subject:(\"{criterion['subject']}\")") # Subject exact match
    if criterion.get('toEmails'):
        query_parts.append(f"to:(\"{criterion['toEmails']}\")") # To exact match
    if criterion.get('ccEmails'):
        query_parts.append(f"cc:(\"{criterion['ccEmails']}\")") # CC exact match
    if criterion.get('excludeSubject'):
        query_parts.append(f"-subject:(\"{criterion['excludeSubject']}\")") # Exclude subject exact match
    
    # Remove 'is:unread' if no other specific criteria are present to avoid empty query issues,
    # or if the user intends to manage all emails matching a criteria regardless of read status.
    # For now, keeping as per original script.

    return " ".join(query_parts).strip()


def delete_emails_by_criteria(gmail_service, criteria, dry_run):
    """
    Searches for and deletes (or dry-runs deletion of) emails based on the provided criteria.
    Returns lists of statuses, deleted counts, and dry run counts.
    """
    statuses = []
    deleted_counts = []
    dry_run_counts = []

    for i, criterion in enumerate(criteria):
        query = build_query(criterion)
        if not query or query.strip() == 'is:unread': # If query is only 'is:unread' or empty, skip.
            print(f"Skipping criterion {i+1}: Invalid or too broad query generated: '{query}'")
            statuses.append('Failed: Invalid query')
            deleted_counts.append(0)
            dry_run_counts.append(0)
            time.sleep(1) # Pacing even for skipped criteria
            continue
        
        print(f"Processing criterion {i+1}: Query: '{query}'")
        
        current_retries = 0
        current_delay = INITIAL_RETRY_DELAY
        success = False
        
        while current_retries < RETRY_ATTEMPTS:
            try:
                # Search for messages
                response = gmail_service.users().messages().list(userId=USER_ID, q=query).execute()
                messages = response.get('messages', [])
                
                # Collect all message IDs, handling pagination if necessary
                message_ids = []
                while 'nextPageToken' in response:
                    for message in messages:
                        message_ids.append(message['id'])
                    page_token = response['nextPageToken']
                    response = gmail_service.users().messages().list(userId=USER_ID, q=query, pageToken=page_token).execute()
                    messages = response.get('messages', [])
                else:
                    # Add messages from the last page
                    for message in messages:
                        message_ids.append(message['id'])

                if message_ids:
                    print(f"  Found {len(message_ids)} matching emails.")
                    if not dry_run:
                        # Batch delete messages
                        batch_delete_request = {'ids': message_ids}
                        gmail_service.users().messages().batchDelete(userId=USER_ID, body=batch_delete_request).execute()
                        statuses.append('Success')
                        deleted_counts.append(len(message_ids))
                        dry_run_counts.append('')
                        print(f"  Successfully moved {len(message_ids)} emails to trash.")
                    else:
                        statuses.append('Dry Run')
                        deleted_counts.append('')
                        dry_run_counts.append(len(message_ids))
                        print(f"  Dry run: Would move {len(message_ids)} emails to trash.")
                else:
                    statuses.append('No matching emails found')
                    deleted_counts.append(0)
                    dry_run_counts.append(0)
                    print("  No matching emails found.")
                success = True
                break # Break out of retry loop on success

            except HttpError as error:
                if error.resp.status == 429: # Too Many Requests
                    current_retries += 1
                    print(f"  Rate limit exceeded (429). Retrying in {current_delay} seconds (attempt {current_retries}/{RETRY_ATTEMPTS})...")
                    time.sleep(current_delay)
                    current_delay *= 2 # Exponential backoff
                else:
                    error_message = f'Failed: Gmail API error: {error}'
                    print(f"  {error_message}")
                    statuses.append(error_message)
                    deleted_counts.append(0)
                    dry_run_counts.append(0)
                    break # Break out of retry loop for other HTTP errors
            except Exception as e:
                error_message = f'Failed: An unexpected error occurred: {e}'
                print(f"  {error_message}")
                statuses.append(error_message)
                deleted_counts.append(0)
                dry_run_counts.append(0)
                break # Break out of retry loop for other unexpected errors
        
        if not success: # If loop completed without success after retries
            error_message = f'Failed: Retries exhausted for query: {query}'
            print(f"  {error_message}")
            statuses.append(error_message)
            deleted_counts.append(0)
            dry_run_counts.append(0)
        
        time.sleep(1) # Pacing: Wait 1 second before processing the next criterion

    return statuses, deleted_counts, dry_run_counts


def main():
    """Main function to run the email deletion script."""
    parser = argparse.ArgumentParser(description='Deletes Gmail messages based on criteria in a Google Sheet.')
    parser.add_argument('--dry-run', action='store_true', help='Perform a dry run without deleting any emails.')
    args = parser.parse_args()

    print("Starting email deletion script...")
    creds = get_credentials()
    
    try:
        sheets_service = build('sheets', 'v4', credentials=creds)
        gmail_service = build('gmail', 'v1', credentials=creds)
        print("Authentication successful.")

        print("Fetching parameters from Google Sheet...")
        parameters = fetch_parameters(sheets_service)
        to_be_deleted_sheet_name = parameters.get('ToBeDeletedSheet')
        
        if not to_be_deleted_sheet_name:
            print("Error: 'ToBeDeletedSheet' parameter not found in the 'Parameters' sheet.")
            return

        print(f"Fetching deletion criteria from sheet: '{to_be_deleted_sheet_name}'")
        header, criteria = get_deletion_criteria(sheets_service, to_be_deleted_sheet_name)
        
        if not criteria:
            print("No deletion criteria found.")
            return
            
        print(f"Found {len(criteria)} criteria to process.")

        print("Dry run mode active." if args.dry_run else "Live mode: Emails will be moved to trash.")
        statuses, deleted_counts, dry_run_counts = delete_emails_by_criteria(gmail_service, criteria, args.dry_run)

        # The next step will be to write these results back to the Google Sheet.
        print("\nGmail processing complete.")
        print("Script finished. (Writing results to sheet to be implemented)")

    except HttpError as error:
        print(f'An API error occurred: {error}')
    except Exception as e:
        print(f'An unexpected error occurred: {e}')

if __name__ == '__main__':
    main()
