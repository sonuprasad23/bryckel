"""
Lease Document Field Extractor - Expert RAG Approach

Key insights:
1. Chat works because it uses full context + natural question format
2. Batching failed because JSON format confused the model
3. Solution: Use chat-style prompt with multiple questions, parse structured response

This version:
- Uses the SAME prompt style as working chat
- Batches all questions in ONE call (fast)
- Uses simple numbered format for easy parsing
- Falls back to individual calls if batch fails
"""

import re
import csv
import os
import asyncio
import httpx
from typing import Optional, Callable
from models import ExtractedField, LeaseSummary, SchemaField
from embedding_index import EmbeddingIndex
from config import OPENROUTER_API_KEY, OPENROUTER_MODEL, OPENROUTER_BASE_URL, DATA_DIR


# Priority fields
PRIORITY_FIELDS = [
    {"name": "tenant", "display_name": "Tenant", "field_type": "text", "description": "Party Information"},
    {"name": "landlord", "display_name": "Landlord", "field_type": "text", "description": "Party Information"},
    {"name": "lease_start_date", "display_name": "Lease Start Date", "field_type": "date", "description": "Lease Terms"},
    {"name": "lease_end_date", "display_name": "Lease End Date", "field_type": "date", "description": "Lease Terms"},
    {"name": "rent_amount", "display_name": "Rent Amount", "field_type": "currency", "description": "Financial Terms"},
    {"name": "security_deposit", "display_name": "Security Deposit", "field_type": "currency", "description": "Financial Terms"},
    {"name": "renewal_options", "display_name": "Renewal Options", "field_type": "text", "description": "Lease Terms"},
    {"name": "termination_clauses", "display_name": "Termination Clauses", "field_type": "text", "description": "Legal Clauses"},
    {"name": "special_provisions", "display_name": "Special Provisions", "field_type": "text", "description": "Additional Terms"},
]

# Questions for each field (natural language, like user would ask in chat)
FIELD_QUESTIONS = {
    "tenant": "Who is the tenant or lessee?",
    "landlord": "Who is the landlord or lessor?",
    "lease_start_date": "What is the lease start/commencement date?",
    "lease_end_date": "What is the lease end/expiration date?",
    "rent_amount": "What is the rent amount (monthly or annual)?",
    "security_deposit": "What is the security deposit amount?",
    "renewal_options": "What are the renewal options?",
    "termination_clauses": "What are the early termination clauses?",
    "special_provisions": "Are there any special provisions or addendums?",
}

# System prompt - same style as working chat
BATCH_SYSTEM_PROMPT = """You are an expert lease document analyst. Answer questions about the lease document accurately and concisely.

Rules:
- Only use information explicitly stated in the document
- Give direct, brief answers (just the value, not full sentences)
- If information is not found, write "NOT FOUND"
- Be precise with names, dates, and amounts"""

# User prompt for batch extraction
BATCH_USER_PROMPT = """## LEASE DOCUMENT:
{context}

## QUESTIONS:
Answer each question briefly. Format your response EXACTLY like this:

1. [answer]
2. [answer]
3. [answer]
...

Questions:
1. Who is the tenant or lessee? (full name)
2. Who is the landlord or lessor? (full name)
3. What is the lease start/commencement date?
4. What is the lease end/expiration date?
5. What is the rent amount? (include monthly/annual)
6. What is the security deposit amount?
7. What are the renewal options?
8. What are the early termination clauses?
9. Are there any special provisions?

Your answers (numbered 1-9):"""


def get_full_document_context(index: EmbeddingIndex, max_chunks: int = 15) -> str:
    """
    Get comprehensive document context.
    Uses all chunks up to a limit, ensuring we capture key information.
    """
    all_chunks = index.get_all_chunks()
    
    if not all_chunks:
        return ""
    
    # Take up to max_chunks
    chunks_to_use = all_chunks[:max_chunks]
    
    # Build context with clear section markers
    context_parts = []
    for chunk in chunks_to_use:
        page_info = f" (Page {chunk.page_number})" if chunk.page_number else ""
        section = chunk.section_name or "Document"
        context_parts.append(f"### {section}{page_info}\n{chunk.text}")
    
    return "\n\n---\n\n".join(context_parts)


async def extract_batch_with_chat_style(index: EmbeddingIndex) -> dict[str, str]:
    """
    Extract all fields in ONE API call using chat-style prompt.
    Returns dict mapping field_name -> value (or None if not found).
    """
    print("\n" + "=" * 60)
    print("BATCH EXTRACTION (Single API Call)")
    print("=" * 60)
    
    # Get comprehensive context
    context = get_full_document_context(index, max_chunks=15)
    
    if not context:
        print("ERROR: No document context available")
        return {}
    
    print(f"Context: {len(context)} characters from document")
    
    # Build prompt
    prompt = BATCH_USER_PROMPT.format(context=context)
    
    print("Calling LLM...")
    
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
                        {"role": "system", "content": BATCH_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1
                },
                timeout=120.0
            )
            
            if response.status_code != 200:
                print(f"API Error: {response.status_code}")
                print(response.text[:300])
                return {}
            
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content")
            
            if not content:
                print("ERROR: Empty response from API")
                return {}
            
            print(f"Response received: {len(content)} characters")
            print(f"\nRaw response:\n{content}\n")
            
            # Parse the numbered response
            return parse_numbered_response(content)
            
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        return {}


def parse_numbered_response(content: str) -> dict[str, str]:
    """
    Parse numbered response format:
    1. John Smith
    2. ABC Properties LLC
    3. January 1, 2024
    ...
    """
    field_names = [
        "tenant", "landlord", "lease_start_date", "lease_end_date",
        "rent_amount", "security_deposit", "renewal_options",
        "termination_clauses", "special_provisions"
    ]
    
    results = {}
    
    # Try to match numbered patterns
    # Pattern: "1." or "1)" or "1:" followed by answer
    lines = content.strip().split('\n')
    
    current_number = None
    current_answer = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check if line starts with a number
        match = re.match(r'^(\d+)[.):]\s*(.*)', line)
        
        if match:
            # Save previous answer if exists
            if current_number is not None and current_answer:
                answer_text = ' '.join(current_answer).strip()
                if current_number <= len(field_names):
                    field_name = field_names[current_number - 1]
                    results[field_name] = clean_answer(answer_text)
            
            # Start new answer
            current_number = int(match.group(1))
            answer_text = match.group(2).strip()
            current_answer = [answer_text] if answer_text else []
        else:
            # Continuation of previous answer
            if current_number is not None:
                current_answer.append(line)
    
    # Don't forget the last answer
    if current_number is not None and current_answer:
        answer_text = ' '.join(current_answer).strip()
        if current_number <= len(field_names):
            field_name = field_names[current_number - 1]
            results[field_name] = clean_answer(answer_text)
    
    # If numbered parsing failed, try alternative parsing
    if not results:
        print("Numbered parsing failed, trying alternative...")
        results = parse_alternative_format(content, field_names)
    
    return results


def parse_alternative_format(content: str, field_names: list) -> dict[str, str]:
    """
    Alternative parsing for different response formats.
    Handles formats like:
    - Tenant: John Smith
    - **Tenant**: John Smith
    """
    results = {}
    
    display_names = [
        "tenant", "landlord", "lease start", "lease end",
        "rent", "security deposit", "renewal", "termination", "special"
    ]
    
    content_lower = content.lower()
    
    for i, field_name in enumerate(field_names):
        # Try to find the field mention
        display = display_names[i]
        
        # Pattern: field_name: value or field_name - value
        patterns = [
            rf'{display}[:\-]\s*([^\n]+)',
            rf'\*\*{display}\*\*[:\-]\s*([^\n]+)',
            rf'{display}\s+is[:\s]+([^\n]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content_lower)
            if match:
                value = match.group(1).strip()
                # Get original case from content
                start = match.start(1)
                end = match.end(1)
                original_value = content[start:end].strip()
                results[field_name] = clean_answer(original_value)
                break
    
    return results


def clean_answer(answer: str) -> Optional[str]:
    """Clean and validate an extracted answer."""
    if not answer:
        return None
    
    answer = answer.strip()
    
    # Remove markdown formatting
    answer = re.sub(r'\*\*([^*]+)\*\*', r'\1', answer)
    answer = re.sub(r'\*([^*]+)\*', r'\1', answer)
    answer = re.sub(r'`([^`]+)`', r'\1', answer)
    
    # Check for "not found" indicators
    not_found_phrases = [
        "not found", "n/a", "none", "not specified", "not mentioned",
        "not stated", "not provided", "not available", "no information",
        "cannot find", "could not find", "not included", "null"
    ]
    
    answer_lower = answer.lower()
    for phrase in not_found_phrases:
        if phrase in answer_lower and len(answer) < 50:
            return None
    
    # If answer is just punctuation or very short
    if len(answer) < 2 or answer in ["-", "—", "–", "N/A", "n/a"]:
        return None
    
    return answer


def build_extracted_fields(results: dict[str, str]) -> list[ExtractedField]:
    """Convert results dict to list of ExtractedField objects."""
    fields = []
    
    for field_def in PRIORITY_FIELDS:
        name = field_def['name']
        value = results.get(name)
        
        # Determine confidence
        if value:
            confidence = "HIGH" if len(value) < 100 else "MEDIUM"
        else:
            confidence = "LOW"
        
        fields.append(ExtractedField(
            field_name=name,
            display_name=field_def['display_name'],
            field_type=field_def['field_type'],
            value=value,
            confidence=confidence,
            description=field_def['description']
        ))
    
    return fields


async def extract_single_field_fallback(
    field: dict, 
    index: EmbeddingIndex
) -> ExtractedField:
    """
    Fallback: Extract a single field using individual API call.
    Used if batch extraction fails.
    """
    field_name = field['display_name']
    question = FIELD_QUESTIONS.get(field['name'], f"What is the {field_name}?")
    
    print(f"  Fallback extraction: {field_name}")
    
    # Get relevant chunks for this specific field
    chunks = index.search(question, top_k=5)
    if not chunks:
        chunks = index.get_all_chunks()[:5]
    
    if not chunks:
        return ExtractedField(
            field_name=field['name'],
            display_name=field_name,
            field_type=field.get('field_type', 'text'),
            value=None,
            confidence="LOW",
            description=field.get('description', '')
        )
    
    # Build context
    context_parts = []
    for chunk in chunks:
        page_info = f" (Page {chunk.page_number})" if chunk.page_number else ""
        context_parts.append(f"{chunk.section_name}{page_info}:\n{chunk.text}")
    context = "\n\n".join(context_parts)
    
    prompt = f"""Based on this lease document excerpt, answer briefly:

{context}

Question: {question}

Answer (just the value, or "NOT FOUND" if not in document):"""

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
                        {"role": "system", "content": "You are a lease document analyst. Give brief, direct answers."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1
                },
                timeout=60.0
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                value = clean_answer(content)
                
                return ExtractedField(
                    field_name=field['name'],
                    display_name=field_name,
                    field_type=field.get('field_type', 'text'),
                    value=value,
                    confidence="MEDIUM" if value else "LOW",
                    description=field.get('description', '')
                )
    except Exception as e:
        print(f"    Error: {e}")
    
    return ExtractedField(
        field_name=field['name'],
        display_name=field_name,
        field_type=field.get('field_type', 'text'),
        value=None,
        confidence="LOW",
        description=field.get('description', '')
    )


async def extract_priority_fields(index: EmbeddingIndex) -> list[ExtractedField]:
    """
    Extract all priority fields.
    Tries batch first (fast), falls back to individual calls if needed.
    """
    # Try batch extraction first (1 API call)
    results = await extract_batch_with_chat_style(index)
    
    # Check how many fields we got
    found_count = len([v for v in results.values() if v])
    print(f"\nBatch extraction found: {found_count}/{len(PRIORITY_FIELDS)} fields")
    
    # Build fields from results
    fields = build_extracted_fields(results)
    
    # If batch got less than half, try fallback for missing fields
    if found_count < len(PRIORITY_FIELDS) // 2:
        print("\nBatch extraction incomplete, trying fallback for missing fields...")
        
        for i, field in enumerate(fields):
            if not field.value:
                fallback_result = await extract_single_field_fallback(
                    PRIORITY_FIELDS[i], 
                    index
                )
                if fallback_result.value:
                    fields[i] = fallback_result
                await asyncio.sleep(0.3)  # Rate limiting
    
    # Final summary
    final_count = len([f for f in fields if f.value])
    print("\n" + "=" * 60)
    print(f"EXTRACTION COMPLETE: {final_count}/{len(fields)} fields found")
    print("=" * 60)
    
    print("\nResults:")
    for f in fields:
        val = f.value[:50] + "..." if f.value and len(f.value) > 50 else f.value
        status = val if val else "NOT FOUND"
        print(f"  {f.display_name}: {status}")
    
    return fields


async def extract_schema_fields_batch(
    schema_fields: list[SchemaField],
    index: EmbeddingIndex
) -> list[ExtractedField]:
    """Extract custom schema fields."""
    if not schema_fields:
        return []
    
    print(f"\nExtracting {len(schema_fields)} schema fields...")
    
    # Get context
    context = get_full_document_context(index, max_chunks=10)
    
    # Build questions
    questions = "\n".join([
        f"{i+1}. {f.display_name}?"
        for i, f in enumerate(schema_fields)
    ])
    
    prompt = f"""## DOCUMENT:
{context}

## Answer these questions briefly:
{questions}

Format: Number followed by answer. Use "NOT FOUND" if not in document."""

    results = []
    
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
                        {"role": "system", "content": BATCH_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1
                },
                timeout=120.0
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                # Parse numbered response
                answers = {}
                for line in content.split('\n'):
                    match = re.match(r'^(\d+)[.):]\s*(.*)', line.strip())
                    if match:
                        num = int(match.group(1))
                        answer = clean_answer(match.group(2))
                        answers[num] = answer
                
                for i, f in enumerate(schema_fields):
                    value = answers.get(i + 1)
                    results.append(ExtractedField(
                        field_name=f.name,
                        display_name=f.display_name,
                        field_type=f.field_type,
                        value=value,
                        confidence="HIGH" if value else "LOW",
                        description=f.description
                    ))
                
                return results
                
    except Exception as e:
        print(f"Schema extraction error: {e}")
    
    # Return empty results on failure
    return [
        ExtractedField(
            field_name=f.name,
            display_name=f.display_name,
            field_type=f.field_type,
            value=None,
            confidence="LOW",
            description=f.description
        )
        for f in schema_fields
    ]


def save_to_csv(fields: list[ExtractedField], filename: str = "lease_details.csv") -> str:
    """Save extracted fields to CSV file."""
    os.makedirs(DATA_DIR, exist_ok=True)
    csv_path = os.path.join(DATA_DIR, filename)
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Field Name', 'Display Name', 'Type', 'Value', 'Confidence'])
        
        for field in fields:
            writer.writerow([
                field.field_name,
                field.display_name,
                field.field_type,
                field.value or '',
                field.confidence or ''
            ])
    
    print(f"\nSaved to {csv_path}")
    return csv_path


def generate_markdown(fields: list[ExtractedField], title: str = "Lease Summary", is_full: bool = False) -> str:
    """Generate Markdown summary."""
    lines = [f"# {title}\n"]
    
    if not is_full:
        lines.append("*Key terms extracted from your lease document*\n")
    
    lines.append("---\n")
    
    # Group by category
    categories = {}
    for field in fields:
        cat = field.description if field.description else "General"
        categories.setdefault(cat, []).append(field)
    
    for category, cat_fields in categories.items():
        lines.append(f"\n## {category}\n")
        lines.append("| Field | Value | Confidence |")
        lines.append("|-------|-------|------------|")
        
        for f in cat_fields:
            val = f.value if f.value else "*Not found*"
            val = str(val).replace("|", "/").replace("\n", " ")
            if len(val) > 80:
                val = val[:77] + "..."
            conf = f.confidence or "-"
            lines.append(f"| **{f.display_name}** | {val} | {conf} |")
    
    found = len([f for f in fields if f.value])
    lines.append(f"\n---\n**Extracted:** {found}/{len(fields)} fields\n")
    
    return "\n".join(lines)


# ============================================================================
# Main API functions
# ============================================================================

async def extract_priority_only(index: EmbeddingIndex) -> LeaseSummary:
    """Extract priority fields - main entry point."""
    priority_fields = await extract_priority_fields(index)
    markdown = generate_markdown(priority_fields, "Key Lease Terms", is_full=False)
    
    save_to_csv(priority_fields)
    
    return LeaseSummary(
        fields=priority_fields,
        markdown_summary=markdown,
        full_markdown=markdown,
        priority_fields=priority_fields
    )


async def extract_remaining_fields(
    index: EmbeddingIndex,
    schema_fields: Optional[list[SchemaField]],
    priority_fields: list[ExtractedField]
) -> LeaseSummary:
    """Extract remaining schema fields in background."""
    all_fields = list(priority_fields)
    
    if schema_fields:
        priority_names = {f['name'].lower() for f in PRIORITY_FIELDS}
        priority_display = {f['display_name'].lower() for f in PRIORITY_FIELDS}
        
        remaining = [
            f for f in schema_fields
            if f.name.lower() not in priority_names
            and f.display_name.lower() not in priority_display
        ]
        
        if remaining:
            additional = await extract_schema_fields_batch(remaining, index)
            all_fields.extend(additional)
    
    save_to_csv(all_fields)
    
    priority_markdown = generate_markdown(priority_fields, "Key Lease Terms", is_full=False)
    full_markdown = generate_markdown(all_fields, "Complete Lease Report", is_full=True)
    
    return LeaseSummary(
        fields=all_fields,
        markdown_summary=priority_markdown,
        full_markdown=full_markdown,
        priority_fields=priority_fields
    )


async def extract_lease_summary(
    index: EmbeddingIndex,
    schema_fields: Optional[list[SchemaField]] = None,
    on_priority_complete: Optional[Callable] = None
) -> LeaseSummary:
    """Full extraction - legacy compatibility."""
    priority_fields = await extract_priority_fields(index)
    priority_markdown = generate_markdown(priority_fields, "Key Lease Terms", is_full=False)
    
    if on_priority_complete:
        on_priority_complete(priority_fields, priority_markdown)
    
    all_fields = list(priority_fields)
    
    if schema_fields:
        priority_names = {f['name'].lower() for f in PRIORITY_FIELDS}
        priority_display = {f['display_name'].lower() for f in PRIORITY_FIELDS}
        
        remaining = [
            f for f in schema_fields
            if f.name.lower() not in priority_names
            and f.display_name.lower() not in priority_display
        ]
        
        if remaining:
            additional = await extract_schema_fields_batch(remaining, index)
            all_fields.extend(additional)
    
    save_to_csv(all_fields)
    full_markdown = generate_markdown(all_fields, "Complete Lease Report", is_full=True)
    
    return LeaseSummary(
        fields=all_fields,
        markdown_summary=priority_markdown,
        full_markdown=full_markdown,
        priority_fields=priority_fields
    )
