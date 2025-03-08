import logging
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


class CredentialsManager:

    def __init__(self, token_path, client_secret_path, scopes):
        self.token_path = token_path
        self.client_secret_path = client_secret_path
        self.scopes = scopes
        self.creds = self._get_credentials()
        logging.info("Credentials obtained.")

    def _get_credentials(self):
        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, self.scopes)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secret_path, self.scopes
                )
                creds = flow.run_local_server(port=0)
            with open(self.token_path, "w") as token:
                token.write(creds.to_json())
        return creds

    def get_credentials(self):
        return self.creds