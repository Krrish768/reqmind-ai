"""All shared data formats: API requests and responses, LLM outputs, sample files.

The frontend reads the same field names, so a change here is told to the other
teammate first and made in one small commit.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

RequirementType = Literal["functional", "non_functional", "constraint"]
Priority = Literal["high", "medium", "low"]
ReqStatus = Literal["draft", "approved", "rejected"]
Category = Literal["security", "performance", "usability", "data", "ui", "integration", "reliability", "other"]
JobStatus = Literal["queued", "running", "done", "failed"]


class OrmModel(BaseModel):
    """Base for responses built from database rows."""

    model_config = ConfigDict(from_attributes=True)


# ---------- Auth and projects ----------
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    company_name: str = Field(min_length=1)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(OrmModel):
    id: int
    email: EmailStr
    role: str
    company_id: int


class Token(BaseModel):
    access_token: str
    token_type: str


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None


class ProjectResponse(OrmModel):
    id: int
    name: str
    description: str | None
    company_id: int
    created_by_id: int


class ProjectDetail(ProjectResponse):
    created_at: datetime | None = None


class HealthResponse(BaseModel):
    status: str
    database: str
    config: str
    ai_enabled: bool


# ---------- Documents (Muskaan) ----------
class DocumentResponse(OrmModel):
    id: int
    project_id: int
    filename: str
    content_type: str | None
    size_bytes: int
    status: str
    error: str | None
    created_at: datetime | None


class ChunkResponse(OrmModel):
    id: int
    document_id: int
    chunk_index: int
    text: str
    page: int | None


class ChunkIn(BaseModel):
    """One text chunk given to the analysis. Same format as samples/chunks.json."""

    chunk_id: int | None = None
    chunk_index: int
    text: str
    page: int | None = None


# ---------- Requirements (both write, Muskaan owns the API) ----------
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


class RequirementResponse(OrmModel):
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


# ---------- Analysis, conflicts, graph, chat (Krrish) ----------
class JobResponse(OrmModel):
    id: int
    project_id: int
    document_id: int
    status: JobStatus
    progress: int
    message: str | None
    created_at: datetime | None = None
    finished_at: datetime | None = None


class ConflictResponse(OrmModel):
    id: int
    requirement_a_id: int
    requirement_b_id: int
    reason: str


class GraphNode(BaseModel):
    id: str  # "req:12", "ent:payment gateway", "doc:3"
    label: str
    type: Literal["requirement", "entity", "document"]
    data: dict = {}


class GraphEdge(BaseModel):
    source: str
    target: str
    type: Literal["MENTIONS", "CONFLICTS_WITH", "SOURCE_OF"]


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    source: Literal["neo4j", "database"]


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class ChatSource(BaseModel):
    document_id: int
    filename: str
    chunk_index: int
    text: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]
    method: Literal["llm", "template"]


# ---------- LLM outputs (JSON schema given to Ollama) ----------
class LlmRequirement(BaseModel):
    title: str = Field(description="Short name, at most 8 words")
    description: str = Field(description="The requirement in one clear sentence")
    type: RequirementType
    category: Category
    source_quote: str = Field(description="The exact sentence from the text this requirement comes from")
    entities: list[str] = Field(description="Nouns from the text: actors, systems, data. Lowercase.")
    is_ambiguous: bool
    ambiguity_note: str | None = Field(description="Which words are vague, or null")


class LlmExtraction(BaseModel):
    requirements: list[LlmRequirement]


class LlmConflictVerdict(BaseModel):
    is_conflict: bool
    reason: str = Field(description="One sentence. Use only facts from the two requirements.")


class LlmChatAnswer(BaseModel):
    answer: str = Field(description="Answer using only the passages")
    passages: list[str] = Field(description='Letters of the passages the answer uses, like ["A", "C"]')


# ---------- Analysis results inside the backend ----------
class FoundRequirement(BaseModel):
    """A requirement found in one chunk, before it is saved."""

    title: str
    description: str
    type: RequirementType
    category: str | None
    priority: Priority
    source_quote: str
    entities: list[str]
    is_ambiguous: bool
    ambiguity_note: str | None
    chunk_index: int
    chunk_id: int | None
    method: Literal["llm", "rules"]


class FoundConflict(BaseModel):
    """Two requirements (positions in the found list) that contradict each other."""

    index_a: int
    index_b: int
    reason: str
