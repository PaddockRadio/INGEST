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
