from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    users = relationship("User", back_populates="company")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="member")
    company_id = Column(Integer, ForeignKey("companies.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    company = relationship("Company", back_populates="users")

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    created_by_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    company = relationship("Company")
    created_by = relationship("User")


# =====================================================================
# SHARED CONTRACT (Step 0). Do NOT change columns without telling the
# other person. Any change = its own commit starting with "contract:".
# =====================================================================

class Document(Base):
    """Owner: Muskaan (creates rows on upload). Krrish only updates `status`."""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True, nullable=False)
    uploaded_by_id = Column(Integer, ForeignKey("users.id"))
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=True)
    storage_key = Column(String, nullable=False)          # MinIO object key
    size_bytes = Column(Integer, default=0)
    # uploaded -> parsed (Muskaan) -> analyzing -> analyzed (Krrish) | failed (either)
    status = Column(String, default="uploaded", nullable=False)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    chunks = relationship(
        "DocumentChunk", back_populates="document",
        cascade="all, delete-orphan", passive_deletes=True,
        order_by="DocumentChunk.chunk_index",
    )


class DocumentChunk(Base):
    """Owner: Muskaan (writes). Krrish reads these for embeddings + agents."""
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False)
    chunk_index = Column(Integer, nullable=False)        # 0,1,2... order inside document
    text = Column(Text, nullable=False)
    page = Column(Integer, nullable=True)                # PDF page number (1-based), else null
    char_start = Column(Integer, nullable=True)
    char_end = Column(Integer, nullable=True)

    document = relationship("Document", back_populates="chunks")


class Requirement(Base):
    """Written by BOTH: Krrish's agents (created_by='ai') and Muskaan's CRUD (created_by='user')."""
    __tablename__ = "requirements"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True, nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    source_chunk_id = Column(Integer, ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True)
    code = Column(String, nullable=False)                # "REQ-001" (use deps.next_requirement_code)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    type = Column(String, default="functional")          # functional | non_functional | constraint
    category = Column(String, nullable=True)             # e.g. security, performance, usability, data, ui
    priority = Column(String, default="medium")          # high | medium | low
    status = Column(String, default="draft")             # draft | approved | rejected
    is_ambiguous = Column(Boolean, default=False)
    ambiguity_note = Column(Text, nullable=True)
    entities = Column(JSON, default=list)                # ["user", "payment gateway"] - used for knowledge graph
    confidence = Column(Float, nullable=True)            # 0..1, AI only
    created_by = Column(String, default="user")          # ai | user
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RequirementConflict(Base):
    """Owner: Krrish (writes). Muskaan only reads (export + UI)."""
    __tablename__ = "requirement_conflicts"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    requirement_a_id = Column(Integer, ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False)
    requirement_b_id = Column(Integer, ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AnalysisJob(Base):
    """Owner: Krrish. Frontend (Muskaan) polls GET /jobs/{id}."""
    __tablename__ = "analysis_jobs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    status = Column(String, default="queued")            # queued | running | done | failed
    progress = Column(Integer, default=0)                # 0..100
    message = Column(Text, nullable=True)                # human readable step, e.g. "Extracting (12/40)"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
