# ============================================
# Paddock Media Ingest Repair + Rebuild Script
# Version: 0.81
# ============================================

import os
import subprocess
from textwrap import dedent

# ---------- Paths ----------
CONFIG_PATH = os.path.expanduser("~/INGEST/config.ini")
MODULES_DIR = os.path.expanduser("~/INGEST/modules")
FOLDERS = [
    "~/INGEST/Temp",
    "~/INGEST/Working",
    "~/INGEST/Publish",
    "~/INGEST/SFTP",
    "~/INGEST/Logs",
    "~/INGEST/Archive",
    "~/INGEST/modules"
]

# ---------- Required Dependencies ----------
REQUIRED_PACKAGES = [
    "python-docx", "mutagen", "python_wordpress_xmlrpc",
    "pymupdf", "beautifulsoup4", "lxml", "paramiko", "Pillow", "requests"
]

# ---------- Config File ----------
config_ini = dedent("""\
[ADMIN]
ADMIN_EMAIL = paddockradiolive@gmail.com

[EMAIL]
IMAP_SERVER = imap.gmail.com
EMAIL_ADDRESS = kbpaddockradio@gmail.com
EMAIL_PASSWORD = mrkh easg blfb vsbh
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
SFTP_HOST = 144.126.215.156
SFTP_PORT = 2022
SFTP_USERNAME = pwuser
SFTP_PASSWORD = prwifi01
SFTP_REMOTE_FOLDER = /upload/inbox/Featured/

[WORDPRESS]
WP_URL = https://paddockradio.net/xmlrpc.php
WP_USERNAME = paddockradiolive@gmail.com
WP_PASSWORD = prwifi01
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

# ---------- file_utils.py ----------
module_file_utils_code = dedent("""\
import os
import shutil

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

# ---------- sanitation_utils.py ----------
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

# ---------- email_utils.py ----------
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

# ---------- doc_utils.py ----------
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

# ---------- audio_utils.py ----------
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

                # Embed album art if available
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

# ---------- sftp_utils.py ----------
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

# ---------- wordpress_utils.py ----------
module_wordpress_utils_code = dedent("""\
import os
import logging
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import NewPost
from modules.config import load_config
from modules.constants import FOLDER_PATHS

def post_to_wordpress(folder, job_id):
    config = load_config()
    wp_url = config['WORDPRESS']['WP_URL']
    wp_user = config['WORDPRESS']['WP_USERNAME']
    wp_pass = config['WORDPRESS']['WP_PASSWORD']

    text_file = os.path.join(folder, f"{job_id}.txt")
    if not os.path.isfile(text_file):
        logging.warning(f"No publish file for {job_id}")
        return False

    with open(text_file, 'r') as f:
        content = f.read()

    try:
        client = Client(wp_url, wp_user, wp_pass)
        post = WordPressPost()
        post.title = job_id.replace("_", " ")
        post.content = content
        post.post_status = 'draft'
        client.call(NewPost(post))
        logging.info(f"WordPress post created: {job_id}")
        return True
    except Exception as e:
        logging.error(f"WordPress post failed for {job_id}: {e}")
        return False
""")

# ---------- ingest.py ----------
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
        audio_ok = process_audio_files(folder, config, processed_audio_jobs)
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
def write_module(filename, code):
    path = os.path.join(MODULES_DIR, filename)
    with open(path, "w") as f:
        f.write(code)
    print(f"[+] Rewritten: {filename}")

def write_all_modules():
    write_module("constants.py", module_constants_code)
    write_module("logs.py", module_logs_code)
    write_module("config.py", module_config_code)
    write_module("file_utils.py", module_file_utils_code)
    write_module("sanitation_utils.py", module_sanitation_utils_code)
    write_module("email_utils.py", module_email_utils_code)
    write_module("doc_utils.py", module_doc_utils_code)
    write_module("audio_utils.py", module_audio_utils_code)
    write_module("sftp_utils.py", module_sftp_utils_code)
    write_module("wordpress_utils.py", module_wordpress_utils_code)
    with open(os.path.expanduser("~/INGEST/ingest.py"), "w") as f:
        f.write(module_ingest_code)
    print("[+] Rewritten: ingest.py")

# ---------- Install Steps ----------
def create_folders():
    for folder in FOLDERS:
        path = os.path.expanduser(folder)
        os.makedirs(path, exist_ok=True)
        print(f"[+] Ensured folder exists: {path}")

def install_dependencies():
    for package in REQUIRED_PACKAGES:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            print(f"[!] Missing package '{package}' - installing...")
            subprocess.run(["pip3", "install", package])

def write_config():
    with open(CONFIG_PATH, "w") as f:
        f.write(config_ini)
    print("[+] Rewritten: config.ini")

# ---------- Main ----------
def main():
    print("[+] Logging started in repair_patch.log")
    create_folders()
    install_dependencies()
    write_config()
    write_all_modules()
    print("[?] All essential scripts and modules rebuilt.")
    print("[?] Repair patch complete.")

if __name__ == "__main__":
    main()
