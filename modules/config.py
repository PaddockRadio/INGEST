import configparser
import os

def load_config():
    config_path = os.path.expanduser('~/INGEST/config.ini')
    config = configparser.ConfigParser()
    config.read(config_path)
    return config
