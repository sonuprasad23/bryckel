import csv
from typing import Optional
from models import SchemaField


def load_schema(csv_path: str) -> list[SchemaField]:
    """
    Load schema fields from CSV file.
    Handles various CSV formats flexibly.
    """
    fields = []
    
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    
    # Try to detect format
    lines = content.strip().split('\n')
    if not lines:
        return fields
    
    # Check if it's a simple two-column format (field_name, field_type)
    first_line = lines[0]
    
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        # Detect delimiter
        try:
            dialect = csv.Sniffer().sniff(content[:2048], delimiters=',;\t|')
            delimiter = dialect.delimiter
        except:
            delimiter = ','
        
        f.seek(0)
        reader = csv.reader(f, delimiter=delimiter)
        rows = list(reader)
    
    if not rows:
        return fields
    
    # Detect if first row is header
    first_row = rows[0]
    has_header = any(
        h.lower() in ['name', 'field', 'field_name', 'type', 'field_type', 'description']
        for h in first_row if h
    )
    
    start_idx = 1 if has_header else 0
    current_category = None
    current_subcategory = None
    
    for row in rows[start_idx:]:
        if not row or all(not cell.strip() for cell in row):
            continue
        
        # Get first two columns
        col1 = row[0].strip() if len(row) > 0 else ""
        col2 = row[1].strip() if len(row) > 1 else ""
        col3 = row[2].strip() if len(row) > 2 else ""
        
        # Skip empty rows
        if not col1 and not col2:
            continue
        
        # Check if this is a category header (no type, possibly uppercase)
        if col1 and not col2:
            if col1.isupper() or '&' in col1 or col1.endswith(':'):
                current_category = col1.rstrip(':')
                current_subcategory = None
            else:
                current_subcategory = col1
            continue
        
        # This is a field definition
        if col1 and col2:
            # Build description from category info
            description = ""
            if current_category:
                description = f"{current_category}"
                if current_subcategory:
                    description += f" > {current_subcategory}"
            
            # Add any explicit description from col3
            if col3:
                if description:
                    description += f" | {col3}"
                else:
                    description = col3
            
            # Determine display name
            display_name = col1
            
            fields.append(SchemaField(
                name=col1.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('$', 'amount'),
                display_name=display_name,
                field_type=col2.lower(),
                description=description,
                required=False
            ))
    
    print(f"Loaded {len(fields)} fields from schema:")
    for f in fields[:10]:
        print(f"  - {f.display_name} ({f.field_type})")
    if len(fields) > 10:
        print(f"  ... and {len(fields) - 10} more")
    
    return fields


def get_field_categories(fields: list[SchemaField]) -> dict[str, list[SchemaField]]:
    """Group fields by their category from description."""
    categories = {}
    
    for field in fields:
        category = "General"
        if field.description:
            parts = field.description.split('>')
            if parts:
                category = parts[0].strip()
        
        if category not in categories:
            categories[category] = []
        categories[category].append(field)
    
    return categories
