"""Loads the YAML config"""

import logging
import logging.config
import yaml
import os
from pathlib import Path

def setup_logging(
    default_path="config/logging_config.yaml",
    default_level=logging.INFO,
    env_key="LOG_CFG"
):
    """Setup logging configuration"""
    path = Path(default_path)
    
    # Ensure log directory exists
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    value = os.getenv(env_key, None)
    if value:
        path = value
        
    if os.path.exists(path):
        with open(path, 'rt') as f:
            try:
                config = yaml.safe_load(f.read())
                logging.config.dictConfig(config)
            except Exception as e:
                print(f"Error in Logging Configuration. Using default configs {e}")
                logging.basicConfig(level=default_level)
    else:
        logging.basicConfig(level=default_level)
        print("Failed to load configuration file. Using default configs")
        
    return logging.getLogger(__name__)