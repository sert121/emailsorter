import csv
import os


def load_existing_data(csv_file):
    """Load data from the CSV file."""
    if not os.path.exists(csv_file):
        # Initialize with headers if the file doesn't exist
        with open(csv_file, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Sender", "Subject", "Body Snippet", "Category", "Decision", "Round", "Status"])
        return []

    # Load existing rows
    with open(csv_file, "r", newline="") as file:
        reader = csv.DictReader(file)
        return list(reader)

def save_to_csv(data, csv_file):
    """Save data back to the CSV file."""
    with open(csv_file, "w", newline="") as file:
        fieldnames = ["Sender", "Subject", "Body Snippet", "Category", "Decision", "Round", "Status"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

def check_relevance_with_gpt(existing_row, email_doc):
    """
    Use GPT to determine if the email pertains to an existing job based on context.
    """
    openaiclient = OpenAI()
    prompt = (
        f"You are an assistant tasked with determining if two emails are related to the same job.\n"
        f"Here is the existing job email:\n"
        f"Subject: {existing_row['Subject']}\n"
        f"Body: {existing_row['Body Snippet']}\n\n"
        f"Here is the new email:\n"
        f"Subject: {email_doc['subject']}\n"
        f"Body: {email_doc['snippet']}\n\n"
        f"Does the new email build upon or pertain to the same job as the existing job in the row?"
        f" Reply 'Yes' or 'No' only."
    )

    response = openaiclient.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "system", "content": "You are a helpful assistant."},
                  {"role": "user", "content": prompt}],
        max_tokens=5,  
        temperature=0
    )
    
    answer = response["choices"][0]["message"]["content"].strip()
    if 'yes' in answer.lower():
        return True
    return False



def update_or_add_job(csv_file, email_doc):
    """
    Update the CSV file to reflect the status of a job.
    If the job (identified by sender and subject) exists, update its status; otherwise, add a new row.
    """
    existing_data = load_existing_data(csv_file)
    updated = False

    # Match existing row based on "Sender" and "Subject"
    for row in existing_data:
        if row["Sender"] == email_doc["sender"] and row["Subject"] == email_doc["subject"]:
            # Update relevant fields
            row["Body Snippet"] = email_doc["snippet"]
            row["Category"] = email_doc.get("category", "NA")
            row["Decision"] = email_doc.get("decision", "NA")
            row["Round"] = email_doc.get("round", "NA")
            row["Status"] = "Updated"  # Mark as updated
            updated = True
            break


    # Use LLM calls to relevance check if no exact match was found
    if not updated:
        for row in existing_data:
            is_relevant = check_relevance_with_gpt(row, email_doc)
            if is_relevant:
                # Update relevant fields based on relevance from LLM
                row["Body Snippet"] = email_doc["snippet"]
                row["Category"] = email_doc.get("category", "NA")
                row["Decision"] = email_doc.get("decision", "NA")
                row["Round"] = email_doc.get("round", "NA")
                row["Status"] = "Updated"  # Mark as 
                updated = True
                break

    # Add a new row if no match found
    if not updated:
        new_row = {
            "Sender": email_doc["sender"],
            "Subject": email_doc["subject"],
            "Body Snippet": email_doc["snippet"],
            "Category": email_doc.get("category", "NA"),
            "Decision": email_doc.get("decision", "NA"),
            "Round": email_doc.get("round", "NA"),
            "Status": "New"
        }
        existing_data.append(new_row)

    # Save updated data back to CSV
    save_to_csv(existing_data, csv_file)

