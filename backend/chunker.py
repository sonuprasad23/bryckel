import re
from models import Chunk


def chunk_text(content: str, chunk_size: int = 1000, overlap: int = 200) -> list[Chunk]:
    """Main entry point for chunking text content."""
    if not content or not content.strip():
        print("DEBUG: Empty content passed to chunk_text")
        return []
    
    content = clean_text(content)
    print(f"DEBUG: After cleaning, content length: {len(content)}")
    
    # Check for page markers
    page_pattern = re.compile(r'\[Page\s+(\d+)\]')
    
    if page_pattern.search(content):
        print("DEBUG: Found page markers, using page-based chunking")
        chunks = chunk_by_pages(content, chunk_size, overlap)
    else:
        print("DEBUG: No page markers, using section-based chunking")
        chunks = chunk_by_sections(content, chunk_size, overlap)
    
    # Fallback: if no chunks created, create simple chunks
    if not chunks and len(content.strip()) > 50:
        print("DEBUG: Fallback to simple chunking")
        chunks = simple_chunk(content, chunk_size, overlap)
    
    print(f"DEBUG: Created {len(chunks)} chunks")
    return chunks


def chunk_by_pages(content: str, chunk_size: int, overlap: int) -> list[Chunk]:
    """Chunk content that has [Page N] markers."""
    chunks = []
    chunk_counter = 0
    
    # Split by page markers but keep the page numbers
    page_pattern = re.compile(r'\[Page\s+(\d+)\]\s*')
    
    # Find all page markers and their positions
    pages = []
    last_end = 0
    
    for match in page_pattern.finditer(content):
        # Get text before this marker (belongs to previous page)
        if last_end > 0 and pages:
            # Update the previous page's text
            pass
        
        page_num = int(match.group(1))
        start_pos = match.end()
        pages.append({'page_num': page_num, 'start': start_pos, 'text': ''})
        last_end = start_pos
    
    # Now extract text for each page
    for i, page in enumerate(pages):
        if i + 1 < len(pages):
            # Text goes until next page marker
            next_start = pages[i + 1]['start']
            # Find where the next [Page marker begins
            marker_match = page_pattern.search(content[page['start']:])
            if marker_match:
                page['text'] = content[page['start']:page['start'] + marker_match.start()].strip()
            else:
                page['text'] = content[page['start']:next_start].strip()
        else:
            # Last page - text goes to end
            page['text'] = content[page['start']:].strip()
    
    # Create chunks from pages
    for page in pages:
        page_text = page['text']
        page_num = page['page_num']
        
        if not page_text or len(page_text) < 20:
            continue
        
        section_name = detect_section_name(page_text, f"Page {page_num}")
        
        if len(page_text) <= chunk_size:
            chunks.append(Chunk(
                chunk_id=f"chunk_{chunk_counter}",
                section_name=section_name,
                text=page_text,
                page_number=page_num
            ))
            chunk_counter += 1
        else:
            sub_chunks = split_text_with_overlap(page_text, chunk_size, overlap)
            for j, sub_text in enumerate(sub_chunks):
                if sub_text.strip():
                    chunks.append(Chunk(
                        chunk_id=f"chunk_{chunk_counter}",
                        section_name=f"{section_name} (Part {j + 1})",
                        text=sub_text,
                        page_number=page_num
                    ))
                    chunk_counter += 1
    
    return chunks


def chunk_by_sections(content: str, chunk_size: int, overlap: int) -> list[Chunk]:
    """Chunk content by detecting section headers."""
    chunks = []
    chunk_counter = 0
    
    # Try to find section patterns
    section_patterns = [
        re.compile(r'^(?:ARTICLE|SECTION|EXHIBIT)\s*[\d\w.]+[:\s]*(.*)', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^(\d+\.)\s+([A-Z][A-Za-z\s]+)', re.MULTILINE),
        re.compile(r'^([A-Z][A-Z\s]{3,}):?\s*$', re.MULTILINE),
    ]
    
    # Find all section headers
    all_matches = []
    for pattern in section_patterns:
        for match in pattern.finditer(content):
            all_matches.append((match.start(), match.end(), match.group(0).strip()[:100]))
    
    # Sort by position
    all_matches.sort(key=lambda x: x[0])
    
    # Remove overlapping matches (keep first)
    filtered_matches = []
    last_end = 0
    for start, end, name in all_matches:
        if start >= last_end:
            filtered_matches.append((start, end, name))
            last_end = end
    
    # Extract sections
    sections = []
    for i, (start, end, section_name) in enumerate(filtered_matches):
        if i + 1 < len(filtered_matches):
            next_start = filtered_matches[i + 1][0]
            text = content[end:next_start].strip()
        else:
            text = content[end:].strip()
        
        if text and len(text) > 30:
            sections.append((section_name, text))
    
    # If no sections found, treat entire content as one section
    if not sections:
        if len(content.strip()) > 30:
            sections = [("Document", content.strip())]
    
    # Create chunks from sections
    for section_name, text in sections:
        page_num = extract_page_from_text(text)
        
        if len(text) <= chunk_size:
            chunks.append(Chunk(
                chunk_id=f"chunk_{chunk_counter}",
                section_name=section_name,
                text=text,
                page_number=page_num
            ))
            chunk_counter += 1
        else:
            sub_chunks = split_text_with_overlap(text, chunk_size, overlap)
            for j, sub_text in enumerate(sub_chunks):
                if sub_text.strip():
                    chunks.append(Chunk(
                        chunk_id=f"chunk_{chunk_counter}",
                        section_name=f"{section_name} (Part {j + 1})",
                        text=sub_text,
                        page_number=page_num
                    ))
                    chunk_counter += 1
    
    return chunks


def simple_chunk(content: str, chunk_size: int, overlap: int) -> list[Chunk]:
    """Simple fallback chunking - just split by size."""
    chunks = []
    chunk_counter = 0
    
    text_chunks = split_text_with_overlap(content, chunk_size, overlap)
    
    for i, text in enumerate(text_chunks):
        if text.strip():
            chunks.append(Chunk(
                chunk_id=f"chunk_{chunk_counter}",
                section_name=f"Section {i + 1}",
                text=text.strip(),
                page_number=None
            ))
            chunk_counter += 1
    
    return chunks


def extract_page_from_text(text: str) -> int | None:
    """Try to extract page number from text content."""
    page_match = re.search(r'page\s*(\d+)', text[:200], re.IGNORECASE)
    if page_match:
        return int(page_match.group(1))
    return None


def split_text_with_overlap(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into chunks with overlap, trying to break at sentence boundaries."""
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    
    # Try to split by sentences first
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    current_chunk = []
    current_length = 0
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        sentence_len = len(sentence)
        
        if current_length + sentence_len > chunk_size and current_chunk:
            chunks.append(' '.join(current_chunk))
            
            # Keep some sentences for overlap
            overlap_sentences = []
            overlap_len = 0
            for s in reversed(current_chunk):
                if overlap_len + len(s) > overlap:
                    break
                overlap_sentences.insert(0, s)
                overlap_len += len(s)
            current_chunk = overlap_sentences
            current_length = overlap_len
        
        current_chunk.append(sentence)
        current_length += sentence_len + 1  # +1 for space
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    # If sentence splitting didn't work, fall back to character-based
    if not chunks:
        pos = 0
        while pos < len(text):
            end = min(pos + chunk_size, len(text))
            chunks.append(text[pos:end])
            pos = end - overlap if end < len(text) else end
    
    return chunks


def detect_section_name(text: str, default: str) -> str:
    """Try to detect a section name from the beginning of text."""
    patterns = [
        (r'^(?:ARTICLE|SECTION)\s*[\d\w.]+[:\s]*([^\n]+)', 0),
        (r'^(\d+\.)\s*([A-Z][A-Za-z\s]+)', 0),
        (r'^([A-Z][A-Z\s]{5,})', 0),
    ]
    
    for pattern, group in patterns:
        match = re.search(pattern, text[:500], re.MULTILINE)
        if match:
            section = match.group(0).strip()[:80]
            return section
    
    return default


def clean_text(text: str) -> str:
    """Clean up text content."""
    if not text:
        return ""
    # Remove control characters
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    # Remove HTML/markdown image placeholders
    text = re.sub(r'<!-- image -->', '', text)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)  # Markdown images
    # Normalize whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.replace('\r\n', '\n')
    return text.strip()


def chunk_markdown(content: str) -> list[Chunk]:
    """Alias for chunk_text for markdown content."""
    return chunk_text(content)
