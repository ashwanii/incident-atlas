import re
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, field_validator

class DocumentInput(BaseModel):
    source_key: str = Field(min_length=1, max_length=180, pattern=r'^[a-zA-Z0-9_:/.-]+$')
    title: str = Field(min_length=2, max_length=250)
    content: str = Field(min_length=20, max_length=200000)
    kind: Literal['RCA', 'SOP'] | None = None
    services: list[str] = Field(default_factory=list, max_length=30)
    origin: Literal['greenfield', 'brownfield'] = 'brownfield'
    owner: str = Field(default='', max_length=100)
    reviewed_on: date | None = None

    @field_validator('services')
    @classmethod
    def service_length(cls, values):
        if any(not v.strip() or len(v) > 80 for v in values):
            raise ValueError('Each service must contain 1-80 characters.')
        return values

    @field_validator('reviewed_on')
    @classmethod
    def valid_review(cls, value):
        if value and value > date.today():
            raise ValueError('Review date cannot be in the future.')
        return value

class ChatInput(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    kind: Literal['RCA', 'SOP'] | None = None
    document_id: str | None = Field(default=None, max_length=40)
    session_id: str | None = Field(default=None, max_length=64)

class ReviewInput(BaseModel):
    approve: bool
