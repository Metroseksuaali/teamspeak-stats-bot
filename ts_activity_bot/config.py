"""
Configuration management for TS6 Activity Bot.

Loads and validates configuration from YAML file using Pydantic.

Copyright (C) 2025 Metroseksuaali
Licensed under GNU AGPL v3.0 - see LICENSE file for details.
"""

import os
import sys
from pathlib import Path
from typing import Optional

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class TeamspeakConfig(BaseSettings):
    """TeamSpeak server connection settings."""

    base_url: str = Field(..., description="WebQuery base URL (e.g., https://ts.example.com:10443)")
    api_key: str = Field(..., description="WebQuery API key")
    virtual_server_id: int = Field(1, description="Virtual server ID")
    verify_ssl: bool = Field(True, description="Verify SSL certificates")
    timeout: int = Field(10, description="Request timeout in seconds")
    include_query_clients: bool = Field(False, description="Include query clients in stats")

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Ensure base_url doesn't have trailing slash."""
        return v.rstrip("/")

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """Ensure timeout is reasonable."""
        if v < 1 or v > 300:
            raise ValueError("timeout must be between 1 and 300 seconds")
        return v


class PollingConfig(BaseSettings):
    """Polling behavior settings."""

    interval_seconds: int = Field(30, description="Polling interval in seconds")
    max_retries: int = Field(3, description="Maximum retry attempts on failure")
    retry_backoff_base: int = Field(2, description="Exponential backoff base (seconds)")

    @field_validator("interval_seconds")
    @classmethod
    def validate_interval(cls, v: int) -> int:
        """Ensure polling interval is reasonable."""
        if v < 10 or v > 3600:
            raise ValueError("interval_seconds must be between 10 and 3600")
        return v


class DatabaseConfig(BaseSettings):
    """Database settings."""

    path: str = Field("./data/ts_activity.sqlite", description="SQLite database file path")
    retention_days: Optional[int] = Field(None, description="Data retention period in days (null = keep forever)")

    @field_validator("retention_days")
    @classmethod
    def validate_retention(cls, v: Optional[int]) -> Optional[int]:
        """Ensure retention period is reasonable."""
        if v is not None and v < 1:
            raise ValueError("retention_days must be at least 1 day or null")
        return v


class LoggingConfig(BaseSettings):
    """Logging settings."""

    level: str = Field("INFO", description="Log level: DEBUG, INFO, WARNING, ERROR")
    file: Optional[str] = Field(None, description="Log file path (null for stdout only)")
    max_bytes: int = Field(10485760, description="Max log file size in bytes (10MB default)")
    backup_count: int = Field(5, description="Number of backup log files")

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Ensure log level is valid."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"level must be one of: {', '.join(valid_levels)}")
        return v_upper


class APIConfig(BaseSettings):
    """API server settings."""

    enabled: bool = Field(True, description="Enable FastAPI web server")
    api_key: str = Field("CHANGE_ME_SECRET_KEY_123", description="API authentication key")
    host: str = Field("0.0.0.0", description="Server host binding")
    port: int = Field(8080, description="Server port")
    docs_enabled: bool = Field(True, description="Enable auto-generated API docs")

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Ensure port is valid."""
        if v < 1 or v > 65535:
            raise ValueError("port must be between 1 and 65535")
        return v


class Config(BaseSettings):
    """Main configuration container."""

    teamspeak: TeamspeakConfig
    polling: PollingConfig
    database: DatabaseConfig
    logging: LoggingConfig
    api: APIConfig


def load_config(config_path: str = "config.yaml") -> Config:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Config: Validated configuration object

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
    """
    config_file = Path(config_path)

    if not config_file.exists():
        print(f"Error: Configuration file not found: {config_path}", file=sys.stderr)
        print(f"Please create a config.yaml file. See config.example.yaml for reference.", file=sys.stderr)
        sys.exit(1)

    try:
        with open(config_file, 'r') as f:
            config_dict = yaml.safe_load(f)

        if not config_dict:
            raise ValueError("Configuration file is empty")

        return Config(**config_dict)

    except yaml.YAMLError as e:
        print(f"Error parsing YAML configuration: {e}", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        sys.exit(1)


# Global config instance (loaded on first import)
_config: Optional[Config] = None


def get_config(config_path: str = "config.yaml") -> Config:
    """
    Get the global configuration instance.

    Loads config on first call, returns cached instance on subsequent calls.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Config: Configuration object
    """
    global _config
    if _config is None:
        _config = load_config(config_path)
    return _config
