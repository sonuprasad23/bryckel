import httpx
from typing import Optional
from models import ChatResponse, Citation, Chunk, LeaseSummary
from embedding_index import EmbeddingIndex
from config import OPENROUTER_API_KEY, OPENROUTER_MODEL, OPENROUTER_BASE_URL, TOP_K_CHUNKS


RAG_SYSTEM_PROMPT = """You are an expert lease document assistant. Your role is to answer questions about commercial lease agreements accurately and thoroughly.

CRITICAL RULES:
1. ONLY use information from the provided context and extracted summary
2. ALWAYS cite the specific section/page where you found the information
3. If information is NOT in the context, clearly state "This information is not found in the provided document"
4. Use chain-of-thought reasoning for complex questions
5. Be precise with numbers, dates, and legal terms
6. Format your response in Markdown for better readability

FORMATTING GUIDELINES:
- Use **bold** for important values and terms
- Use bullet points for lists
- Use tables when comparing information
- Use > blockquotes for direct document quotes
- Use code blocks for specific values like amounts or dates"""


RAG_USER_PROMPT = """## EXTRACTED LEASE SUMMARY:
{summary}

## DOCUMENT CONTEXT:
{context}

## QUESTION: 
{question}

## INSTRUCTIONS:
1. First, check if the answer is in the extracted summary above
2. If not, search the document context for relevant information
3. Provide your answer in Markdown format with clear citations
4. Quote relevant text using > blockquotes
5. If the information is not found, say so clearly

Respond with well-formatted Markdown."""


async def chat(
    question: str, 
    index: EmbeddingIndex, 
    lease_summary: Optional[LeaseSummary] = None
) -> ChatResponse:
    """Answer a question about the lease document."""
    
    relevant_chunks = index.search(question, top_k=TOP_K_CHUNKS)
    
    if not relevant_chunks:
        return ChatResponse(
            answer="I couldn't find relevant information in the document to answer your question. Please try rephrasing or ask about a different aspect of the lease.",
            citations=[],
            reasoning=None
        )
    
    # Build summary context from extracted fields
    summary_context = ""
    if lease_summary and lease_summary.fields:
        summary_lines = ["### Extracted Fields"]
        for field in lease_summary.fields:
            if field.value:
                summary_lines.append(f"- **{field.display_name}**: {field.value}")
        summary_context = "\n".join(summary_lines)
    
    context = build_context(relevant_chunks)
    answer, reasoning = await generate_answer_with_reasoning(question, context, summary_context)
    citations = build_citations(relevant_chunks)
    
    return ChatResponse(
        answer=answer,
        citations=citations,
        reasoning=reasoning
    )


def build_context(chunks: list[Chunk]) -> str:
    """Build context string from chunks."""
    parts = []
    for i, chunk in enumerate(chunks):
        page_info = f" (Page {chunk.page_number})" if chunk.page_number else ""
        parts.append(f"### Section {i+1}: {chunk.section_name}{page_info}\n{chunk.text}")
    return "\n\n---\n\n".join(parts)


def build_citations(chunks: list[Chunk]) -> list[Citation]:
    """Build citation list from chunks."""
    seen = set()
    citations = []
    for chunk in chunks:
        key = f"{chunk.section_name}_{chunk.page_number}"
        if key not in seen:
            excerpt = chunk.text[:150] + "..." if len(chunk.text) > 150 else chunk.text
            citations.append(Citation(
                chunk_id=chunk.chunk_id,
                section_name=chunk.section_name,
                text_excerpt=excerpt,
                page_number=chunk.page_number
            ))
            seen.add(key)
    return citations


async def generate_answer_with_reasoning(
    question: str, 
    context: str, 
    summary: str
) -> tuple[str, Optional[str]]:
    """Generate a Markdown-formatted answer using the LLM."""
    
    prompt = RAG_USER_PROMPT.format(
        summary=summary if summary else "*No summary available*",
        context=context,
        question=question
    )
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": OPENROUTER_MODEL,
                    "messages": [
                        {"role": "system", "content": RAG_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2
                },
                timeout=60.0
            )
            response.raise_for_status()
            data = response.json()
            
            # Handle null content from API
            content = data["choices"][0]["message"].get("content")
            if not content:
                return "**Error**: The AI service returned an empty response. Please try again.", None
            
            return content.strip(), None
            
    except httpx.HTTPStatusError as e:
        return f"**Error**: Could not communicate with AI service (Status: {e.response.status_code})", None
    except Exception as e:
        return f"**Error**: {str(e)}", None
