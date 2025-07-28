import fitz  # PyMuPDF
import statistics
from collections import Counter
import re

def _clean_text(text):
    """
    Cleans and normalizes a line of text.
    - Removes leading/trailing whitespace.
    - Replaces multiple spaces with a single space.
    """
    return re.sub(r'\s+', ' ', text).strip()

def _merge_text_blocks(blocks):
    """
    Merges horizontally adjacent text blocks into coherent lines.
    """
    if not blocks:
        return []

    blocks.sort(key=lambda b: (b['bbox'][1], b['bbox'][0]))

    merged_lines = []
    current_line_spans = []
    
    y_tolerance = 2.0 
    x_gap_tolerance = 20.0

    for block in blocks:
        if "lines" not in block:
            continue

        for line in block["lines"]:
            if line["dir"] != (1, 0):
                continue
                
            if not current_line_spans:
                current_line_spans.extend(line['spans'])
                continue

            last_span = current_line_spans[-1]
            current_span = line['spans'][0]
            
            is_on_same_line = abs(current_span['bbox'][1] - last_span['bbox'][1]) <= y_tolerance
            
            if is_on_same_line:
                horizontal_gap = current_span['bbox'][0] - last_span['bbox'][2]
                if horizontal_gap < x_gap_tolerance:
                    current_line_spans.extend(line['spans'])
                else:
                    current_line_spans.sort(key=lambda s: s['bbox'][0])
                    merged_lines.append(current_line_spans)
                    current_line_spans = line['spans']
            else:
                if current_line_spans:
                    current_line_spans.sort(key=lambda s: s['bbox'][0])
                    merged_lines.append(current_line_spans)
                current_line_spans = line['spans']

    if current_line_spans:
        current_line_spans.sort(key=lambda s: s['bbox'][0])
        merged_lines.append(current_line_spans)

    final_lines = []
    for spans in merged_lines:
        if not spans:
            continue
        
        line_text = "".join([span["text"] for span in spans])
        cleaned_text = _clean_text(line_text)
        
        if cleaned_text:
            font_sizes = [s["size"] for s in spans]
            font_names = [s["font"] for s in spans]
            
            final_lines.append({
                "text": cleaned_text,
                "font_size": statistics.mean(font_sizes) if font_sizes else 0,
                "font_name": Counter(font_names).most_common(1)[0][0] if font_names else "",
                "bbox": (
                    min(s['bbox'][0] for s in spans),
                    min(s['bbox'][1] for s in spans),
                    max(s['bbox'][2] for s in spans),
                    max(s['bbox'][3] for s in spans)
                )
            })
            
    return final_lines

def _calculate_heading_score(line, body_text_size, body_text_font):
    """
    Calculates a score indicating how likely a line is to be a heading.
    Points are awarded for boldness, larger font size, and being all-caps.
    """
    score = 0
    font_name = line["font_name"].lower()
    
    # Points for being bold
    if "bold" in font_name or "black" in font_name or "heavy" in font_name:
        score += 2
        
    # Points for font size relative to body text
    if line["font_size"] > body_text_size * 1.15:
        score += 2
    if line["font_size"] > body_text_size * 1.4:
        score += 1 # Extra point for being much larger

    # Points for being all-caps (and having at least one letter)
    if line["text"].isupper() and any(c.isalpha() for c in line["text"]):
        score += 1
        
    # Penalize lines that are likely body text
    is_not_a_sentence = not line["text"].endswith('.')
    is_not_a_label = not line["text"].strip().endswith(':')
    if not is_not_a_sentence or not is_not_a_label:
        score -= 2

    # Penalize lines that look like list items
    if re.match(r'^\d+\.\s', line['text']):
        score = 0

    return score

def process_pdf_file(pdf_path):
    """
    Processes a single PDF file to extract its title and hierarchical outline
    using a multi-factor scoring system for accuracy.
    """
    doc = fitz.open(pdf_path)
    all_lines = []
    
    # Step 1: Extract, merge, and clean all text lines from each page.
    for page_num, page in enumerate(doc):
        page_height = page.rect.height
        
        raw_blocks = page.get_text("dict")["blocks"]
        reconstructed_lines = _merge_text_blocks(raw_blocks)

        for line in reconstructed_lines:
            y0 = line["bbox"][1]
            # A more lenient header/footer filter
            if page_height * 0.08 < y0 < page_height * 0.92:
                line_data = line.copy()
                line_data["page"] = page_num
                line_data["y0"] = y0
                all_lines.append(line_data)

    if not all_lines:
        return {"title": "", "outline": []}

    # Step 2: Find the most common body text style.
    font_styles = [(round(line["font_size"]), line["font_name"]) for line in all_lines if any(c.isalpha() for c in line['text'])]
    if not font_styles:
        return {"title": all_lines[0]['text'] if all_lines else "", "outline": []}
        
    most_common_style = Counter(font_styles).most_common(1)[0][0]
    body_text_size = most_common_style[0]
    body_text_font = most_common_style[1]

    # Step 3: Score all lines to identify potential headings.
    HEADING_SCORE_THRESHOLD = 2 # A line needs at least this score to be a heading
    for line in all_lines:
        line['score'] = _calculate_heading_score(line, body_text_size, body_text_font)

    potential_headings = [line for line in all_lines if line['score'] >= HEADING_SCORE_THRESHOLD and len(line['text']) < 200]

    if not potential_headings:
        # Fallback if no headings are found
        first_page_lines = sorted([l for l in all_lines if l['page'] == 0], key=lambda x: x['font_size'], reverse=True)
        title = first_page_lines[0]['text'] if first_page_lines else ""
        return {"title": title, "outline": []}
    
    # Step 4: Extract the title. The title has the highest score on the first page.
    title_line = None
    first_page_headings = [h for h in potential_headings if h["page"] == 0]
    
    if first_page_headings:
        title_line = max(first_page_headings, key=lambda x: x["score"])
    
    if title_line:
        title_text = title_line["text"]
        headings = [h for h in potential_headings if h != title_line]
    else:
        # If no headings on page 1, take the largest text as a potential title.
        first_page_lines = sorted([l for l in all_lines if l['page'] == 0], key=lambda x: x['font_size'], reverse=True)
        title_text = first_page_lines[0]['text'] if first_page_lines else ""
        headings = potential_headings

    # Step 5: Classify remaining headings by font size.
    heading_font_sizes = sorted(list(set([round(h["font_size"]) for h in headings])), reverse=True)
    
    size_to_level_map = {}
    for i, size in enumerate(heading_font_sizes):
        if i < 6:
            size_to_level_map[size] = f"H{i + 1}"

    outline = []
    for h in headings:
        rounded_size = round(h["font_size"])
        if rounded_size in size_to_level_map:
            outline.append({
                "level": size_to_level_map[rounded_size],
                "text": h["text"],
                "page": h["page"],
                "y0": h["y0"]
            })
            
    # Step 6: Sort the final outline.
    outline.sort(key=lambda x: (x["page"], x["y0"]))

    # Step 7: Handle documents with only a single heading (like posters/invitations).
    if title_text and not outline:
        outline.append({
            "level": "H1",
            "text": title_text,
            "page": title_line['page'] if title_line else 0
        })
        title_text = ""

    # Clean up the final outline by removing temporary keys
    for item in outline:
        if 'y0' in item:
            del item['y0']

    return {
        "title": title_text,
        "outline": outline
    }
