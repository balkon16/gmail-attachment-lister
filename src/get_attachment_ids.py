import json
import os
import re
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


# TODO: given an attachment API, get its conent
#  https://developers.google.com/gmail/api/reference/rest/v1/users.messages.attachments/get
# TODO: transform attachments from base64 to readable format


def get_credentials(token_path, client_secret_path, scopes):
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secret_path, SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as token:
            token.write(creds.to_json())
    return creds


def prepare_file_structure():
    os.makedirs("./output", exist_ok=True)
    os.makedirs("./credentials", exist_ok=True)


def extract_emails(text):
    """
    Extracts email addresses from a string and returns them as a list.
    Handles names and angle brackets around the email addresses.

    Args:
      text: The input string.

    Returns:
      A list of email addresses found in the string.  Returns an empty list if no emails are found.
    """
    email_pattern = r"<([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})>"
    emails = re.findall(email_pattern, text)
    return emails


def get_message_details(message):
    msg_details = dict()

    headers_to_get = {'Subject', 'To', 'Cc', 'From'}

    for h in message['payload']['headers']:
        if h['name'] in headers_to_get:
            if h['name'] in {'Cc', 'To', 'From'}:
                msg_details[h['name']] = re.findall(r"<(.*?)>", h['value'])
            else:
                msg_details[h['name']] = h['value']

    mime_types = {'application/pdf', 'image/png', 'image/jpeg'}

    msg_details['attachments'] = []

    parts = message['payload'].get('parts', [])
    for p in parts:
        if p['mimeType'] in mime_types:
            msg_details['attachments'].append(p['body']['attachmentId'])

    return msg_details


if __name__ == "__main__":
    prepare_file_structure()
    creds = get_credentials('../credentials/token.json', './credentials/client_secret.json', SCOPES)
    service = build("gmail", "v1", credentials=creds)

    threads = (
        service.users().threads().list(userId="me", limit=10).execute().get("threads", []) # TODO: get than 100 threads
    )

    # threads = [{"id": ""}] # debugging

    for thread in threads:
        print(f"Working with thread: {thread['id']}")

        tdata = (
            service.users().threads().get(userId="me", id=thread['id']).execute()
        )
        thread_data = []
        for msg in tdata['messages']:
            msg_data = get_message_details(msg)
            if len(msg_data['attachments']) > 0:
                thread_data.append(msg_data)
                with open(f"./output/{thread['id']}_data.json", "w") as outfile:
                    json.dump(thread_data, outfile, indent=4, ensure_ascii=False, sort_keys=True)