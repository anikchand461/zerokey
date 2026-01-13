from pydantic import BaseModel
from datetime import datetime

class ApiKeyOut(BaseModel):
    id: int
    provider: str
    created_at: datetime

    class Config:
        from_attributes = True  # Allows SQLAlchemy objects to be converted
