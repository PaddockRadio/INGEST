# ============================================
# Paddock Media Ingest Repair + Rebuild Script
# Version: 0.81
# ============================================

import os
import subprocess
import logging
from textwrap import dedent

# ---------- Paths ----------
CONFIG_PATH = os.path.expanduser("~/INGEST/config.ini")
FOLDERS = [
    "~/INGEST/Temp",
    "~/INGEST/Working",
    "~/INGEST/Publish",
    "~/INGEST/SFTP",
    "~/INGEST/Logs",
    "~/INGEST/Archive",
    "~/INGEST/modules",
    "~/INGEST/tests" # Added tests directory
]

# ---------- Required Dependencies ----------
REQUIRED_PACKAGES = [
    "python-docx", "mutagen", "pymupdf", "beautifulsoup4",
    "lxml", "paramiko", "Pillow", "requests"
]

# ---------- Config File ----------
config_ini = dedent("""\
[ADMIN]
ADMIN_EMAIL = paddockradiolive@gmail.com

[EMAIL]
IMAP_SERVER = imap.gmail.com
EMAIL_ADDRESS = kbpaddockradio@gmail.com
EMAIL_PASSWORD = 
LABEL_PROCESSED = Processed
LABEL_PENDING = Pending
LABEL_ERROR = Error
LABEL_UNMATCHED = Unmatched
WHITELIST =
SEARCH_TERMS = UNSEEN

[AUDIO PROCESSING]
OUTPUT_FORMAT = MP3
OUTPUT_BITRATE = 128k
ID3_GENRE_OVERWRITE = Featured

[SFTP]
SFTP_HOST = 
SFTP_PORT = 
SFTP_USERNAME = 
SFTP_PASSWORD = 
SFTP_REMOTE_FOLDER = /upload/inbox/Featured/

[WORDPRESS]
WP_URL = 
WP_USERNAME = 
# Application Password generated from WordPress admin (Users -> Your Profile -> Application Passwords)
WP_APP_PASSWORD =
""")

# ---------- Module Strings ----------
module_constants_code = dedent("""\
import os
LOG_FOLDER = os.path.expanduser('~/INGEST/Logs')
LOG_FILE = os.path.join(LOG_FOLDER, 'ingest.log')
FOLDER_PATHS = {
    "temp": os.path.expanduser("~/INGEST/Temp"),
    "working": os.path.expanduser("~/INGEST/Working"),
    "publish": os.path.expanduser("~/INGEST/Publish"),
    "sftp": os.path.expanduser("~/INGEST/SFTP"),
    "logs": LOG_FOLDER,
    "archive": os.path.expanduser("~/INGEST/Archive")
}
""")

module_logs_code = dedent("""\
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
""")

module_config_code = dedent("""\
import configparser
import os

def load_config():
    config_path = os.path.expanduser('~/INGEST/config.ini')
    config = configparser.ConfigParser()
    config.read(config_path)
    return config
""")

module_file_utils_code = dedent("""\
import os

def enforce_storage_limits(target_folder):
    total_size = 0
    for dirpath, _, filenames in os.walk(target_folder):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.isfile(fp):
                total_size += os.path.getsize(fp)
    total_gb = total_size / (1024**3)
    if total_gb > 8:
        print(f"[!] Folder size exceeds 8GB: {total_gb:.2f} GB")
    else:
        print(f"[+] Current folder usage for {target_folder}: {total_gb:.2f} GB (OK)")
""")

module_sanitation_utils_code = dedent("""\
import re

def sanitize_filename(name):
    name = re.sub(r'[\\/*?:"<>|]', "_", name)
    name = re.sub(r'\\s+', '_', name)
    return name.strip('_')

def clean_text(text):
    lines = text.splitlines()
    clean = []
    skip_patterns = ['Forwarded message', 'From:', 'Date:', 'Subject:', 'To:']
    for line in lines:
        if not any(line.startswith(p) for p in skip_patterns):
            clean.append(line)
    return '\\n'.join(clean)
""")

module_email_utils_code = dedent("""\
import imaplib
import email
import os
import logging
from email.header import decode_header
from modules.constants import FOLDER_PATHS
from modules.sanitation_utils import sanitize_filename, clean_text

def decode_subject(subject_raw):
    decoded = decode_header(subject_raw)
    return ''.join(
        part.decode(enc or 'utf-8') if isinstance(part, bytes) else part
        for part, enc in decoded
    ).replace("Fwd: ", "").strip()

def extract_email_body(message):
    for part in message.walk():
        if part.get_content_type() == "text/plain":
            return part.get_payload(decode=True).decode(errors="ignore")
    return ""

def fetch_emails_and_extract(config):
    results = []
    user = config['EMAIL']['EMAIL_ADDRESS']
    password = config['EMAIL']['EMAIL_PASSWORD']
    server = config['EMAIL']['IMAP_SERVER']
    try:
        mail = imaplib.IMAP4_SSL(server)
        mail.login(user, password)
        mail.select("inbox")
        _, messages = mail.search(None, config['EMAIL'].get('SEARCH_TERMS', 'UNSEEN'))

        for num in messages[0].split():
            _, data = mail.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(data[0][1])
            subject = decode_subject(msg.get("Subject") or "No Subject")
            folder_name = sanitize_filename(subject)
            folder = os.path.join(FOLDER_PATHS['working'], folder_name)
            os.makedirs(folder, exist_ok=True)

            body = extract_email_body(msg)
            with open(os.path.join(folder, "body.txt"), "w") as f:
                f.write(clean_text(body))

            has_audio, has_doc = False, False
            art_count = 1

            for part in msg.walk():
                filename = part.get_filename()
                if filename:
                    filename = decode_subject(filename)
                    ext = os.path.splitext(filename)[1].lower()
                    content = part.get_payload(decode=True)
                    clean_name = sanitize_filename(filename)

                    if ext in [".jpg", ".jpeg", ".png"]:
                        clean_name = f"album_art{art_count}{ext}"
                        art_count += 1

                    filepath = os.path.join(folder, clean_name)
                    with open(filepath, "wb") as f:
                        f.write(content)

                    if ext in ('.mp3', '.wav', '.flac', '.aac', '.m4a'):
                        has_audio = True
                    elif ext in ('.docx', '.pdf', '.txt'):
                        has_doc = True

            if has_audio and has_doc:
                results.append({'subject': subject, 'folder': folder})
            mail.store(num, '+FLAGS', '\\Seen')

        mail.logout()
    except Exception as e:
        logging.error(f"Email fetch failed: {e}")
    return results
""")

module_doc_utils_code = dedent("""\
import os
import logging
from modules.sanitation_utils import clean_text

def convert_documents_to_text(folder):
    try:
        for file in os.listdir(folder):
            path = os.path.join(folder, file)
            text = ""
            if file.endswith(".docx"):
                from docx import Document
                doc = Document(path)
                text = "\\n".join([p.text for p in doc.paragraphs])
            elif file.endswith(".pdf"):
                import fitz
                doc = fitz.open(path)
                text = "\\n".join([page.get_text() for page in doc])
            elif file.endswith(".txt"):
                with open(path, "r") as f:
                    text = f.read()
            if text.strip():
                with open(os.path.join(folder, "publish.txt"), "w") as f:
                    f.write(clean_text(text.strip()))
                break
    except Exception as e:
        logging.warning(f"Document conversion failed: {e}")
""")

module_audio_utils_code = dedent("""\
import os
import logging
import subprocess
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TCON, APIC
from modules.constants import FOLDER_PATHS

def process_audio_files(folder, config, processed_list):
    genre = config['AUDIO PROCESSING']['ID3_GENRE_OVERWRITE']
    bitrate = config['AUDIO PROCESSING']['OUTPUT_BITRATE']
    for file in os.listdir(folder):
        if file.lower().endswith(('.mp3', '.wav', '.flac', '.aac', '.m4a')):
            original = os.path.join(folder, file)
            base = os.path.splitext(file)[0]
            out_path = os.path.join(FOLDER_PATHS['sftp'], f"{base}.mp3")
            try:
                subprocess.run([
                    "ffmpeg", "-y", "-i", original, "-codec:a", "libmp3lame",
                    "-b:a", bitrate, out_path
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

                audio = MP3(out_path, ID3=ID3)
                if audio.tags is None:
                    audio.add_tags()
                else:
                    audio.tags.clear()

                artist, title = base.split("-", 1) if "-" in base else (base, "")
                audio.tags.add(TPE1(encoding=3, text=artist.strip()))
                audio.tags.add(TIT2(encoding=3, text=title.strip()))
                audio.tags.add(TCON(encoding=3, text=genre))

                for art_file in os.listdir(folder):
                    if art_file.startswith("album_art") and art_file.endswith(('.jpg', '.jpeg', '.png')):
                        art_path = os.path.join(folder, art_file)
                        with open(art_path, 'rb') as img:
                            audio.tags.add(APIC(
                                encoding=3,
                                mime="image/jpeg",
                                type=3,
                                desc="Cover",
                                data=img.read()
                            ))
                        break
                audio.save()
                processed_list.append(f"{base}.mp3")
                logging.info(f"Processed & tagged audio: {file}")
                return True
            except Exception as e:
                logging.error(f"Audio processing failed for {file}: {e}")
    return False
""")

module_sftp_utils_code = dedent("""\
import os
import logging
import paramiko
from modules.constants import FOLDER_PATHS
from modules.config import load_config

def upload_sftp_files(file_list):
    config = load_config()
    host = config['SFTP']['SFTP_HOST']
    port = int(config['SFTP']['SFTP_PORT'])
    username = config['SFTP']['SFTP_USERNAME']
    password = config['SFTP']['SFTP_PASSWORD']
    remote_path = config['SFTP']['SFTP_REMOTE_FOLDER']
    local_folder = FOLDER_PATHS['sftp']

    try:
        transport = paramiko.Transport((host, port))
        transport.connect(username=username, password=password)
        sftp = paramiko.SFTPClient.from_transport(transport)
        uploaded = 0
        failed = 0
        for filename in file_list:
            local_path = os.path.join(local_folder, filename)
            remote_filename = filename.replace(" ", "_")
            remote_fullpath = os.path.join(remote_path, remote_filename)
            if not os.path.isfile(local_path):
                logging.error(f"Missing for upload: {local_path}")
                failed += 1
                continue
            try:
                sftp.put(local_path, remote_fullpath)
                uploaded += 1
            except Exception as e:
                logging.error(f"SFTP upload failed for {filename}: {e}")
                failed += 1
        sftp.close()
        transport.close()
        logging.info(f"SFTP Upload Summary: {uploaded} success, {failed} failed")
    except Exception as e:
        logging.error(f"SFTP connection error: {e}")
""")

module_wordpress_utils_code = dedent("""\
import os
import logging
import requests
from requests.auth import HTTPBasicAuth
from modules.config import load_config
from modules.constants import FOLDER_PATHS

def post_to_wordpress(folder, job_id):
    \"\"\"
    Creates a new draft post on WordPress using the REST API.

    Args:
        folder (str): The path to the folder containing the '{job_id}.txt' file.
        job_id (str): The identifier for the job, used for the post title
                      and the content filename.

    Returns:
        bool: True if the post was created successfully, False otherwise.
    \"\"\"
    config = load_config()
    wp_url = config['WORDPRESS']['WP_URL']
    wp_user = config['WORDPRESS']['WP_USERNAME']
    wp_app_password = config['WORDPRESS']['WP_APP_PASSWORD']

    text_file = os.path.join(folder, f"{job_id}.txt")
    if not os.path.isfile(text_file):
        logging.warning(f"No publish file for {job_id}")
        return False

    with open(text_file, 'r') as f:
        content = f.read()

    api_url = f"{wp_url.rstrip('/')}/wp-json/wp/v2/posts"
    data = {
        'title': job_id.replace("_", " "),
        'content': content,
        'status': 'draft'
    }
    auth = HTTPBasicAuth(wp_user, wp_app_password)

    try:
        response = requests.post(api_url, data=data, auth=auth, timeout=30)
        response.raise_for_status()
        logging.info(f"WordPress post created via REST API: {job_id}, Status: {response.status_code}")
        return True
    except requests.exceptions.HTTPError as e:
        logging.error(f"WordPress REST API post failed for {job_id}: HTTP Error: {e.response.status_code} - {e.response.text}")
        return False
    except requests.exceptions.RequestException as e:
        logging.error(f"WordPress REST API post failed for {job_id}: {e}")
        return False
""")

module_test_wordpress_utils_code = dedent("""\
import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
import logging

# Adjust the import path based on your project structure if necessary
from modules.wordpress_utils import post_to_wordpress
from modules.config import load_config # To be mocked
from requests.exceptions import HTTPError, RequestException

# Suppress logging output during tests for cleaner test results
logging.disable(logging.CRITICAL)

class TestWordPressUtils(unittest.TestCase):

    @patch('modules.wordpress_utils.load_config')
    @patch('modules.wordpress_utils.requests.post')
    @patch('modules.wordpress_utils.os.path.isfile')
    @patch('modules.wordpress_utils.open', new_callable=mock_open, read_data="Test content")
    def test_post_to_wordpress_success(self, mock_file_open, mock_isfile, mock_requests_post, mock_load_config):
        # Setup mock config
        mock_load_config.return_value = {
            'WORDPRESS': {
                'WP_URL': 'http://example.com',
                'WP_USERNAME': 'testuser',
                'WP_APP_PASSWORD': 'testpassword'
            }
        }

        # Mock os.path.isfile to return True (file exists)
        mock_isfile.return_value = True

        # Mock requests.post response for success
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.raise_for_status = MagicMock() # Ensure it doesn't raise for success
        mock_requests_post.return_value = mock_response

        result = post_to_wordpress('/fake/folder', 'test_job_id')

        self.assertTrue(result)
        mock_requests_post.assert_called_once()
        args, kwargs = mock_requests_post.call_args
        self.assertEqual(args[0], 'http://example.com/wp-json/wp/v2/posts')
        self.assertEqual(kwargs['data']['title'], 'test job id')
        self.assertEqual(kwargs['data']['content'], 'Test content')
        self.assertEqual(kwargs['data']['status'], 'draft')
        self.assertEqual(kwargs['auth'].username, 'testuser')
        self.assertEqual(kwargs['auth'].password, 'testpassword')

    @patch('modules.wordpress_utils.load_config')
    @patch('modules.wordpress_utils.os.path.isfile')
    def test_post_to_wordpress_file_not_found(self, mock_isfile, mock_load_config):
        # Setup mock config
        mock_load_config.return_value = {
            'WORDPRESS': {
                'WP_URL': 'http://example.com',
                'WP_USERNAME': 'testuser',
                'WP_APP_PASSWORD': 'testpassword'
            }
        }
        # Mock os.path.isfile to return False (file does not exist)
        mock_isfile.return_value = False

        result = post_to_wordpress('/fake/folder', 'test_job_id')
        self.assertFalse(result)

    @patch('modules.wordpress_utils.load_config')
    @patch('modules.wordpress_utils.requests.post')
    @patch('modules.wordpress_utils.os.path.isfile')
    @patch('modules.wordpress_utils.open', new_callable=mock_open, read_data="Test content")
    def test_post_to_wordpress_http_error(self, mock_file_open, mock_isfile, mock_requests_post, mock_load_config):
        # Setup mock config
        mock_load_config.return_value = {
            'WORDPRESS': {
                'WP_URL': 'http://example.com',
                'WP_USERNAME': 'testuser',
                'WP_APP_PASSWORD': 'testpassword'
            }
        }
        mock_isfile.return_value = True

        # Mock requests.post to raise HTTPError
        mock_response = MagicMock()
        mock_response.status_code = 401 # Example: Unauthorized
        mock_response.text = "Client error: Unauthorized"
        http_error = HTTPError(response=mock_response)
        mock_response.raise_for_status = MagicMock(side_effect=http_error)
        mock_requests_post.return_value = mock_response

        result = post_to_wordpress('/fake/folder', 'test_job_id_http_error')
        self.assertFalse(result)
        mock_requests_post.assert_called_once()

    @patch('modules.wordpress_utils.load_config')
    @patch('modules.wordpress_utils.requests.post')
    @patch('modules.wordpress_utils.os.path.isfile')
    @patch('modules.wordpress_utils.open', new_callable=mock_open, read_data="Test content")
    def test_post_to_wordpress_request_exception(self, mock_file_open, mock_isfile, mock_requests_post, mock_load_config):
        # Setup mock config
        mock_load_config.return_value = {
            'WORDPRESS': {
                'WP_URL': 'http://example.com',
                'WP_USERNAME': 'testuser',
                'WP_APP_PASSWORD': 'testpassword'
            }
        }
        mock_isfile.return_value = True

        # Mock requests.post to raise RequestException
        mock_requests_post.side_effect = RequestException("Connection timed out")

        result = post_to_wordpress('/fake/folder', 'test_job_id_req_exception')
        self.assertFalse(result)
        mock_requests_post.assert_called_once()

if __name__ == '__main__':
    unittest.main()
""")

module_ingest_code = dedent("""\
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
        process_audio_files(folder, config, processed_audio_jobs) # Changed this line
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
""")

# ---------- Module Writer ----------
# Modified to write_file(base_dir, filename, code)
def write_file(base_dir, filename, code):
    # Ensure parent directory of base_dir itself is created if base_dir is like '~/INGEST/modules'
    # os.makedirs(os.path.expanduser(base_dir), exist_ok=True) # This line is actually not needed if create_folders() handles all base_dirs
    path = os.path.join(os.path.expanduser(base_dir), filename)
    # Ensure parent directory of the file itself is created
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(code)
    print(f"[+] Rewritten: {path}")

def write_all_modules():
    # MODULES_DIR is "~/INGEST/modules"
    # CONFIG_PATH is "~/INGEST/config.ini"
    # ingest.py is in "~/INGEST/ingest.py"
    # tests dir is "~/INGEST/tests"

    modules_base_dir = "~/INGEST/modules"
    ingest_base_dir = "~/INGEST"
    tests_base_dir = "~/INGEST/tests"

    write_file(modules_base_dir, "constants.py", module_constants_code)
    write_file(modules_base_dir, "logs.py", module_logs_code)
    write_file(modules_base_dir, "config.py", module_config_code)
    write_file(modules_base_dir, "file_utils.py", module_file_utils_code)
    write_file(modules_base_dir, "sanitation_utils.py", module_sanitation_utils_code)
    write_file(modules_base_dir, "email_utils.py", module_email_utils_code)
    write_file(modules_base_dir, "doc_utils.py", module_doc_utils_code)
    write_file(modules_base_dir, "audio_utils.py", module_audio_utils_code)
    write_file(modules_base_dir, "sftp_utils.py", module_sftp_utils_code)
    write_file(modules_base_dir, "wordpress_utils.py", module_wordpress_utils_code)

    # Write ingest.py
    write_file(ingest_base_dir, "ingest.py", module_ingest_code)
    print("[+] Rewritten: ingest.py (using write_file)") # Explicitly confirming ingest.py rewrite

    # Write the new test file
    write_file(tests_base_dir, "test_wordpress_utils.py", module_test_wordpress_utils_code)


# ---------- Install Steps ----------
def create_folders():
    for folder_path_str in FOLDERS: # folder_path_str since 'folder' is used as var name in some module codes
        path = os.path.expanduser(folder_path_str)
        os.makedirs(path, exist_ok=True)
        print(f"[+] Ensured folder exists: {path}")

def install_dependencies():
    for package in REQUIRED_PACKAGES:
        try:
            # Attempt to import the top-level module name used by the package
            # This is a heuristic and might not be perfect for all package names
            import_name = package.replace('-', '_').split('.')[0]
            __import__(import_name)
        except ImportError:
            print(f"[!] Missing package '{package}' (tried importing '{import_name}') - installing...")
            subprocess.run(["pip3", "install", package], check=True) # Added check=True

def write_config():
    # CONFIG_PATH is already expanded
    with open(CONFIG_PATH, "w") as f:
        f.write(config_ini)
    print(f"[+] Rewritten: {CONFIG_PATH}")


# ---------- Main ----------
def main():
    log_filename = os.path.expanduser("~/INGEST/repair_patch.log") # Define log_filename
    # Simple file logging for the repair script itself
    logging.basicConfig(filename=log_filename,
                        level=logging.INFO,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    print(f"[+] Logging repair script actions to {log_filename}")
    logging.info("Repair script started.")

    try:
        create_folders()
        logging.info("Folder creation step completed.")

        install_dependencies()
        logging.info("Dependency installation step completed.")

        write_config()
        logging.info("Config file writing step completed.")

        write_all_modules()
        logging.info("Module and script writing step completed.")

        print("[?] All essential scripts and modules rebuilt.")
        logging.info("All essential scripts and modules rebuilt.")

        print("[?] Repair patch complete.")
        logging.info("Repair patch complete.")

    except Exception as e:
        error_message = f"An error occurred during the repair process: {e}"
        print(f"[!] {error_message}")
        logging.error(error_message)
        # Optionally, re-raise the exception if you want the script to exit with an error code
        # raise

if __name__ == "__main__":
    main()
