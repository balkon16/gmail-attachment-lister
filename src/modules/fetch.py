import logging
import random
import threading
from queue import Queue
import time

class ThreadFetcher:

    def __init__(self, service, max_results=200, num_threads=4):
        self.service = service
        self.max_results = max_results
        self.already_used_tokens = set()
        self.num_threads = num_threads
        self.threads_queue = Queue()  # Queue for storing thread data
        self.all_threads = []
        self.lock = threading.Lock()  # Lock for thread-safe access to shared resources

    def exponential_backoff(self, func, max_retries=5, base_delay=1, max_delay=60, exceptions=(Exception,)):
        """
        Implements exponential backoff for a function that might fail.

        Args:
            func: The function to execute.
            max_retries: The maximum number of retries.
            base_delay: The base delay in seconds (e.g., 1 second).
            max_delay: The maximum delay in seconds (e.g., 60 seconds).
            exceptions: A tuple of exception types to catch and retry on.  Defaults to all Exceptions.

        Returns:
            The result of the function if successful.

        Raises:
            Exception: If the function fails after max_retries.
        """

        retries = 0
        while retries < max_retries:
            try:
                return func()  # Attempt to execute the function
            except exceptions as e:
                retries += 1
                if retries == max_retries:
                    raise  # Re-raise the exception if max retries reached

                delay = min(base_delay * (2 ** (retries - 1)), max_delay)  # Calculate delay
                jitter = random.uniform(0, delay * 0.1)  # Add a small amount of jitter
                delay += jitter

                logging.info(f"Attempt {retries} failed with error: {e}.  Retrying in {delay:.2f} seconds...")
                time.sleep(delay)

        raise Exception("Max retries reached without success.")

    def _get_threads_chunk(self, token=None):
        """Fetches a chunk of threads from the API."""
        # while
        try:
            resp = self.service.users().threads().list(userId="me", maxResults=self.max_results,
                                                       pageToken=token).execute()
            return resp.get("threads", []), resp.get("nextPageToken")
        except Exception as e:
            logging.error(f"Error fetching threads with token {token}: {e}")
            return [], None  # Return empty list and None to signal an error

    def _worker(self):
        """Worker thread function."""
        while True:
            logging.info("Started the _worker func.")
            token = self.threads_queue.get()
            if token is None:  # Sentinel value to signal thread termination
                self.threads_queue.task_done()
                break

            if token in self.already_used_tokens:
                logging.warning(f"Thread {threading.current_thread().name}: Token {token} already used. Skipping.")
                self.threads_queue.task_done()
                continue

            logging.info(f"Thread {threading.current_thread().name}: Fetching threads with token {token}")
            # threads, next_page_token = self._get_threads_chunk(token)
            threads, next_page_token = self.exponential_backoff(lambda: self._get_threads_chunk(token), max_retries=3,)

            with self.lock:  # Acquire lock before modifying shared resources
                self.all_threads.extend(threads)
                self.already_used_tokens.add(token)  # Add token to used tokens

            if next_page_token:
                self.threads_queue.put(next_page_token)  # Add the next page token to the queue
            else:
                logging.info(f"Thread {threading.current_thread().name}: No more pages after token {token}")

            self.threads_queue.task_done()
            time.sleep(random.uniform(0.01, 0.99))
            logging.info(f"Thread {threading.current_thread().name}: Finished processing token {token}")

    def get_all_threads(self):
        """Fetches all threads using multiple threads."""
        logging.info("Starting multi-threaded thread fetching.")

        # **Explicitly fetch the first page in the main thread**
        initial_threads, next_page_token = self._get_threads_chunk()

        with self.lock:
            self.all_threads.extend(initial_threads)

        # give each thread a not-None token to start working with
        for _ in range(self.num_threads):
            self.threads_queue.put(next_page_token)
            # ignore fetched threads, because we need tokens only
            _, next_page_token = self._get_threads_chunk(token=next_page_token)

        # **Add the initial next_page_token to the queue *before* starting threads**
        if next_page_token:
            self.threads_queue.put(next_page_token)
            logging.info(f"Added initial next_page_token to queue: {next_page_token}")
        else:
            logging.info("No initial next_page_token found.")

        logging.info(f"threads queue: " + str(self.threads_queue.qsize()))

        # Create and start worker threads
        threads = []
        for i in range(self.num_threads):
            thread = threading.Thread(target=self._worker, name=f"Thread-{i + 1}")
            logging.info(f"Created thread: Thread-{i + 1}")
            thread.daemon = True  # Daemonize threads so they exit when the main thread exits
            threads.append(thread)

        for t in threads:
            t.start()

        # Wait for all tasks to be processed
        self.threads_queue.join()

        # Signal threads to terminate by adding sentinel values to the queue
        for _ in range(self.num_threads):
            self.threads_queue.put(None)

        # Wait for all threads to finish
        for thread in threads:
            thread.join()

        logging.info("Multi-threaded thread fetching complete.")
        return self.all_threads
