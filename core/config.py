import json
import os
import logging

class ConfigManager:
    """
    Singleton Pattern (單例模式) 實作的設定檔管理員。
    整個程式中共用此實體來讀寫 tts_settings.json，避免狀態不同步。
    """
    _instance = None
    SETTINGS_FILE = "tts_settings.json"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        self.settings = {
            "voice": "zh-TW-HsiaoChenNeural", 
            "devices": [], 
            "auto_clear": True, 
            "format": "mp3", 
            "tab": "Live Playback"
        }
        if os.path.exists(self.SETTINGS_FILE):
            try:
                with open(self.SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.settings.update(data)
            except Exception as e:
                logging.error(f"Failed to load settings: {e}")

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value

    def save(self):
        """將記憶體內的設定寫入 JSON"""
        try:
            with open(self.SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logging.error(f"Failed to save settings: {e}")
