from .config import Config, DefaultPreferences, UserPreferences
import sys

config = Config()

__all__ = ["Config", "DefaultPreferences", "UserPreferences", "config"]

# Ensure "config.config" imports work
sys.modules.setdefault('config.config', sys.modules[__name__]) 