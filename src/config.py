"""
Configuration loader for the financial tracker.
"""

import yaml
import os
from typing import Dict, Any


class Config:
    """Configuration management for the financial tracker."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing configuration file: {e}")
    
    def get(self, key: str, default=None):
        """Get a configuration value using dot notation (e.g., 'data.raw_statements')."""
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_data_paths(self) -> Dict[str, str]:
        """Get all data directory paths."""
        return self.get('data', {}) or {}
    
    def get_categories(self) -> Dict[str, Dict[str, list]]:
        """Get categorization rules."""
        return self.get('categories', {}) or {}
    
    def get_dashboard_config(self) -> Dict[str, Any]:
        """Get dashboard configuration."""
        return self.get('dashboard', {}) or {}
    
    def get_processing_config(self) -> Dict[str, Any]:
        """Get processing configuration."""
        return self.get('processing', {}) or {}
    
    def ensure_directories(self):
        """Create necessary directories if they don't exist."""
        data_paths = self.get_data_paths()
        for path in data_paths.values():
            os.makedirs(path, exist_ok=True)
        
        # Also create models directory for future ML features
        os.makedirs("./models", exist_ok=True)


# Global config instance
config = Config()