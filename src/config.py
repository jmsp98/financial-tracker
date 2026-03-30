"""
Configuration loader for the financial tracker.

Loads settings from config.yaml if present, otherwise uses sensible defaults.
The active pipeline (PureMLCategorizer) does not require config.yaml -- all
callers use config.get() with default values.
"""

import yaml
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Default configuration when no config.yaml is present
_DEFAULTS: Dict[str, Any] = {
    "data": {
        "raw_statements": "./data/raw",
        "processed": "./data/processed",
        "categorized": "./data/categorized",
    },
    "dashboard": {
        "host": "127.0.0.1",
        "port": 8050,
        "debug": False,
    },
    "processing": {
        "date_formats": [
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%d %b %Y",
            "%d %b %y",
            "%Y-%m-%d",
        ],
        "currency_symbols": ["£", "GBP"],
    },
}


class Config:
    """Configuration management for the financial tracker."""

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file, falling back to defaults."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as file:
                    loaded = yaml.safe_load(file)
                    if isinstance(loaded, dict):
                        return loaded
                    logger.warning("config.yaml is empty or invalid; using defaults")
            except yaml.YAMLError as e:
                logger.warning(f"Error parsing {self.config_path}: {e}; using defaults")
        else:
            logger.debug(f"No {self.config_path} found; using built-in defaults")
        return dict(_DEFAULTS)

    def get(self, key: str, default=None):
        """Get a configuration value using dot notation (e.g., 'data.raw_statements')."""
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_data_paths(self) -> Dict[str, str]:
        """Get all data directory paths."""
        return self.get("data", {}) or {}

    def get_dashboard_config(self) -> Dict[str, Any]:
        """Get dashboard configuration."""
        return self.get("dashboard", {}) or {}

    def get_processing_config(self) -> Dict[str, Any]:
        """Get processing configuration."""
        return self.get("processing", {}) or {}

    def ensure_directories(self):
        """Create necessary directories if they don't exist."""
        data_paths = self.get_data_paths()
        for path in data_paths.values():
            os.makedirs(path, exist_ok=True)


# Global config instance
config = Config()
