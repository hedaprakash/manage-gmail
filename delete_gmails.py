import os
import argparse
import time
import json
import logging
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://mail.google.com/']
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

def get_local_criteria(criteria_file='criteria.json'):
    """Fetches the deletion criteria from the specified criteria file."""
    if not os.path.exists(criteria_file):
        raise FileNotFoundError(f"{criteria_file} not found. Please create the criteria file first.")
    with open(criteria_file, 'r') as f:
        return json.load(f)

def build_query(criterion, min_age_days=0):
    """Builds a Gmail API search query string from a criterion dictionary.

    Args:
        criterion: Dictionary containing filter criteria
        min_age_days: Minimum age in days - only match emails older than this
    """
    query_parts = ['is:unread'] # Always search unread as per original script

    # Add age filter if specified (older_than:Xd)
    if min_age_days > 0:
        query_parts.append(f"older_than:{min_age_days}d")

    if criterion.get('email'):
        query_parts.append(f"from:{criterion['email']}")
    if criterion.get('subdomain'):
        query_parts.append(f"from:*@{criterion['subdomain']}")
    if criterion.get('primaryDomain'):
        query_parts.append(f"from:{criterion['primaryDomain']}")
    if criterion.get('subject'):
        query_parts.append(f"subject:(\"{criterion['subject']}\")") # Subject exact match
    if criterion.get('toEmails'):
        query_parts.append(f"to:(\"{criterion['toEmails']}\")") # To exact match
    if criterion.get('ccEmails'):
        query_parts.append(f"cc:(\"{criterion['ccEmails']}\")") # CC exact match
    if criterion.get('excludeSubject'):
        # Support multiple exclusions separated by comma
        exclusions = [e.strip() for e in criterion['excludeSubject'].split(',')]
        for exclusion in exclusions:
            if exclusion:
                query_parts.append(f"-subject:(\"{exclusion}\")")

    return " ".join(query_parts).strip()


def delete_emails_by_criteria(logger, gmail_service, criteria, dry_run, min_age_days=0):
    """
    Searches for and deletes (or dry-runs deletion of) emails based on the provided criteria.
    Logs the results.

    Args:
        min_age_days: Only delete emails older than this many days (0 = no age filter)
    """
    for i, criterion in enumerate(criteria):
        query = build_query(criterion, min_age_days)
        # Skip if query has no actual criteria (only base filters like is:unread and older_than)
        base_only = query.replace('is:unread', '').strip()
        if min_age_days > 0:
            base_only = base_only.replace(f'older_than:{min_age_days}d', '').strip()
        if not base_only:
            logger.warning(f"Skipping criterion {i+1} due to invalid query (no sender/subject criteria).")
            continue
        
        current_retries = 0
        current_delay = INITIAL_RETRY_DELAY
        success = False
        
        while current_retries < RETRY_ATTEMPTS:
            try:
                # Search for messages - log query to file only (debug level)
                logger.debug(f"Executing query: '{query}'")
                response = gmail_service.users().messages().list(userId=USER_ID, q=query).execute()
                messages = response.get('messages', [])
                
                # Collect all message IDs, handling pagination if necessary
                message_ids = []
                if messages:
                    while 'nextPageToken' in response:
                        for message in messages:
                            message_ids.append(message['id'])
                        page_token = response['nextPageToken']
                        response = gmail_service.users().messages().list(userId=USER_ID, q=query, pageToken=page_token).execute()
                        messages = response.get('messages', [])
                    else:
                        for message in messages:
                            message_ids.append(message['id'])
                
                # Log zero matches to file only, matches > 0 to console
                if len(message_ids) == 0:
                    logger.debug(f"  Found 0 matching emails for query: '{query}'")
                if message_ids:
                    logger.info(f"Found {len(message_ids)} emails - Query: '{query}'")
                    if not dry_run:
                        # Trash messages one by one
                        for message_id in message_ids:
                            gmail_service.users().messages().trash(userId=USER_ID, id=message_id).execute()
                        logger.info(f"  Successfully moved {len(message_ids)} emails to trash.")
                    else:
                        logger.info(f"  Dry run: Would move {len(message_ids)} emails to trash.")
                
                success = True
                break # Break out of retry loop on success

            except HttpError as error:
                if error.resp.status == 429: # Too Many Requests
                    current_retries += 1
                    logger.warning(f"  Rate limit exceeded (429). Retrying in {current_delay} seconds (attempt {current_retries}/{RETRY_ATTEMPTS})...")
                    time.sleep(current_delay)
                    current_delay *= 2 # Exponential backoff
                else:
                    logger.error(f'  Failed: Gmail API error: {error}')
                    break 
            except Exception as e:
                logger.error(f'  Failed: An unexpected error occurred: {e}')
                break
        
        if not success: 
            logger.error(f'  Failed: Retries exhausted for query: {query}')
        
        time.sleep(1)


def main():
    """Main function to run the email deletion script."""
    # --- Setup Logging ---
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    log_filename = f"logs/delete_gmails_{time.strftime('%Y-%m-%d_%H-%M-%S')}.log"

    # Create logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # File handler - logs everything including zero matches (DEBUG level)
    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    # Console handler - only logs matches and important info (INFO level)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    parser = argparse.ArgumentParser(description='Deletes Gmail messages based on criteria in a local JSON file.')
    parser.add_argument('--dry-run', action='store_true', help='Perform a dry run without deleting any emails.')
    parser.add_argument('--filter', type=str, help='Only process criteria containing this text in the sender columns.')
    parser.add_argument('--criteria-file', type=str, default='criteria.json',
                        help='Path to the criteria JSON file (default: criteria.json)')
    parser.add_argument('--min-age', type=int, default=0,
                        help='Only delete emails older than this many days (default: 0 = no age filter). '
                             'Use this to avoid deleting recent OTPs/verification codes.')
    args = parser.parse_args()

    logger.info("Starting email deletion script...")
    
    try:
        creds = get_credentials()
        gmail_service = build('gmail', 'v1', credentials=creds)
        logger.info("Gmail authentication successful.")

        logger.info(f"Fetching deletion criteria from {args.criteria_file}...")
        criteria = get_local_criteria(args.criteria_file)
        logger.info(f"Found {len(criteria)} total criteria.")

        if args.min_age > 0:
            logger.info(f"Age filter active: Only deleting emails older than {args.min_age} day(s).")

        # Filter criteria if the --filter argument is used
        if args.filter:
            logger.info(f"Filtering criteria for text: '{args.filter}'")
            original_count = len(criteria)
            filter_lower = args.filter.lower()
            criteria = [
                c for c in criteria if
                filter_lower in c.get('email', '').lower() or
                filter_lower in c.get('subdomain', '').lower() or
                filter_lower in c.get('primaryDomain', '').lower()
            ]
            logger.info(f"Filtered down to {len(criteria)} from {original_count} criteria.")

            # Also add a criterion based on the filter itself, as a primary domain.
            logger.info(f"Adding a broad criterion for filter: '{args.filter}'")
            criteria.append({'primaryDomain': args.filter, 'email': '', 'subdomain': '', 'subject': '', 'toEmails': '', 'ccEmails': '', 'excludeSubject': ''})
        
        if not criteria:
            logger.info("No criteria matched the filter.")
            return

        logger.info("Dry run mode active." if args.dry_run else "Live mode: Emails will be moved to trash.")
        delete_emails_by_criteria(logger, gmail_service, criteria, args.dry_run, args.min_age)
        
        logger.info("\nGmail processing complete.")
        logger.info("Script finished.")

    except HttpError as error:
        logger.error(f'An API error occurred: {error}')
    except Exception as e:
        logger.error(f'An unexpected error occurred: {e}')

if __name__ == '__main__':
    main()
