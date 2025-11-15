"""
TeamSpeak WebQuery client.

Handles HTTP communication with TeamSpeak 3 (3.13+) and TeamSpeak 6 WebQuery API.

Copyright (C) 2025 Metroseksuaali
Licensed under GNU AGPL v3.0 - see LICENSE file for details.
"""

import logging
import time
from typing import Dict, List, Optional

import httpx

from ts_activity_bot.config import TeamspeakConfig

logger = logging.getLogger(__name__)


class TeamSpeakQueryClient:
    """Client for TeamSpeak 3/6 WebQuery HTTP API."""

    def __init__(self, config: TeamspeakConfig):
        """
        Initialize WebQuery client.

        Args:
            config: TeamSpeak configuration
        """
        self.config = config
        self.base_url = config.base_url
        self.api_key = config.api_key
        self.virtual_server_id = config.virtual_server_id
        self.timeout = config.timeout
        self.verify_ssl = config.verify_ssl
        self.include_query_clients = config.include_query_clients

        # Debug: Log API key info (NOT the actual key for security)
        logger.info(f"API Key length: {len(self.api_key)} chars, starts with: {self.api_key[:5]}...")

        # Create HTTP client with connection pooling
        self.client = httpx.Client(
            timeout=self.timeout,
            verify=self.verify_ssl,
            headers={
                'x-api-key': self.api_key,
                'User-Agent': 'TS6-Activity-Bot/1.0'
            }
        )

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close HTTP client."""
        self.close()

    def close(self) -> None:
        """Close HTTP client and cleanup resources."""
        self.client.close()

    def _make_request(self, endpoint: str, params: Optional[Dict[str, str]] = None) -> Dict:
        """
        Make HTTP request to WebQuery API.

        Args:
            endpoint: API endpoint (e.g., 'clientlist')
            params: Optional query parameters

        Returns:
            dict: Response body

        Raises:
            httpx.HTTPError: On network/HTTP errors
            ValueError: On invalid API response
        """
        url = f"{self.base_url}/{self.virtual_server_id}/{endpoint}"

        logger.debug(f"WebQuery request: GET {url}")

        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()

            # Parse JSON response
            data = response.json()

            # Check for TS6 API response structure
            if isinstance(data, dict) and 'status' in data:
                # TS6/TS3 WebQuery format: {"status": {...}, "body": [...]}
                status = data.get('status', {})
                if status.get('code') != 0:
                    error_msg = status.get('message', 'Unknown error')
                    raise ValueError(f"TeamSpeak API error: {error_msg}")

                return data.get('body', [])

            # Fallback: return raw data if format is different
            logger.warning("Unexpected API response format, returning raw data")
            return data

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            raise

        except httpx.RequestError as e:
            logger.error(f"Network error: {e}")
            raise

        except ValueError as e:
            logger.error(f"API response error: {e}")
            raise

    def fetch_clientlist(self) -> List[Dict[str, any]]:
        """
        Fetch list of currently connected clients.

        Returns:
            list: List of client dictionaries with fields:
                - clid (int): Client ID
                - cid (int): Channel ID
                - client_database_id (int): Database ID
                - client_nickname (str): Nickname
                - client_unique_identifier (str): Unique identifier
                - client_idle_time (int): Idle time in milliseconds
                - client_type (int): 0 = normal user, 1 = query client

        Example response:
            [
                {
                    "clid": 5,
                    "cid": 1,
                    "client_database_id": 10,
                    "client_nickname": "User123",
                    "client_unique_identifier": "abc123def456==",
                    "client_idle_time": 5000,
                    "client_type": 0
                }
            ]
        """
        try:
            # Request with additional info flags
            # -uid = unique identifier, -times = connection times, -voice = voice status
            clients = self._make_request('clientlist', params={'-uid': '', '-times': ''})

            # Filter out query clients if configured
            if not self.include_query_clients:
                clients = [c for c in clients if c.get('client_type', 0) == 0]

            logger.info(f"Fetched {len(clients)} clients from TeamSpeak server")
            return clients

        except Exception as e:
            logger.error(f"Failed to fetch clientlist: {e}")
            raise

    def test_connection(self) -> bool:
        """
        Test connection to TeamSpeak server.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Try to fetch server info
            self._make_request('serverinfo')
            logger.info("TeamSpeak server connection test successful")
            return True

        except Exception as e:
            logger.error(f"TeamSpeak server connection test failed: {e}")
            return False

    def get_server_info(self) -> Dict[str, any]:
        """
        Get TeamSpeak server information.

        Returns:
            dict: Server info (name, version, uptime, etc.)
        """
        try:
            info = self._make_request('serverinfo')
            # Info is usually a list with one element for single server
            if isinstance(info, list) and len(info) > 0:
                return info[0]
            return info

        except Exception as e:
            logger.error(f"Failed to fetch server info: {e}")
            raise


def create_client(config: TeamspeakConfig) -> TeamSpeakQueryClient:
    """
    Factory function to create TeamSpeak query client.

    Args:
        config: TeamSpeak configuration

    Returns:
        TeamSpeakQueryClient: Configured client instance
    """
    return TeamSpeakQueryClient(config)
