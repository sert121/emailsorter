import imaplib
import email
from email.header import decode_header
import re, os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from pymongo import MongoClient
from openai import OpenAI
from helpers import gpt_filter
from save_to_db import update_or_add_job

# Load environment variables
load_dotenv()

# IMAP Configurations
IMAP_SERVER = "imap.gmail.com"
EMAIL_ACCOUNT = "yash.more@alumni.ashoka.edu.in"  # Replace with your Gmail account
PASSWORD = os.getenv("EMAIL_PASSWORD")
CSV_FILE = "job_applications.csv"

SENDER_KEYWORDS = r"recruiter|careers|hiring|@company\.com"
NO_REPLY_REGEX = r"^(no-?reply|donotreply|noreply)[\w.-]*@"
JOB_TITLE_KEYWORDS = r"job|application|interview|hiring|career|offer|update|hire|jobs"


def fetch_emails_imap(unread_only=False, max_emails=10):
    """Fetch emails from Gmail using IMAP, ordered latest to oldest."""
    try:
        # Connect to the Gmail IMAP server
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ACCOUNT, PASSWORD)

        # Select the inbox folder
        mail.select("inbox")

        # Search query: 'UNSEEN' for unread emails, 'ALL' for all emails
        search_criteria = "UNSEEN" if unread_only else "ALL"
        status, messages = mail.search(None, search_criteria)

        email_ids = messages[0].split()
        print(f"Total emails found: {len(email_ids)} (Mode: {'Unread' if unread_only else 'All'})")

        # Sort email IDs in descending order to get the latest emails first
        email_ids = email_ids[::-1]  # Reverse the list
       

        fetched_emails = []
        for email_id in email_ids[:max_emails]:  # Limit to max_emails
            # Fetch the email content
            _, msg_data = mail.fetch(email_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    # Parse the email
                    msg = email.message_from_bytes(response_part[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")
                    from_ = msg.get("From")

                    # Extract body
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            if content_type == "text/plain" and part.get_payload(decode=True):
                                body = part.get_payload(decode=True).decode()
                    else:
                        body = msg.get_payload(decode=True).decode()

                    fetched_emails.append({"sender": from_, "subject": subject, "body": body, "snippet": body[:100]})
        mail.logout()
        return fetched_emails

    except Exception as e:
        print(f"Error fetching emails: {e}")
        return []



def filter_email(sender, subject):
    """Filter based on regex for sender keywords and no-reply heuristics."""
    sender_email_match = re.search(r"<(.*?)>", sender)  # Extract email from "Name <email>"
    email_address = sender_email_match.group(1) if sender_email_match else sender

    if re.search(JOB_TITLE_KEYWORDS, email_address, re.IGNORECASE):
        return "job title match"
    if re.search(SENDER_KEYWORDS, email_address, re.IGNORECASE):
        return "sender keyword match"
    if re.search(NO_REPLY_REGEX, email_address, re.IGNORECASE):
        return "No-Reply email"

    return None


def main():
    openaiclient = OpenAI()

    saved_dictionaries = []

    # MongoDB setup
    db_password = os.getenv("DB_PASSWORD")
    uri = os.getenv("URI").replace("<db_password>", db_password)
    client = MongoClient(uri)
    db = client.email_app
    collection = db.filtered_emails

    # Fetch unread emails using IMAP
    print("Fetching unread emails...")
    emails = fetch_emails_imap()

    print("Filtering emails...")
    for email_data in emails:
        sender, subject, body, snippet = email_data["sender"], email_data["subject"], email_data["body"], email_data["snippet"]
        # filter_result = filter_email(sender, subject)
        
        # if filter_result:
        print(f" {sender} | {subject} | ")

        # Call GPT-based filtering
        filtered_info = gpt_filter(body=body, client=openaiclient)
        if filtered_info.get('job_related') == 'Yes':
            email_doc = {
                "sender": sender,
                "subject": subject,
                "body": body,
                "category": filtered_info.get('category', "NA"),
                "decision": filtered_info.get('decision', "NA"),
                "round": filtered_info.get('round', "NA"),
                "snippet":snippet,
            }
            saved_dictionaries.append(email_doc)
            update_or_add_job(CSV_FILE, email_doc)
            collection.insert_one(email_doc)
            # print(f"Saved: {sender} | {subject} | Filter: {filter_result}")


if __name__ == "__main__":
    main()
