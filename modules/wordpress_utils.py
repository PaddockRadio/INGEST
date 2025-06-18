import os
import logging
import requests
from requests.auth import HTTPBasicAuth
from modules.config import load_config
from modules.constants import FOLDER_PATHS

def post_to_wordpress(folder, job_id):
    """
    Creates a new draft post on WordPress using the REST API.

    Args:
        folder (str): The path to the folder containing the '{job_id}.txt' file.
        job_id (str): The identifier for the job, used for the post title
                      and the content filename.

    Returns:
        bool: True if the post was created successfully, False otherwise.
    """
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
        response = requests.post(api_url, data=data, auth=auth, timeout=30) # Added timeout
        response.raise_for_status()  # This will raise an HTTPError for bad responses (4xx or 5xx)
        logging.info(f"WordPress post created via REST API: {job_id}, Status: {response.status_code}")
        return True
    except requests.exceptions.HTTPError as e:
        logging.error(f"WordPress REST API post failed for {job_id}: HTTP Error: {e.response.status_code} - {e.response.text}")
        return False
    except requests.exceptions.RequestException as e:
        logging.error(f"WordPress REST API post failed for {job_id}: {e}")
        return False
