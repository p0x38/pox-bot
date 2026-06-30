from typing import Any, TypeVar

from pydantic import BaseModel, Field, model_validator

T = TypeVar("T")


class EmotionDict[T](BaseModel):
    default: T
    scary: T


class ContributorItem(BaseModel):
    id: int
    command: str
    description: EmotionDict[str] = Field(
        default_factory=lambda: EmotionDict(default="", scary="")
    )
    quote: EmotionDict[str] = Field(
        default_factory=lambda: EmotionDict(default="", scary="")
    )
    contributions: EmotionDict[list[str]] = Field(
        default_factory=lambda: EmotionDict(default=[], scary=[])
    )
    content: EmotionDict[list[str]] = Field(
        default_factory=lambda: EmotionDict(default=[], scary=[])
    )
    thumbnail_url: EmotionDict[str] = Field(
        default_factory=lambda: EmotionDict(default="", scary="")
    )
    
    @model_validator(mode="before")
    @classmethod
    def transform_flat_to_nested(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        
        fields_to_transform = {
            "description": "",
            "quote": "",
            "thumbnail_url": "",
            "contributions": [],
            "content": [],
        }
        
        new_data = data.copy()
        
        for field, default_val in fields_to_transform.items():
            if field in data or f"{field}.scary" in data:
                d_val = (
                    default_val.copy()
                    if isinstance(default_val, list)
                    else default_val
                )
                s_val = (
                    default_val.copy()
                    if isinstance(default_val, list)
                    else default_val
                )
                
                current_default = data.get(field, d_val)
                current_scary = data.get(f"{field}.scary", s_val)
                
                new_data[field] = {"default": current_default, "scary": current_scary}
                
                if f"{field}.scary" in new_data:
                    del new_data[f"{field}.scary"]
        return new_data


class Contributors(BaseModel):
    data_version: int = 3
    contributors: list[ContributorItem] = Field(default_factory=list)
