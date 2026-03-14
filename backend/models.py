from pydantic import BaseModel, field_validator
from typing import Optional, Any


class Chunk(BaseModel):
    chunk_id: str
    section_name: str
    text: str
    page_number: Optional[int] = None


class SchemaField(BaseModel):
    """A field definition from the schema CSV."""
    name: str
    display_name: str
    field_type: str = "text"
    description: str = ""
    required: bool = False


class ExtractedField(BaseModel):
    """An extracted field with value and metadata."""
    field_name: str
    display_name: str
    field_type: str = "text"
    value: Optional[str] = None
    confidence: Optional[str] = None
    evidence: Optional[str] = None
    page_reference: Optional[str] = None
    description: str = ""
    
    @field_validator('value', mode='before')
    @classmethod
    def convert_value_to_string(cls, v):
        """Convert any value to string, handling None."""
        if v is None:
            return None
        return str(v)


class LeaseSummary(BaseModel):
    """Summary of all extracted lease fields."""
    fields: list[ExtractedField] = []
    markdown_summary: str = ""  # Brief summary (priority fields)
    full_markdown: str = ""  # Full report (all fields)
    priority_fields: list[ExtractedField] = []  # Quick-extracted priority fields
    
    def to_list(self) -> list[ExtractedField]:
        return self.fields
    
    def get_priority_count(self) -> int:
        return len([f for f in self.priority_fields if f.value])
    
    def get_total_count(self) -> int:
        return len([f for f in self.fields if f.value])


class ChatRequest(BaseModel):
    question: str


class Citation(BaseModel):
    chunk_id: str
    section_name: str
    text_excerpt: Optional[str] = None
    page_number: Optional[int] = None


class ChatResponse(BaseModel):
    answer: str  # Markdown formatted
    citations: list[Citation]
    reasoning: Optional[str] = None


class ProcessRequest(BaseModel):
    pdf_type: str = "text"


class ProcessResponse(BaseModel):
    status: str
    chunks_created: int
    fields_extracted: int
    priority_fields_extracted: int = 0
    summary: Optional[LeaseSummary] = None
    markdown_output: str = ""
    full_markdown: str = ""
