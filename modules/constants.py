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
