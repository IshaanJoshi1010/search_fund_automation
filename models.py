"""
SQLAlchemy ORM models for SFAO.
"""
import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Text, JSON, Enum as SAEnum,
    ForeignKey, Boolean
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class ResponseStatus(str, enum.Enum):
    new = "new"
    contacted = "contacted"
    replied = "replied"
    closed_no_response = "closed_no_response"


class EmailType(str, enum.Enum):
    initial = "initial"
    follow_up_1 = "follow_up_1"
    follow_up_2 = "follow_up_2"


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=True)
    firm_name = Column(String(200), nullable=True)
    email = Column(String(200), nullable=False, unique=True, index=True)
    website_url = Column(String(500), nullable=True)

    # Location
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)
    country = Column(String(100), nullable=True, default="USA")

    # Classification output
    sector_focus = Column(JSON, nullable=True)       # list of sector tags
    education = Column(JSON, nullable=True)           # list of school names found
    prior_experience = Column(Text, nullable=True)    # raw bio text
    relationship_hook = Column(String(300), nullable=True)
    focus_hook = Column(String(300), nullable=True)

    # Source
    source_url = Column(String(500), nullable=True)

    # Outreach tracking
    response_status = Column(
        SAEnum(ResponseStatus),
        nullable=False,
        default=ResponseStatus.new
    )
    follow_up_count = Column(Integer, nullable=False, default=0)
    last_contacted_at = Column(DateTime, nullable=True)
    gmail_thread_id = Column(String(200), nullable=True)  # for reply threading

    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    email_logs = relationship("EmailLog", back_populates="lead", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Lead {self.first_name} {self.last_name} <{self.email}> [{self.response_status}]>"


class EmailLog(Base):
    __tablename__ = "email_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    sent_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    email_type = Column(SAEnum(EmailType), nullable=False)
    subject = Column(String(300), nullable=False)
    body_snippet = Column(Text, nullable=True)         # first 500 chars for debugging
    gmail_message_id = Column(String(200), nullable=True)
    dry_run = Column(Boolean, nullable=False, default=False)

    lead = relationship("Lead", back_populates="email_logs")

    def __repr__(self):
        return f"<EmailLog lead_id={self.lead_id} type={self.email_type} sent={self.sent_at}>"


class Thesis(Base):
    __tablename__ = "thesis"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(300), nullable=False)
    industry_label = Column(String(200), nullable=False, unique=True, index=True)
    filepath = Column(String(500), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<Thesis {self.industry_label} → {self.filename}>"


class AppConfig(Base):
    __tablename__ = "app_config"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<AppConfig {self.key}={self.value}>"
