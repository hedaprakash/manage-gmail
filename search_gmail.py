import os
import argparse
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://mail.google.com/']
USER_ID = 'me' # Special value for the authenticated user

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

def count_emails(service, query):
    """Counts the number of emails matching a given query."""
    try:
        response = service.users().messages().list(userId=USER_ID, q=query).execute()
        return response.get('resultSizeEstimate', 0)
    except HttpError as error:
        print(f'An API error occurred: {error}')
        return 0

def main():
    """Searches for emails from a specific sender and prints the read/unread counts."""
    parser = argparse.ArgumentParser(description='Counts read and unread emails from a specific sender or in specific categories.')
    parser.add_argument('sender', type=str, nargs='?', default=None, help='The sender email or domain to search for (e.g., "USPS.com").')
    parser.add_argument('--promotions', action='store_true', help='Count unread promotional emails.')
    parser.add_argument('--social', action='store_true', help='Count unread social emails.')
    parser.add_argument('--forums', action='store_true', help='Count unread forum emails.')
    args = parser.parse_args()

    creds = get_credentials()
    try:
        gmail_service = build('gmail', 'v1', credentials=creds)

        if args.promotions:
            print("Searching for promotional emails...")
            promo_query = "category:promotions is:unread"
            promo_count = count_emails(gmail_service, promo_query)
            print(f"Unread promotional emails: {promo_count}")
        elif args.social:
            print("Searching for social emails...")
            social_query = "category:social is:unread"
            social_count = count_emails(gmail_service, social_query)
            print(f"Unread social emails: {social_count}")
        elif args.forums:
            print("Searching for forum emails...")
            forums_query = "category:forums is:unread"
            forums_count = count_emails(gmail_service, forums_query)
            print(f"Unread forum emails: {forums_count}")
        elif args.sender:
            sender = args.sender
            print(f"Searching for emails from: {sender}")

            # Count unread emails
            unread_query = f"from:{sender} is:unread"
            unread_count = count_emails(gmail_service, unread_query)
            print(f"Unread emails: {unread_count}")

            # Count read emails
            read_query = f"from:{sender} is:read"
            read_count = count_emails(gmail_service, read_query)
            print(f"Read emails: {read_count}")
        else:
            parser.print_help()

    except HttpError as error:
        print(f'An API error occurred: {error}')
    except Exception as e:
        print(f'An unexpected error occurred: {e}')

if __name__ == '__main__':
    main()
