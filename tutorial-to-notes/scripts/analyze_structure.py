"""Phase A: Analyze process file and output chapter section structure report.
Scans the process .md file and outputs:
1. Section → page range mapping
2. Subsection listing per section
3. Image assignment per section (by page position)
"""
import re, sys, json
from collections import OrderedDict

def parse_process_file(filepath):
    """Parse the process .md into a list of page entries."""
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    pages = []
    # Split by page markers
    chunks = re.split(r'^## 第(\d+)页\s*$', text, flags=re.MULTILINE)
    # chunks[0] is preface (may be empty or contain chapter title), then alternating page_number, content
    if len(chunks) > 1:
        # Skip preface if it's not a page number
        first = chunks[0].strip()
        if first == '' or first.startswith('#'):
            chunks = chunks[1:]
    i = 0
    while i < len(chunks) - 1:
        page_num = int(chunks[i].strip())
        content = chunks[i+1]
        pages.append(parse_page(page_num, content))
        i += 2
    return pages

def parse_page(page_num, content):
    """Parse a single page's content into text blocks and images."""
    entry = {'page': page_num, 'texts': [], 'images': []}

    # Split by sections
    sections = re.split(r'^### (文本|图片\d+)\s*$', content, flags=re.MULTILINE)
    # sections[0] is preface, then alternating type, content
    if sections and sections[0].strip() in ('', '\n'):
        sections = sections[1:]
    i = 0
    while i < len(sections) - 1:
        stype = sections[i].strip()
        scontent = sections[i+1].strip()
        if stype == '文本':
            # Extract all text lines
            lines = []
            for line in scontent.split('\n'):
                line = line.strip()
                if line and not line.startswith('状态:') and not line.startswith('类型:') and not line.startswith('内容描述:') and not line.startswith('保留判定:'):
                    lines.append(line)
            entry['texts'] = lines
        elif stype.startswith('图片'):
            img_match = re.search(r'!\[IMG:([^\]]+)\]\(([^)]+)\)', scontent)
            if img_match:
                entry['images'].append({
                    'filename': os.path.basename(img_match.group(2)),  # real filename from path
                    'path': img_match.group(2),
                    'alt_text': img_match.group(1).replace('IMG:', ''),  # descriptive alt text
                    'status': extract_field(scontent, '状态:'),
                    'ocr': extract_field(scontent, '内容描述:'),
                    'keep': extract_field(scontent, '保留判定:'),
                })
        i += 2
    return entry

import os

def extract_field(text, field):
    m = re.search(re.escape(field) + r'\s*(.*?)(?:\n|$)', text)
    return m.group(1).strip() if m else ''

# == Detect section structure ==

def find_section_headers(pages):
    """Find pages that define section/subsection hierarchy."""
    headers = []
    for p in pages:
        for t in p['texts']:
            t = t.strip()
            # Match patterns like "5.1" or "5.1.1" at start of line
            m = re.match(r'^(\d+\.\d+(?:\.\d+)?)\s+(.*)', t)
            if m:
                num, name = m.group(1), m.group(2)
                # Skip if it's just a bare number reference
                if not name.strip():
                    continue
                headers.append({'page': p['page'], 'num': num, 'name': name, 'text': t})
                # Don't break — capture ALL headers on this page (TOC pages list multiple subsections)
    return headers

def infer_section_ranges(pages, headers):
    """Infer page ranges for each section level."""
    # Filter to just unique first-occurrence section headers for each number
    seen = set()
    uniq_h = []
    for h in headers:
        if h['num'] not in seen:
            seen.add(h['num'])
            uniq_h.append(h)

    # Detect the chapter number dynamically from the headers
    if not uniq_h:
        return [], []
    
    # Find the root chapter number (e.g., "5" from "5.1")
    # First header is typically the top-level section number
    first_num = uniq_h[0]['num']
    chapter_prefix = first_num.split('.')[0] + '.'
    
    chapter_headers = [h for h in uniq_h if h['num'].startswith(chapter_prefix)]
    
    # Top-level sections (5.1, 5.2, etc.)
    top = [h for h in chapter_headers if len(h['num'].split('.')) == 2]
    # Subsections (5.1.1, 5.1.2, etc.)
    subs = [h for h in chapter_headers if len(h['num'].split('.')) == 3]

    return top, subs

# == Main ==

def generate_report(filepath):
    pages = parse_process_file(filepath)
    headers = find_section_headers(pages)
    top_sections, subsections = infer_section_ranges(pages, headers)

    report = []
    report.append(f"文件: {os.path.basename(filepath)}")
    report.append(f"总页数: {len(pages)}")
    report.append(f"")

    # Build image-by-page map
    page_images = {}
    for p in pages:
        if p['images']:
            page_images[p['page']] = p['images']

    # Report each top-level section
    for i, sec in enumerate(top_sections):
        sec_num = sec['num']
        sec_name = sec['name']
        
        # Find page range for this section
        next_page = pages[-1]['page'] + 1
        if i + 1 < len(top_sections):
            # Find the first content page of next section
            next_sec = top_sections[i+1]
            # The next section's header page is its start
            next_page = next_sec['page']
        
        report.append(f"=== {sec_num} {sec_name}  (p.{sec['page']}-p.{next_page-1}) ===")
        
        # Find subsections within this range
        local_subs = [s for s in subsections 
                       if s['num'].startswith(sec_num) and s['page'] >= sec['page'] and s['page'] < next_page]
        if local_subs:
            for s in local_subs:
                # find sub end: next subsection or section end
                s_next = next_page
                for j, ss in enumerate(local_subs):
                    if ss['page'] > s['page']:
                        s_next = ss['page']
                        break
                
                report.append(f"  {s['num']} {s['name']} (p.{s['page']}-p.{s_next-1})")
                
                # Assign images from pages within this subsection range
                sub_pages = sorted([k for k in page_images.keys() if k >= s['page'] and k < s_next])
                if sub_pages:
                    for sp in sub_pages:
                        for img in page_images[sp]:
                            keep = img.get('keep', '')
                            report.append(f"    ├─ p{sp} {img['filename']}  [keep={keep}]")
        
        # Assign images that fall in the section but not in any subsection
        # (section-level images)
        top_pages = sorted([k for k in page_images.keys() 
                           if k >= sec['page'] and k < next_page])
        # Remove those already assigned to subsections
        sub_page_set = set()
        for s in local_subs:
            s_next = next_page
            for j, ss in enumerate(local_subs):
                if ss['page'] > s['page']:
                    s_next = ss['page']
                    break
            sub_page_set.update(range(s['page'], s_next))
        
        unassigned_pages = [p for p in top_pages if p not in sub_page_set]
        if unassigned_pages:
            for sp in unassigned_pages:
                for img in page_images[sp]:
                    keep = img.get('keep', '')
                    report.append(f"    ├─ p{sp} {img['filename']}  [keep={keep}]  ← section level")
        
        report.append("")

    return '\n'.join(report)

if __name__ == '__main__':
    fpath = sys.argv[1] if len(sys.argv) > 1 else '/root/.hermes/笔记过程/数据库/第7章-过程.md'
    report = generate_report(fpath)
    print(report)
    # Also save to file
    outpath = fpath.replace('-过程.md', '-结构分析.txt')
    with open(outpath, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n[已保存] {outpath}")
