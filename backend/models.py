from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, func, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship
from .database import Base

# backend/models.py
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)  # nullable for OAuth users
    email = Column(String, index=True, nullable=True)
    github_id = Column(String, unique=True, index=True, nullable=True)  # GitHub OAuth ID
    github_username = Column(String, nullable=True)  # GitHub username
    gitlab_id = Column(String, unique=True, index=True, nullable=True)  # GitLab OAuth ID
    gitlab_username = Column(String, nullable=True)  # GitLab username
    bitbucket_id = Column(String, unique=True, index=True, nullable=True)  # Bitbucket OAuth ID
    bitbucket_username = Column(String, nullable=True)  # Bitbucket username
    auth_method = Column(String, default="jwt")  # "jwt", "github", "gitlab", or "bitbucket"
    is_subscribed = Column(Boolean, default=False)  # Premium subscription status
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    api_keys = relationship("ApiKey", back_populates="user")
    usage_logs = relationship("UsageLog", back_populates="user")


class ApiKey(Base):
    __tablename__ = "api_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "api_provider", "name_slug", name="uq_user_provider_name"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    api_provider = Column(String, nullable=False)  # openai, anthropic, groq, ...
    name = Column(String, nullable=False)
    name_slug = Column(String, nullable=False, index=True)
    encrypted_key = Column(String, nullable=False)
    unified_key_encrypted = Column(String, nullable=False)
    unified_endpoint = Column(String, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="api_keys")


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    api_key_id = Column(Integer, ForeignKey("api_keys.id"), nullable=True)
    api_provider = Column(String, nullable=False)
    endpoint_or_model = Column(String, nullable=True)
    request_tokens = Column(Integer, default=0)
    response_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    latency_ms = Column(Integer, nullable=True)
    status_code = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="usage_logs")
    api_key = relationship("ApiKey")
