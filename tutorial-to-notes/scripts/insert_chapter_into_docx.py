#!/usr/bin/env python3
"""Insert chapter content into an existing notes docx at the correct position.

Usage via stdin:
  python3 insert_chapter_into_docx.py <docx_path> <new_chapter_title>

Stdin format (one line per paragraph):
  h1|第10章 关系数据库系统的查询处理
  h2|10.1 查询处理
  h3|选择操作的实现
  body|全表扫描：小表简单有效
  body:2|二级缩进内容

Line prefixes:
  h1       = Heading 1 (chapter title, centered, bold, 18pt)
  h2       = Heading 2 (section title, left, bold, 15pt)
  h3       = Heading 3 (subsection, left, bold, 13pt)
  body     = Body text with 1-level indent (12pt)
  body:N   = Body text with N-level indent (N * 0.75cm)
"""

import sys, re
from docx import Document
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml
from lxml import etree

NS = nsdecls("w")

def esc(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def make_p(text, align_center=False, indent_cm=0, font_size=12, bold=False):
    safe = esc(text)
    xml = '<w:p ' + NS + '>'
    xml += '<w:pPr>'
    xml += '<w:jc w:val="' + ('center' if align_center else 'left') + '"/>'
    if indent_cm > 0:
        xml += '<w:ind w:left="' + str(int(indent_cm * 567)) + '"/>'
    xml += '<w:spacing w:before="0" w:after="0" w:line="360" w:lineRule="auto"/>'
    xml += '</w:pPr><w:r><w:rPr>'
    xml += '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="宋体"/>'
    xml += '<w:sz w:val="' + str(font_size * 2) + '"/>'
    xml += '<w:szCs w:val="' + str(font_size * 2) + '"/>'
    if bold:
        xml += '<w:b/>'
    xml += '</w:rPr><w:t xml:space="preserve">' + safe + '</w:t></w:r></w:p>'
    return parse_xml(xml)

def parse_stdin():
    """Parse stdin lines into paragraph XML elements."""
    paras = []
    for line in sys.stdin:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '|' not in line:
            continue
        prefix, text = line.split('|', 1)
        prefix = prefix.strip()
        text = text.strip()
        if prefix == 'h1':
            paras.append(make_p(text, True, 0, 18, True))
        elif prefix == 'h2':
            paras.append(make_p(text, False, 0, 15, True))
        elif prefix == 'h3':
            paras.append(make_p(text, False, 0.75, 13, True))
        elif prefix.startswith('body'):
            indent = 1
            if ':' in prefix:
                indent = int(prefix.split(':')[1])
            paras.append(make_p(text, False, 0.75 * indent, 12, False))
    return paras

def extract_chapter_num(text):
    """Extract chapter number from text like '第10章...' or 'Chapter 5...'."""
    m = re.search(r'第(\d+)章', text)
    if m:
        return int(m.group(1))
    m = re.search(r'Chapter\s+(\d+)', text, re.I)
    if m:
        return int(m.group(1))
    return None

def find_insert_position(body_elem, new_chapter_num):
    """Find the paragraph element before which to insert. Returns (ref_elem, 'prepend'|'append'|'insert_before')."""
    chapter_paras = []  # (element, chapter_num, text)
    
    for child in body_elem:
        if etree.QName(child).localname != 'p':
            continue
        texts = ''.join(t.text or '' for t in child.iter(qn('w:t')))
        num = extract_chapter_num(texts)
        if num is not None:
            chapter_paras.append((child, num, texts))
    
    if not chapter_paras:
        return None, 'append'
    
    # Find where new chapter belongs
    for i, (elem, num, _) in enumerate(chapter_paras):
        if new_chapter_num < num:
            return elem, 'insert_before'
        elif new_chapter_num == num:
            return elem, 'after_existing'
    
    return None, 'append'

def main():
    if len(sys.argv) < 2:
        print('Usage: cat content.txt | python3 insert_chapter_into_docx.py <docx_path>', file=sys.stderr)
        sys.exit(1)
    
    docx_path = sys.argv[1]
    doc = Document(docx_path)
    body_elem = doc.element.body
    
    new_paras = parse_stdin()
    if not new_paras:
        print('No content read from stdin', file=sys.stderr)
        sys.exit(1)
    
    # Get chapter number from first h1
    first_h1_texts = []
    for p in new_paras:
        texts = ''.join(t.text or '' for t in p.iter(qn('w:t')))
        if texts:
            first_h1_texts = texts
            break
    
    new_num = extract_chapter_num(first_h1_texts) if first_h1_texts else None
    
    if new_num is None:
        # Can't determine chapter number, append
        for p in new_paras:
            body_elem.append(p)
        print('Appended (no chapter number detected)', file=sys.stderr)
    else:
        ref, action = find_insert_position(body_elem, new_num)
        if action == 'append' or ref is None:
            for p in new_paras:
                body_elem.append(p)
            print(f'Appended chapter {new_num} to end', file=sys.stderr)
        elif action == 'insert_before':
            for p in new_paras:
                ref.addprevious(p)
            print(f'Inserted chapter {new_num} before existing chapter', file=sys.stderr)
        elif action == 'after_existing':
            # Insert after the matching chapter's last paragraph
            # Find where the matching chapter ends (next chapter or end of doc)
            next_sibling = ref.getnext()
            while next_sibling is not None:
                ntexts = ''.join(t.text or '' for t in next_sibling.iter(qn('w:t')))
                if extract_chapter_num(ntexts) is not None and extract_chapter_num(ntexts) != new_num:
                    break
                next_sibling = next_sibling.getnext()
            
            if next_sibling is not None:
                for p in new_paras:
                    next_sibling.addprevious(p)
            else:
                for p in new_paras:
                    body_elem.append(p)
            print(f'Appended to existing chapter {new_num}', file=sys.stderr)
    
    doc.save(docx_path)
    print(f'Saved: {docx_path}', file=sys.stderr)

if __name__ == '__main__':
    main()
