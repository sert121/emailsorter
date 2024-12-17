import os, json, base64
from bs4 import BeautifulSoup  # For stripping HTML tags (optional)



def gpt_filter(body, client):
    prompt = f"""
You are an assistant that classifies job-related emails based on their content. Analyze the following email and classify it into one of the following categories:

1. Applied: Indicates that the email confirms the submission of a job application.
2. Got Interview: Indicates that the email invites the candidate to an interview or provides interview details. Also specify the round of the interview (e.g., "Round 1", "Round 2", or "Final Round").
- If its a specific round i.e it mentions the round number, then specify the round number.
- If its a general interview invite, then specify the type of round i,e <TYPE> that can be coding/phonecall/test based on the body of the email.
3. Got Decision: Indicates that the email provides the result of the interview:
- "Success" if the candidate passed.
- "Reject" if the candidate was not selected.
4. Not Job-Related: If the email is not related to a job application or interview process.

Here is the email content:
---
{body}
---

Please respond strictly in the following JSON format:
{{
"job_related": "Yes" or "No",
"category": "Applied" or "Got Interview" or "Got Decision" or "NA",
"decision": "Success" or "Reject" ( if category is 'Got Decision', else 'NA'),
"round": "Round <TYPE>" (only required if category is 'Got Interview', else 'NA')
}}
"""
    completion = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "developer", "content": "You are a helpful assistant."},
        {"role": "user", "content": f"{prompt}"}]
    )

    possible_json = completion.choices[0].message.content
    possible_json = possible_json.strip('`').strip()
    possible_json = possible_json.strip("json")
    print(possible_json)
    try:
        json_response = eval(possible_json)
    except json.JSONDecodeError:
        json_response = None

    return json_response



def get_minified_email_details(service, message_id):
    """Get email sender, subject, and snippet."""
    message = service.users().messages().get(userId='me', id=message_id, format='metadata', metadataHeaders=['From', 'Subject']).execute()
    headers = message['payload']['headers']
    sender = subject = ""
    for header in headers:
        if header['name'] == 'From':
            sender = header['value']
        if header['name'] == 'Subject':
            subject = header['value']
    snippet = message.get('snippet', '')

    return sender, subject, snippet


def get_full_email_details(service, message_id):
    """Get email sender, subject, and full text body."""
    # Retrieve the full email message
    message = service.users().messages().get(
        userId='me',
        id=message_id,
        format='full',
    ).execute()
    
    headers = message['payload']['headers']
    sender = subject = ""

    # Extract 'From' and 'Subject' headers
    for header in headers:
        if header['name'] == 'From':
            sender = header['value']
        if header['name'] == 'Subject':
            subject = header['value']

    snippet = message.get('snippet', '')

    # Enhanced recursive function to handle all MIME types
    def extract_text(payload):
        """Recursively extract text content from all MIME types."""
        # If 'parts' exists, process recursively
        if 'parts' in payload:
            # Prioritize text/plain but fallback to text/html
            all_text = []
            for part in payload['parts']:
                text = extract_text(part)
                if text:
                    all_text.append(text)
            return "\n".join(all_text).strip()

        # Handle single MIME type
        mime_type = payload.get('mimeType', '')
        body_data = payload.get('body', {}).get('data', '')

        if body_data:
            decoded_bytes = base64.urlsafe_b64decode(body_data.encode('UTF-8'))
            decoded_text = decoded_bytes.decode('UTF-8', errors='ignore')

            # Prioritize text/plain over text/html
            if mime_type == 'text/plain':
                return decoded_text.strip()
            elif mime_type == 'text/html':
                # Use BeautifulSoup to strip HTML tags
                return BeautifulSoup(decoded_text, 'html.parser').get_text().strip()
        return ""


    # Extract body text using the enhanced function
    body_text = extract_text(message['payload'])

    return {
        'sender': sender,
        'subject': subject,
        'body': body_text or "",
        'snippet': snippet  
    }


def get_body(payload):
    """Recursively extract text content from all MIME types."""
    # If 'parts' exists, process recursively
    if 'parts' in payload:
        # Prioritize text/plain but fallback to text/html
        all_text = []
        for part in payload['parts']:
            text = extract_text(part)
            if text:
                all_text.append(text)
        return "\n".join(all_text).strip()

    # Handle single MIME type
    mime_type = payload.get('mimeType', '')
    body_data = payload.get('body', {}).get('data', '')

    if body_data:
        decoded_bytes = base64.urlsafe_b64decode(body_data.encode('UTF-8'))
        decoded_text = decoded_bytes.decode('UTF-8', errors='ignore')

        # Prioritize text/plain over text/html
        if mime_type == 'text/plain':
            return decoded_text.strip()
        elif mime_type == 'text/html':
            # Use BeautifulSoup to strip HTML tags
            return BeautifulSoup(decoded_text, 'html.parser').get_text().strip()
    return ""

    # Extract body text using the enhanced function
    body_text = extract_text(message['payload'])

    return {
    'sender': sender,
    'subject': subject,
    'body': body_text or "No body found"
    }

