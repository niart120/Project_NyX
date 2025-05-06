import requests
from nyxpy.framework.core.api.bluesky_notification import BlueskyNotification
from unittest.mock import patch, Mock, call

def test_bluesky_notification_authentication():
    with patch("requests.post") as mock_post:
        # Mock the authentication response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "accessJwt": "mock_access_token",
            "refreshJwt": "mock_refresh_token"
        }
        mock_post.return_value = mock_response

        notifier = BlueskyNotification("test_user", "test_password")

        assert notifier.access_token == "mock_access_token"
        assert notifier.refresh_token == "mock_refresh_token"
        mock_post.assert_called_once_with(
            "https://bsky.social/xrpc/com.atproto.server.createSession",
            json={
                "identifier": "test_user",
                "password": "test_password"
            },
            timeout=5
        )

def test_bluesky_notification_notify():
    with patch("requests.post") as mock_post:
        # Mock responses
        auth_response = Mock()
        auth_response.status_code = 200
        auth_response.raise_for_status.return_value = None
        auth_response.json.return_value = {
            "accessJwt": "mock_access_token",
            "refreshJwt": "mock_refresh_token"
        }
        
        post_response = Mock()
        post_response.status_code = 200
        post_response.raise_for_status.return_value = None
        
        # Set up side effects - first call returns auth_response, second call returns post_response
        mock_post.side_effect = [auth_response, post_response]

        notifier = BlueskyNotification("test_user", "test_password")
        notifier.notify("Test message")

        # Verify all calls were made correctly
        assert mock_post.call_count == 2
        
        # Check authentication call
        assert mock_post.call_args_list[0] == call(
            "https://bsky.social/xrpc/com.atproto.server.createSession",
            json={
                "identifier": "test_user",
                "password": "test_password"
            },
            timeout=5
        )
        
        # Check post creation call
        assert mock_post.call_args_list[1] == call(
            "https://bsky.social/xrpc/com.atproto.repo.createRecord",
            json={
                "collection": "app.bsky.feed.post",
                "record": {
                    "text": "Test message",
                    "createdAt": "2025-05-06T00:00:00.000Z"
                }
            },
            headers={"Authorization": "Bearer mock_access_token"},
            timeout=5
        )

def test_token_refresh_on_401():
    with patch("requests.post") as mock_post:
        # Authentication response
        auth_response = Mock()
        auth_response.status_code = 200
        auth_response.raise_for_status.return_value = None
        auth_response.json.return_value = {
            "accessJwt": "mock_access_token",
            "refreshJwt": "mock_refresh_token"
        }
        
        # First post attempt - 401 error
        mock_error_response = Mock()
        mock_error_response.status_code = 401
        
        # 重要：HTTPErrorオブジェクトを正しく設定
        http_error = requests.exceptions.HTTPError("401 Error")
        http_error.response = mock_error_response
        
        error_response = Mock()
        error_response.raise_for_status.side_effect = http_error
        
        # Refresh token response
        refresh_response = Mock()
        refresh_response.status_code = 200
        refresh_response.raise_for_status.return_value = None
        refresh_response.json.return_value = {
            "accessJwt": "new_access_token",
            "refreshJwt": "mock_refresh_token"
        }
        
        # Successful post after refresh
        success_response = Mock()
        success_response.status_code = 200
        success_response.raise_for_status.return_value = None
        
        # Set up side effects sequence
        mock_post.side_effect = [auth_response, error_response, refresh_response, success_response]
        
        notifier = BlueskyNotification("test_user", "test_password")
        notifier.notify("Test message")
        
        # Should have 4 calls: auth, failed post, refresh, successful post
        assert mock_post.call_count == 4
        
        # Check token refresh call
        assert mock_post.call_args_list[2] == call(
            "https://bsky.social/xrpc/com.atproto.server.refreshSession",
            json={
                "refreshJwt": "mock_refresh_token"
            },
            timeout=5
        )
        
        # Check final post with new token
        assert mock_post.call_args_list[3] == call(
            "https://bsky.social/xrpc/com.atproto.repo.createRecord",
            json={
                "collection": "app.bsky.feed.post",
                "record": {
                    "text": "Test message",
                    "createdAt": "2025-05-06T00:00:00.000Z"
                }
            },
            headers={"Authorization": "Bearer new_access_token"},
            timeout=5
        )
