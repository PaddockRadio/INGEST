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
            mail.store(num, '+FLAGS', '\Seen')

        mail.logout()
    except Exception as e:
        logging.error(f"Email fetch failed: {e}")
    return results
