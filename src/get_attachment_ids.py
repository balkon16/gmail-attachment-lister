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


# TODO: given an attachment API, get its content
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


def get_threads_chunk(service, token, max_results=200):
    resp = service.users().threads().list(userId="me", maxResults=max_results, pageToken=token).execute()
    return resp.get("threads", []), resp.get("nextPageToken")


def get_messages(service, thread):
    print(f"Working with thread: {thread['id']}")
    tdata = (
        service.users().threads().get(userId="me", id=thread['id']).execute()
    )
    all_messages = tdata.get("messages", [])
    token = tdata.get("nextPageToken")
    while token:
        tdata = (
            service.users().threads().get(userId="me", id=thread['id'], nextPageToken=token).execute()
        )
        all_messages.extend(tdata.get("messages", []))
        token = tdata.get("nextPageToken")

    return all_messages


if __name__ == "__main__":
    prepare_file_structure()
    creds = get_credentials('../credentials/token.json', './credentials/client_secret.json', SCOPES)
    service = build("gmail", "v1", credentials=creds)

    max_results = 50  # dev
    i = 0  # dev
    all_threads, next_page_token = get_threads_chunk(service, None, max_results)
    print(f"Getting page no. {i}")

    while i < 1 and next_page_token:  # i < x -> dev
        i += 1
        print(f"Getting page no. {i}")
        threads, next_page_token = get_threads_chunk(service, next_page_token, max_results)
        all_threads.extend(threads)

    print(f"Got {str(len(all_threads))} threads in total.")
    ids = [t['id'] for t in all_threads]
    print(f"Got {str(len(set(ids)))} unique IDs in total.")

    for thread in all_threads:
        print(f"Working with thread: {thread['id']}")

        thread_output = []
        messages = get_messages(service, thread)
        for msg in messages:
            msg_data = get_message_details(msg)
            if len(msg_data['attachments']) > 0:
                thread_output.append(msg_data)

        if len(thread_output) > 0:
            with open(f"./output/{thread['id']}_data.json", "w") as outfile:
                json.dump(thread_output, outfile, indent=4, ensure_ascii=False, sort_keys=True)
