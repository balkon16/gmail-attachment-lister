import re

class Transformer:

    @classmethod
    def extract_emails(cls, text):
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

    @classmethod
    def get_message_details(cls, message):
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