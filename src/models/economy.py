from dataclasses import dataclass
from typing import Any, Dict, Union, cast

import orjson

@dataclass
class EconomyData:
    user_id: int = 0
    wallet: int = 0
    bank: int = 0
    last_daily: int = 0
    last_work: int = 0

    @property
    def total(self) -> int:
        return self.wallet + self.bank
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "wallet": self.wallet,
            "bank": self.bank,
            "last_daily": self.last_daily,
            "last_work": self.last_work
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
    
    @classmethod
    def from_row(cls, row):
        if not row: return cls()
        return cls.from_dict(dict(row))