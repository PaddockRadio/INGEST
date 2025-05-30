import logging
import os
from modules.constants import LOG_FILE, LOG_FOLDER

def setup_logging():
    os.makedirs(LOG_FOLDER, exist_ok=True)
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logging.getLogger().addHandler(logging.StreamHandler())
    logging.info("Logging system initialized.")
