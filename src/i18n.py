import asyncio
import json
import os

from logger import logger

class I18n:
    def __init__(self, default_locale="en"):
        self.default_locale = default_locale
        self.translations = {}
        self._mtimes = {}
        self.path = "resources/locales"
    
    def load(self):
        for file in os.listdir(self.path):
            if file.endswith(".json"):
                self._load_file(file)
    
    def _load_file(self, file):
        locale = file.replace(".json", "")
        full_path = os.path.join(self.path, file)
        
        with open(full_path, "r", encoding="utf-8") as f:
            self.translations[locale] = json.load(f)
        
        self._mtimes[file] = os.path.getmtime(full_path)
        logger.info(f"[i18n] Loaded {locale}")
    
    async def watch(self, interval=25):
        while True:
            await asyncio.sleep(interval)
            
            for file in os.listdir(self.path):
                if not file.endswith(".json"): continue
                
                full_path = os.path.join(self.path, file)
                mtime = os.path.getmtime(full_path)
                
                if file not in self._mtimes or mtime != self._mtimes[file]:
                    self._load_file(file)
    
    def t(self, key: str, locale: str, **kwargs):
        locale = locale.split("-")[0]
        
        data = self.translations.get(locale)
        if not data:
            data = self.translations[self.default_locale]
        
        text = data.get(key)
        
        if text is None:
            text = self.translations[self.default_locale].get(key, key)
        
        return text.format(**kwargs)