#!/usr/bin/env python3
"""Batch process all '待理解' images in a process markdown file using Doubao vision.

Usage:
  python3 batch_vision.py <process_file.md> [--concurrent N]

Reads the process file, finds all images with '状态: 待理解',
calls vision_analyze_doubao.py on each, and writes back the analysis.

Set DOUBAO_API_KEY environment variable before running.
"""

import os
import sys
import re
import subprocess
import tempfile

VISION_SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'vision_analyze_doubao.py'
)


def parse_process_file(path):
    """Return list of (page_section, image_line_index) where status is 待理解."""
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    targets = []
    for i, line in enumerate(lines):
        if line.strip() == '状态: 待理解':
            # Find the image line (the one with ![IMG:...] before this line)
            for j in range(i - 1, max(i - 10, -1), -1):
                if lines[j].strip().startswith('!['):
                    # Extract image path from markdown image syntax
                    m = re.search(r'\]\(([^)]+)\)', lines[j])
                    if m:
                        img_path = m.group(1)
                        targets.append({
                            'img_path': img_path,
                            'status_line_idx': i,
                            'section_start': None
                        })
                    break
    return targets, lines


def analyze_image(img_path, script_path, timeout=120):
    """Run vision_analyze_doubao.py on an image, return stdout text."""
    result = subprocess.run(
        ['python3', script_path, img_path],
        capture_output=True, text=True, timeout=timeout
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def parse_vision_output(text):
    """Parse the vision output into structured fields."""
    lines = text.strip().split('\n')
    img_type = ''
    description = ''
    keep_rating = 'C'
    
    for line in lines:
        line_lower = line.lower()
        if line.startswith('###') or '图的类型' in line or '类型选项' in line_lower:
            # Extract type from next meaningful line
            pass
        elif '类型：' in line or '类型:' in line:
            m = re.search(r'类型[：:]\s*(.+)', line)
            if m:
                img_type = m.group(1).strip()
        elif 'A-' in line or 'B-' in line or 'C-' in line:
            m = re.search(r'([ABC])-', line)
            if m:
                keep_rating = m.group(1)
    
    # Try to find type from first meaningful non-header line
    if not img_type:
        for line in lines:
            cleaned = line.strip().rstrip('：').rstrip(':').strip()
            if cleaned in ('公式', '文字段落', '流程图', '对比/分类表', '架构图', '示例图', '代码截图', '装饰性'):
                img_type = cleaned
                break
    
    description = text.strip()
    
    return {
        'type': img_type if img_type else '其他',
        'description': description,
        'keep': keep_rating
    }


def write_back(path, lines, status_idx, analysis):
    """Write vision analysis result back into the process file lines."""
    indent = ' ' * 0
    # Insert after the status line (replace it)
    lines[status_idx] = indent + '状态: 已理解\n'
    
    # Find where to insert additional info
    insert_pos = status_idx + 1
    # Remove any existing analysis lines for this image
    while insert_pos < len(lines) and any(lines[insert_pos].startswith(prefix) for prefix in 
          ['类型:', '内容描述:', '保留判定:', '类型：', '内容描述：', '保留判定：']):
        lines.pop(insert_pos)
    
    # Insert new analysis lines
    lines.insert(insert_pos, indent + '类型: ' + analysis['type'] + '\n')
    lines.insert(insert_pos + 1, indent + '内容描述: ' + analysis['description'].replace('\n', ' | ') + '\n')
    lines.insert(insert_pos + 2, indent + '保留判定: ' + analysis['keep'] + '\n')


def main():
    if len(sys.argv) < 2:
        print('Usage: python3 batch_vision.py <process_file.md>', file=sys.stderr)
        sys.exit(1)
    
    if not os.environ.get('DOUBAO_API_KEY'):
        print('Error: DOUBAO_API_KEY environment variable not set', file=sys.stderr)
        sys.exit(1)
    
    if not os.path.exists(VISION_SCRIPT):
        print('Error: vision_analyze_doubao.py not found at: ' + VISION_SCRIPT, file=sys.stderr)
        sys.exit(1)
    
    proc_path = sys.argv[1]
    
    targets, lines = parse_process_file(proc_path)
    
    if not targets:
        print('No 待理解 images found in: ' + proc_path)
        return
    
    total = len(targets)
    success = 0
    skipped = 0
    
    for idx, t in enumerate(targets):
        img_path = t['img_path']
        if not os.path.exists(img_path):
            print(f'  [{idx+1}/{total}] SKIP (not found): {os.path.basename(img_path)}')
            # Mark as skipped
            lines[t['status_line_idx']] = '状态: 已跳过（文件不存在）\n'
            skipped += 1
            continue
        
        print(f'  [{idx+1}/{total}] Analyzing: {os.path.basename(img_path)} ({os.path.getsize(img_path)/1024:.0f}KB)...', end=' ', flush=True)
        
        try:
            result_text = analyze_image(img_path, VISION_SCRIPT)
            analysis = parse_vision_output(result_text)
            write_back(proc_path, lines, t['status_line_idx'], analysis)
            print(f'-> {analysis["type"]} ({analysis["keep"]})')
            success += 1
        except Exception as e:
            print(f'-> FAILED: {str(e)[:60]}')
            lines[t['status_line_idx']] = '状态: 理解失败\n'
            skipped += 1
    
    # Write updated process file
    with open(proc_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print(f'\nDone: {success} analyzed, {skipped} skipped/failed out of {total}')


if __name__ == '__main__':
    main()
