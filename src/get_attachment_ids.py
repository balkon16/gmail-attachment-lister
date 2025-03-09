import json
import os
import os.path
import logging
import base64

from googleapiclient.discovery import build

from modules.utils import Utils
from modules.credentials import CredentialsManager
from modules.transform import Transformer
from modules.fetch import ThreadFetcher

CREDENTIALS_DIR = './credentials'

# TODO: the script should be divided into three parts:
#  > getting Gmail's results page
#  > getting attachment info (e.g. message ID, attachment ID)
#  > getting the file
# TODO: can you use more than one thread when getting data using the next page token?


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

    Utils.prepare_file_structure()

    creds_manager = CredentialsManager(
        os.path.join(CREDENTIALS_DIR, 'token.json'),
        os.path.join(CREDENTIALS_DIR, 'client_secret.json'),
        ["https://www.googleapis.com/auth/gmail.readonly"]
    )



    logging.info("Building service.")
    service = build("gmail", "v1", credentials=creds_manager.get_credentials())

    # this operation takes around 1 minute using a single thread
    # this operation takes around 1 minute using 4 threads and doesn't retrieve all data
    #   -> needed rework with network issues in mind
    fetcher = ThreadFetcher(service, num_threads=1)

    all_threads = fetcher.get_all_threads()
    all_threads_count = len(all_threads)
    logging.info(f"Got {str(len(all_threads))} threads in total.")
    ids = [t['id'] for t in all_threads]
    logging.info(f"Got {str(len(set(ids)))} unique IDs in total.")

    with open('./output/thread_ids.json', 'w') as wh:
        json.dump(ids, wh, indent=4, ensure_ascii=False)
    # logging.info(f"There are {all_threads_count} in total.")
    # exit(0)

    # for i, thread in enumerate(all_threads, 1):
    #     progress_msg = f"Working with thread: {thread['id']}."
    #     if i % 100 == 0:
    #         progress_msg += f" Progress: {i} out of {all_threads_count}."
    #     logging.info(progress_msg)
    #
    #     thread_output = []
    #     messages = get_messages(service, thread)
    #
    #     for msg in messages:
    #         msg_data = Transformer.get_message_details(msg)
    #         if len(msg_data['attachments']) > 0:
    #             thread_output.append(msg_data)
    #
    #     if len(thread_output) > 0:
    #         for output_dict in thread_output:
    #             msg_id = output_dict['id']
    #             for attachment in output_dict['attachments']:
    #                 get_and_save_attachment(service, msg_id, attachment['id'], attachment['filename'])
    #         with open(f"./output/{thread['id']}_data.json", "w") as outfile:
    #             json.dump(thread_output, outfile, indent=4, ensure_ascii=False, sort_keys=True)
