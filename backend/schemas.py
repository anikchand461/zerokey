from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ApiKeyOut(BaseModel):
    id: int
    provider: str
    name: str
    created_at: datetime
    expires_at: Optional[datetime]
    api_key: str
    unified_api_key: str
    unified_endpoint: str

    class Config:
        from_attributes = True  # Allows SQLAlchemy objects to be converted
