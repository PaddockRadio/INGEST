import os
import time
import logging
from modules.logs import setup_logging
from modules.config import load_config
from modules.constants import FOLDER_PATHS
from modules.file_utils import enforce_storage_limits
from modules.email_utils import fetch_emails_and_extract
from modules.doc_utils import convert_documents_to_text
from modules.audio_utils import process_audio_files
from modules.sftp_utils import upload_sftp_files
from modules.wordpress_utils import post_to_wordpress

def main():
    setup_logging()
    logging.info("Ingest script started.")
    start = time.time()
    config = load_config()
    processed_audio_jobs = []
    wp_success = []

    email_results = fetch_emails_and_extract(config)
    logging.info(f"Emails found: {len(email_results)}")

    for result in email_results:
        folder = result['folder']
        subject = result['subject']
        logging.info(f"Processing: {subject}")
        convert_documents_to_text(folder)
        process_audio_files(folder, config, processed_audio_jobs)
        job_id = os.path.basename(folder)
        publish_file = os.path.join(folder, "publish.txt")
        body_file = os.path.join(folder, "body.txt")
        if not os.path.exists(publish_file):
            if os.path.exists(body_file):
                os.rename(body_file, os.path.join(folder, f"{job_id}.txt"))
            else:
                open(os.path.join(folder, f"{job_id}.txt"), "w").close()
        else:
            os.rename(publish_file, os.path.join(folder, f"{job_id}.txt"))

    if processed_audio_jobs:
        upload_sftp_files(processed_audio_jobs)
        for job_file in processed_audio_jobs:
            job_id = os.path.splitext(job_file)[0]
            folder = os.path.join(FOLDER_PATHS['working'], job_id)
            success = post_to_wordpress(folder, job_id)
            if success:
                wp_success.append(job_id)

    enforce_storage_limits(FOLDER_PATHS['publish'])
    elapsed = time.time() - start
    logging.info("=== Ingest Summary ===")
    logging.info(f"Total Jobs: {len(email_results)}")
    logging.info(f"Audio Processed: {len(processed_audio_jobs)}")
    logging.info(f"WordPress Posted: {len(wp_success)}")
    logging.info(f"Elapsed Time: {elapsed:.2f} seconds")
    logging.info("Ingestion process completed.")

if __name__ == "__main__":
    main()
