from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from pymongo import MongoClient
import re, os
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from openai import OpenAI
from helpers import gpt_filter, get_body, get_full_email_details
import base64 
from datetime import datetime, timedelta


# Load environment variables
load_dotenv()

# Define Gmail API scope
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

SENDER_KEYWORDS = r"recruiter|careers|hiring|@company\.com"  # Add more domains/keywords
NO_REPLY_REGEX = r"^(no-?reply|donotreply|noreply)[\w.-]*@"
JOB_TITLE_KEYWORDS = r"job|application|interview|hiring|career|offer|update|hire|jobs"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def authenticate_gmail():
    """Authenticate and get Gmail API service."""
    creds = None
    # Token file stores user credentials (created after first auth)
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If no valid credentials, authenticate the user
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080)

        # Save credentials for future use
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    # Build the Gmail API service
    service = build('gmail', 'v1', credentials=creds)
    return service

def filter_email(sender, subject):
    """Filter based on regex for sender keywords and no-reply heuristics."""
    sender_email_match = re.search(r"<(.*?)>", sender)  # Extract email from "Name <email>"
    email_address = sender_email_match.group(1) if sender_email_match else sender

    if re.search(JOB_TITLE_KEYWORDS, email_address, re.IGNORECASE):
        return "job title match"
    if re.search(SENDER_KEYWORDS, email_address, re.IGNORECASE):
        return " sender keyword match"
    if re.search(NO_REPLY_REGEX, email_address, re.IGNORECASE):
        return "No-Reply email"

    return None


 
def fetch_emails(service, max_results=150, days=None, hours=None):
    """Fetch emails using Gmail API within a time range."""
    query = ""

    # Dynamically construct query based on the time range
    if days:
        query += f"newer_than:{days}d "
    if hours:
        now = datetime.now()
        past_time = now - timedelta(hours=hours)
        query += f"after:{past_time.strftime('%Y/%m/%d')} "

    print(f"Query: {query.strip()}")  # Debugging: Show constructed query

    # Add the query to the list method
    results = service.users().messages().list(userId='me', maxResults=max_results, q=query.strip()).execute()
    messages = results.get('messages', [])
    return messages

    

def list_emails(service):
    results = service.users().messages().list(userId='me', maxResults=10).execute()
    messages = results.get('messages', [])
    for msg in messages:
        print(msg,"\n")
        # print(f"Message snippet: {msg}")
        print(f"Message ID: {msg['id']}")

def main():

    openaiclient = OpenAI()

    saved_dictionaries = []

    service = authenticate_gmail()

    db_password = os.getenv("DB_PASSWORD")
    uri = os.getenv("URI")
    uri = uri.replace("<db_password>", db_password)
    client = MongoClient(uri)
    db = client.email_app
    collection = db.filtered_emails
    # Fetch and filter emails
    messages = fetch_emails(service)
    print("Filtering emails...")
    for msg in messages:

        emaildump = get_full_email_details(service, msg['id'])        
        sender, subject, body, snippet = emaildump['sender'], emaildump['subject'], emaildump['body'], emaildump['snippet']
        filter_result = filter_email(sender, subject)
        # exit()
        if filter_result:
            print(f" {sender} | {subject} | Filter: {filter_result}")

            filtered_info = gpt_filter(body=body, client=openaiclient)
            if filtered_info['job_related'] == 'Yes':
                email_doc = {
                    "sender": sender,
                    "subject": subject,
                    "body": body,
                    "snippet": snippet,
                    "category": filtered_info.get('category',"NA"),
                    "decision": filtered_info.get('decision',"NA"),
                    "round": filtered_info.get('round', "NA"),
                }
                saved_dictionaries.append(email_doc)
                collection.insert_one(email_doc)
                print(f"Saved: {sender} | {subject} | Filter: {filter_result}")


if __name__ == "__main__":
    main()
