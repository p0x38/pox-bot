from dataclasses import dataclass, field
from typing import Any, cast

import orjson


@dataclass
class SettingsData:
    _locale: str = field(default="en", repr=False)
    embed_color: str = "#aaaa00"
    
    def __post_init__(self):
        self.locale = self._locale
    
    @property
    def locale(self) -> str:
        return self._locale
    
    @locale.setter
    def locale(self, value):
        if isinstance(value, list):
            value = value[0] if value else "en"
        elif not isinstance(value, str):
            value = "en"
        
        self._locale = value
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "locale": str(self.locale),
            "embed_color": self.embed_color
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any] | str | bytes):
        if isinstance(data, (str, bytes)):
            parsed_data: dict[str, Any] = orjson.loads(data)
        else:
            parsed_data = cast(dict[str, Any], data)
        
        if "locale" in parsed_data:
            parsed_data["_locale"] = parsed_data.pop("locale")
        
        filtered = {
            k: parsed_data[k]
            for k in cls.__dataclass_fields__
            if k in parsed_data
        }

        return cls(**filtered)