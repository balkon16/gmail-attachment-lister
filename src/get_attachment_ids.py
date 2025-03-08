import json
import os
import re
import os.path
import logging
import base64

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


# TODO: the script should be divided into three parts:
#  > getting Gmail's results page
#  > getting attachment info (e.g. message ID, attachment ID)
#  > getting the file


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
    os.makedirs("./output/attachments", exist_ok=True)
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
    msg_details = {
        "id": message["id"]
    }

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
            msg_details['attachments'].append(
                {
                    "id": p['body']['attachmentId'],
                    "filename": p['filename']
                }
            )

    return msg_details


def get_threads_chunk(service, token, max_results=200):
    resp = service.users().threads().list(userId="me", maxResults=max_results, pageToken=token).execute()
    return resp.get("threads", []), resp.get("nextPageToken")


def get_messages(service, thread):
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


def get_and_save_attachment(service, message_id, attachment_id, filename, output_path='./output/attachments'):
    attachment_resp = service.users().messages().attachments().get(
        userId='me', messageId=message_id, id=attachment_id).execute()

    file_data = attachment_resp['data']
    file_data = file_data.replace('-', '+').replace('_', '/')  # Decode base64

    decoded_data = base64.b64decode(file_data)

    file_path = os.path.join(output_path, filename)

    with open(file_path, 'wb') as f:
        f.write(decoded_data)

    logging.info(f"Got and saved {filename}.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    logging.info("Preparing file structure.")
    prepare_file_structure()

    logging.info("Getting credentials.")
    creds = get_credentials('../credentials/token.json', './credentials/client_secret.json', SCOPES)

    logging.info("Building service.")
    service = build("gmail", "v1", credentials=creds)

    max_results = 50  # dev
    i = 0  # dev
    all_threads, next_page_token = get_threads_chunk(service, None, max_results)
    logging.info(f"Getting page no. {i}")

    while i < 1 and next_page_token:  # i < x -> dev
    # while next_page_token:
        i += 1
        logging.info(f"Getting page no. {i}")
        threads, next_page_token = get_threads_chunk(service, next_page_token, max_results)
        all_threads.extend(threads)

    logging.info(f"Got {str(len(all_threads))} threads in total.")
    ids = [t['id'] for t in all_threads]
    logging.info(f"Got {str(len(set(ids)))} unique IDs in total.")

    all_threads_count = len(all_threads)
    for i, thread in enumerate(all_threads, 1):
        progress_msg = f"Working with thread: {thread['id']}."
        if i % 100 == 0:
            progress_msg += f" Progress: {i} out of {all_threads_count}."
        logging.info(progress_msg)

        thread_output = []
        messages = get_messages(service, thread)

        for msg in messages:
            msg_data = get_message_details(msg)
            if len(msg_data['attachments']) > 0:
                thread_output.append(msg_data)

        if len(thread_output) > 0:
            for output_dict in thread_output:
                msg_id = output_dict['id']
                for attachment in output_dict['attachments']:
                    get_and_save_attachment(service, msg_id, attachment['id'], attachment['filename'])
            with open(f"./output/{thread['id']}_data.json", "w") as outfile:
                json.dump(thread_output, outfile, indent=4, ensure_ascii=False, sort_keys=True)
