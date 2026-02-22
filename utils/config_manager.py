import json
import os
import config as default_config
import copy
from google.genai.types import HarmCategory, HarmBlockThreshold, SafetySetting

CONFIG_FILE = "admin_config.json"

class ConfigManager:
    """Manages dynamic configuration overrides for Techiee."""
    
    def __init__(self):
        self.overrides = {}
        self.load()

    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self.overrides = json.load(f)
            except Exception as e:
                print(f"Failed to load admin config overrides: {e}")
                self.overrides = {}

    def save(self):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.overrides, f, indent=4)
        except Exception as e:
            print(f"Failed to save admin config overrides: {e}")

    def get(self, key):
        """Get a configuration value, prioritizing overrides then default_config."""
        if key in self.overrides:
            return self.overrides[key]
        
        # Specially handle get_system_instruction which is a function in config.py
        if key == "system_instruction_base":
            # If not overridden, extract a default base from config.py somehow, 
            # or just rely on a default string.
            pass
            
        return getattr(default_config, key, None)

    def set(self, key, value):
        """Set a configuration override temporarily or permanently."""
        self.overrides[key] = value
        self.save()

    def reset(self):
        """Reset all configuration overrides to defaults."""
        self.overrides = {}
        self.save()
        
    def get_safety_settings(self):
        """Get the parsed safety settings from config or overrides."""
        saved = self.get("safety_settings")
        if not saved:
            return default_config.safety_settings
            
        # Parse from dicts to SafetySetting objects
        settings = []
        for cat_name, threshold_name in saved.items():
            try:
                cat = getattr(HarmCategory, cat_name)
                thresh = getattr(HarmBlockThreshold, threshold_name)
                settings.append(SafetySetting(category=cat, threshold=thresh))
            except AttributeError:
                pass
        return settings if settings else default_config.safety_settings

    def set_safety_settings(self, category_name: str, threshold_name: str):
        """Update a specific safety setting."""
        saved = self.get("safety_settings")
        if not saved:
            # Map default to dict
            saved = {}
            for s in default_config.safety_settings:
                # Get the string name of the enum
                saved[s.category.name] = s.threshold.name
                
        saved[category_name] = threshold_name
        self.set("safety_settings", saved)

    def __getattr__(self, key):
        """Allow dot notation access like dynamic_config.gemini_model"""
        if hasattr(default_config, key):
            # Special getters
            if key == "safety_settings":
                return self.get_safety_settings()
            
            return self.get(key)
        raise AttributeError(f"'ConfigManager' object has no attribute '{key}'")

dynamic_config = ConfigManager()
