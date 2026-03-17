#!/usr/bin/env python3
"""
Enhanced cleanup script for Swiss PII templates.
Handles both 'basic' and 'comprehensive' JSON file formats.

Fixes:
- Brace formatting (single to double braces)
- Removes repetitive boilerplate sections
- Handles comprehensive-specific issues (ERGÄNZENDE INFORMATIONEN, Zusatzinfo, Kontext)
- Validates template structure
"""

import json
import re
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple


def fix_braces(text: str) -> str:
    """
    Convert single braces {PLACEHOLDER} to double braces {{PLACEHOLDER}}.
    Handles cases carefully to avoid converting already-double braces to quadruple.
    """
    # Pattern: {WORD} where WORD is uppercase with underscores
    # Negative lookbehind to ensure not preceded by {
    # Negative lookahead to ensure not followed by }
    pattern = r'(?<!{)\{([A-Z][A-Z_0-9]*)\}(?!})'
    replacement = r'{{\1}}'
    return re.sub(pattern, replacement, text)


def remove_boilerplate_basic(text: str) -> str:
    """
    Remove repetitive footer sections that appear in basic templates.
    """
    cutoff_phrases = [
        "Zusätzliche Informationen:",
        "Bei Rückfragen kontaktieren Sie uns:",
        "Weitere Details:",
        "Kontaktdaten:",
    ]
    
    earliest_pos = len(text)
    found_phrase = None
    
    for phrase in cutoff_phrases:
        pos = text.find(phrase)
        if pos != -1 and pos < earliest_pos:
            earliest_pos = pos
            found_phrase = phrase
    
    if found_phrase:
        cleaned = text[:earliest_pos].rstrip()
        cleaned = cleaned.rstrip('\n')
        return cleaned
    
    return text


def remove_boilerplate_comprehensive(text: str) -> str:
    """
    Remove repetitive sections specific to comprehensive templates.
    These include processing metadata that repeats across templates.
    """
    # Define boilerplate sections with their start markers
    # Order matters - remove longer/more specific patterns first
    boilerplate_sections = [
        # ERGÄNZENDE INFORMATIONEN section (German)
        ("ERGÄNZENDE INFORMATIONEN:", None),
        # Zusatzinfo section (German)
        ("Zusatzinfo:", None),
        # Kontext section (German)
        ("Kontext:", None),
        # Additional common footer patterns
        ("Systemdaten:", None),
        ("---\nKontext:", None),  # Some have a separator before Kontext
    ]
    
    cleaned = text
    removed_sections = []
    
    for start_marker, end_marker in boilerplate_sections:
        pos = cleaned.find(start_marker)
        if pos != -1:
            removed_sections.append(start_marker)
            if end_marker:
                end_pos = cleaned.find(end_marker, pos + len(start_marker))
                if end_pos != -1:
                    cleaned = cleaned[:pos].rstrip() + cleaned[end_pos:]
                else:
                    cleaned = cleaned[:pos].rstrip()
            else:
                # No end marker - truncate from start marker
                cleaned = cleaned[:pos].rstrip()
    
    return cleaned, removed_sections


def clean_template_basic(template_obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean a single template object from basic JSON files.
    """
    if 'template' not in template_obj:
        return template_obj
    
    original_text = template_obj['template']
    
    # Step 1: Fix braces
    cleaned_text = fix_braces(original_text)
    
    # Step 2: Remove boilerplate footers
    cleaned_text = remove_boilerplate_basic(cleaned_text)
    
    # Step 3: Clean up whitespace
    cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)
    cleaned_text = cleaned_text.strip()
    
    # Create new object with cleaned template
    cleaned_obj = template_obj.copy()
    cleaned_obj['template'] = cleaned_text
    
    return cleaned_obj


def clean_template_comprehensive(template_obj: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Clean a single template object from comprehensive JSON files.
    Returns (cleaned_obj, stats).
    """
    stats = {
        'boilerplate_sections_removed': [],
        'had_truncation_issues': False
    }
    
    if 'template' not in template_obj:
        return template_obj, stats
    
    original_text = template_obj['template']
    
    # Step 1: Fix braces
    cleaned_text = fix_braces(original_text)
    
    # Step 2: Remove comprehensive-specific boilerplate
    cleaned_text, removed = remove_boilerplate_comprehensive(cleaned_text)
    stats['boilerplate_sections_removed'] = removed
    
    # Step 3: Check for truncation issues (templates cut off mid-placeholder)
    # Common truncation patterns
    truncation_indicators = [
        r'\{\{[A-Z_]*$',  # Ends with opening braces
        r'\{\{[A-Z_]+<response',  # Contains truncation marker
        r'MAC \{\{M$',  # Specific pattern seen in data
        r'\{\{M$',  # Incomplete placeholder
    ]
    for pattern in truncation_indicators:
        if re.search(pattern, cleaned_text.rstrip()):
            stats['had_truncation_issues'] = True
            break
    
    # Step 4: Clean up whitespace
    cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)
    cleaned_text = cleaned_text.strip()
    
    # Create new object with cleaned template
    cleaned_obj = template_obj.copy()
    cleaned_obj['template'] = cleaned_text
    
    return cleaned_obj, stats


def detect_file_type(data: List[Dict]) -> str:
    """
    Detect whether the file is 'basic' or 'comprehensive' format.
    """
    if not data or not isinstance(data[0], dict):
        return 'unknown'
    
    fields = set(data[0].keys())
    
    # Comprehensive files have these specific fields
    comprehensive_fields = {'structure_type', 'estimated_word_count', 'pii_count', 'pii_categories_used'}
    basic_fields = {'pii_density', 'tone'}
    
    if comprehensive_fields.issubset(fields):
        return 'comprehensive'
    elif basic_fields.issubset(fields):
        return 'basic'
    else:
        return 'unknown'


def process_file(input_path: Path, output_path: Path) -> Dict[str, Any]:
    """
    Process a single JSON file.
    Returns stats about the processing.
    """
    stats = {
        'templates_processed': 0,
        'templates_with_single_braces': 0,
        'templates_with_boilerplate': 0,
        'templates_with_truncation': 0,
        'file_type': 'unknown',
        'errors': 0
    }
    
    try:
        # Load JSON
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            print(f"Warning: {input_path} does not contain a JSON array. Skipping.")
            return stats
        
        # Detect file type
        file_type = detect_file_type(data)
        stats['file_type'] = file_type
        print(f"  Detected file type: {file_type}")
        
        cleaned_data = []
        
        for item in data:
            try:
                if not isinstance(item, dict):
                    continue
                
                template_text = item.get('template', '')
                
                # Check for single braces
                if re.search(r'(?<!{)\{[A-Z][A-Z_]*\}(?!})', template_text):
                    stats['templates_with_single_braces'] += 1
                
                # Check for boilerplate based on file type
                if file_type == 'basic':
                    if any(phrase in template_text for phrase in [
                        "Zusätzliche Informationen:", 
                        "Bei Rückfragen kontaktieren Sie uns:"
                    ]):
                        stats['templates_with_boilerplate'] += 1
                    cleaned_item = clean_template_basic(item)
                    
                elif file_type == 'comprehensive':
                    if any(phrase in template_text for phrase in [
                        "ERGÄNZENDE INFORMATIONEN:",
                        "Zusatzinfo:",
                        "Kontext:"
                    ]):
                        stats['templates_with_boilerplate'] += 1
                    cleaned_item, item_stats = clean_template_comprehensive(item)
                    if item_stats['had_truncation_issues']:
                        stats['templates_with_truncation'] += 1
                else:
                    # Unknown file type - apply basic cleaning
                    cleaned_item = clean_template_basic(item)
                
                cleaned_data.append(cleaned_item)
                stats['templates_processed'] += 1
                
            except Exception as e:
                print(f"Error processing item in {input_path}: {e}")
                stats['errors'] += 1
                cleaned_data.append(item)
        
        # Save cleaned file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
        
        return stats
        
    except json.JSONDecodeError as e:
        print(f"Error: {input_path} is not valid JSON: {e}")
        stats['errors'] += 1
        return stats
    except Exception as e:
        print(f"Error processing {input_path}: {e}")
        stats['errors'] += 1
        return stats


def main():
    # Configuration
    INPUT_DIR = Path("./templates")  # Directory containing JSON files
    OUTPUT_DIR = Path("./templates_cleaned")  # Output directory
    
    # Check if input directory exists
    if not INPUT_DIR.exists():
        print(f"Error: Input directory '{INPUT_DIR}' does not exist.")
        print("Usage: Place this script in the parent directory of your 'templates' folder")
        print("Or modify INPUT_DIR variable to point to your templates directory")
        sys.exit(1)
    
    # Find all JSON files
    json_files = list(INPUT_DIR.glob("*.json"))
    
    if not json_files:
        print(f"No JSON files found in {INPUT_DIR}")
        sys.exit(1)
    
    print(f"Found {len(json_files)} JSON files to process")
    print(f"Output will be saved to: {OUTPUT_DIR}")
    print("-" * 50)
    
    total_stats = {
        'templates_processed': 0,
        'templates_with_single_braces': 0,
        'templates_with_boilerplate': 0,
        'templates_with_truncation': 0,
        'errors': 0
    }
    
    # Process each file
    for json_file in sorted(json_files):
        output_file = OUTPUT_DIR / json_file.name
        print(f"Processing: {json_file.name}...")
        
        stats = process_file(json_file, output_file)
        
        # Aggregate stats
        for key in total_stats:
            total_stats[key] += stats.get(key, 0)
        
        print(f"  ✓ Processed {stats['templates_processed']} templates ({stats['file_type']})")
        if stats['templates_with_single_braces'] > 0:
            print(f"  ⚠ Fixed {stats['templates_with_single_braces']} templates with single braces")
        if stats['templates_with_boilerplate'] > 0:
            print(f"  ✂ Removed boilerplate from {stats['templates_with_boilerplate']} templates")
        if stats.get('templates_with_truncation', 0) > 0:
            print(f"  ⚠ Found {stats['templates_with_truncation']} templates with potential truncation")
        if stats['errors'] > 0:
            print(f"  ✗ {stats['errors']} errors")
    
    print("-" * 50)
    print("CLEANUP COMPLETE")
    print(f"Total templates processed: {total_stats['templates_processed']}")
    print(f"Templates with brace fixes: {total_stats['templates_with_single_braces']}")
    print(f"Templates with boilerplate removed: {total_stats['templates_with_boilerplate']}")
    print(f"Templates with truncation issues: {total_stats['templates_with_truncation']}")
    print(f"Errors: {total_stats['errors']}")
    print(f"Cleaned files saved to: {OUTPUT_DIR.absolute()}")


if __name__ == "__main__":
    main()
