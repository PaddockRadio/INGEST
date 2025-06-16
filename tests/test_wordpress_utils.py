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
        # Or, more directly if raise_for_status is called inside the try block:
        # mock_requests_post.side_effect = HTTPError(response=mock_response)


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
