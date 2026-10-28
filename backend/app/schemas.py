from datetime import datetime
from typing import Literal
from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    company_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    role: str

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class ProjectCreate(BaseModel):
    name: str
    description: str | None = None

class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str | None
    company_id: int
    created_by_id: int

    class Config:
        from_attributes = True


# =====================================================================
# SHARED CONTRACT (Step 0) - API request/response shapes.
# Frontend types (frontend/src/lib/types.ts) must mirror these.
# =====================================================================

class ProjectDetail(ProjectResponse):
    created_at: datetime | None = None


# ---------- Documents (Muskaan) ----------
class DocumentResponse(BaseModel):
    id: int
    project_id: int
    filename: str
    content_type: str | None
    size_bytes: int
    status: str
    error: str | None
    created_at: datetime | None

    class Config:
        from_attributes = True


class ChunkResponse(BaseModel):
    id: int
    document_id: int
    chunk_index: int
    text: str
    page: int | None

    class Config:
        from_attributes = True


# ---------- Requirements (both write, Muskaan owns the API) ----------
RequirementType = Literal["functional", "non_functional", "constraint"]
Priority = Literal["high", "medium", "low"]
ReqStatus = Literal["draft", "approved", "rejected"]


class RequirementCreate(BaseModel):
    title: str
    description: str
    type: RequirementType = "functional"
    category: str | None = None
    priority: Priority = "medium"
    entities: list[str] = []


class RequirementUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    type: RequirementType | None = None
    category: str | None = None
    priority: Priority | None = None
    status: ReqStatus | None = None
    is_ambiguous: bool | None = None
    ambiguity_note: str | None = None
    entities: list[str] | None = None


class RequirementResponse(BaseModel):
    id: int
    project_id: int
    document_id: int | None
    source_chunk_id: int | None
    code: str
    title: str
    description: str
    type: str
    category: str | None
    priority: str
    status: str
    is_ambiguous: bool
    ambiguity_note: str | None
    entities: list[str] | None
    confidence: float | None
    created_by: str
    created_at: datetime | None
    updated_at: datetime | None

    class Config:
        from_attributes = True


# ---------- AI side (Krrish) ----------
class JobResponse(BaseModel):
    id: int
    project_id: int
    document_id: int
    status: str            # queued | running | done | failed
    progress: int          # 0..100
    message: str | None

    class Config:
        from_attributes = True


class ConflictResponse(BaseModel):
    id: int
    requirement_a_id: int
    requirement_b_id: int
    reason: str

    class Config:
        from_attributes = True


class GraphNode(BaseModel):
    id: str                # "req:12", "ent:payment gateway", "doc:3"
    label: str
    type: Literal["requirement", "entity", "document"]
    data: dict = {}


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str              # MENTIONS | CONFLICTS_WITH | SOURCE_OF


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class ChatRequest(BaseModel):
    question: str


class ChatSource(BaseModel):
    document_id: int
    filename: str
    chunk_index: int
    text: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]
