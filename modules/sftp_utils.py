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
