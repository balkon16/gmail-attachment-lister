import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

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


def get_message_details(message):
    msg_details = dict()

    headers_to_get = {'Subject', 'To', 'Cc'}

    # TODO: The 'Cc' header should be svaed as a list of e-mails, e.g. ['email1@email.com', 'email2@email.com']

    for h in message['payload']['headers']:
        if h['name'] in headers_to_get:
            msg_details[h['name']] = h['value']

    mime_types = {'application/pdf', 'image/png', 'image/jpeg'}

    msg_details['attachments'] = []

    for p in message['payload']['parts']:
        if p['mimeType'] in mime_types:
            msg_details['attachments'].append(p['body']['attachmentId'])

    return msg_details


if __name__ == "__main__":
    creds = get_credentials('../credentials/token.json', './credentials/client_secret.json', SCOPES)
    service = build("gmail", "v1", credentials=creds)
    thread_id = '1954dad91bb414ec'
    tdata = (
        service.users().threads().get(userId="me", id=thread_id).execute()
    )
    print("Threads retrieved.")
    results = []
    for msg in tdata['messages']:
        print(get_message_details(msg))
