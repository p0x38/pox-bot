from dataclasses import dataclass, field
from typing import Any, Dict, Union, cast

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
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "locale": str(self.locale),
            "embed_color": self.embed_color
        }
    
    @classmethod
    def from_dict(cls, data: Union[Dict[str, Any], str, bytes]):
        if isinstance(data, (str, bytes)):
            parsed_data: Dict[str, Any] = orjson.loads(data)
        else:
            parsed_data = cast(Dict[str, Any], data)
        
        filtered = {
            k: parsed_data[k]
            for k in cls.__dataclass_fields__
            if k in parsed_data
        }

        return cls(**filtered)