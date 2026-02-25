from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any

class ApiUsageBase(BaseModel):
    provider: str
    endpoint: str
    model: Optional[str] = None
    tokens_prompt: int = 0
    tokens_completion: int = 0
    tokens_total: int = 0
    metadata_json: Optional[Dict[str, Any]] = None

class ApiUsageCreate(ApiUsageBase):
    pass

class ApiUsage(ApiUsageBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class ApiUsageStats(BaseModel):
    total_calls: int
    total_tokens: int
    by_provider: Dict[str, Dict[str, int]]
