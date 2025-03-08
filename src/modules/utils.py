import os
import logging

class Utils:
    @classmethod
    def prepare_file_structure(cls):
        os.makedirs("./output", exist_ok=True)
        os.makedirs("./output/attachments", exist_ok=True)
        os.makedirs("./credentials", exist_ok=True)
        logging.info("Set up directory structure.")
