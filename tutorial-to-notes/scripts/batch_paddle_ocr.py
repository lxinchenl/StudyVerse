#!/usr/bin/env python3
"""Batch OCR all images in a process file using PaddleOCR.

Usage:
  python3 batch_paddle_ocr.py <process_file.md>

Reads the process file, finds all images with '状态: 待理解',
runs PaddleOCR on each, and writes back the recognized text.

For images with no text detected: marks as '装饰性' (skip).
For images with text: writes as OCR result + marks as A (keep).
"""

import os, sys, re, warnings
warnings.filterwarnings('ignore')
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
os.environ['OMP_NUM_THREADS'] = '1'

from paddleocr import PaddleOCR


def main():
    if len(sys.argv) < 2:
        print('Usage: python3 batch_paddle_ocr.py <process_file.md>', file=sys.stderr)
        sys.exit(1)

    proc_path = sys.argv[1]
    if not os.path.exists(proc_path):
        print('File not found: ' + proc_path, file=sys.stderr)
        sys.exit(1)

    # Initialize OCR once
    print('Initializing PaddleOCR...', file=sys.stderr)
    ocr = PaddleOCR(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        engine="paddle",
    )

    # Read process file
    with open(proc_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find all image entries with status "待理解"
    # Pattern: find image lines followed by status lines
    lines = content.split('\n')
    modified = False
    i = 0
    total_images = 0
    processed = 0

    while i < len(lines):
        line = lines[i]
        # Look for image placeholder line
        if line.startswith('!['):
            img_path = None
            m = re.search(r'\]\(([^)]+)\)', line)
            if m:
                img_path = m.group(1)

            # Find the status line after this image
            status_idx = -1
            for j in range(i + 1, min(i + 5, len(lines))):
                if lines[j].strip().startswith('状态:'):
                    status = lines[j].strip().split(':', 1)[1].strip()
                    if status == '待理解':
                        status_idx = j
                    break

            if img_path and status_idx >= 0 and os.path.exists(img_path):
                total_images += 1
                fsize = os.path.getsize(img_path)

                # 所有图片都处理，不跳过大图。若外部 SIGTERM 中断，实时保存确保最多丢一张。
                print(f'  OCR [{total_images}] {os.path.basename(img_path)} ({fsize/1024:.0f}KB)...', end=' ', flush=True)

                try:
                    result = ocr.predict(img_path)
                    texts = []
                    for res in result:
                        ts = res.get('rec_texts', [])
                        if ts:
                            texts.extend(ts)

                    # Remove any existing type/description/keep lines after status
                    remove_end = status_idx + 1
                    while remove_end < len(lines) and any(
                        lines[remove_end].startswith(p) for p in ['类型:', '内容描述:', '保留判定:', '类型：', '内容描述：', '保留判定：']):
                        lines.pop(remove_end)

                    if texts:
                        ocr_text = '\n'.join(texts)
                        print(f'→ {len(texts)}行文字')
                        lines[status_idx] = '状态: 已理解'
                        lines.insert(remove_end, '类型: OCR文字')
                        lines.insert(remove_end + 1, '内容描述: ' + ocr_text.replace('\n', ' | '))
                        lines.insert(remove_end + 2, '保留判定: A')
                        processed += 1
                    else:
                        print('→ 无文字（跳过）')
                        lines[status_idx] = '状态: 跳过（无文字）'
                        lines.insert(remove_end, '类型: 装饰性')
                        lines.insert(remove_end + 1, '内容描述: (OCR未识别到文字)')
                        lines.insert(remove_end + 2, '保留判定: C')

                except Exception as e:
                    print(f'→ FAILED: {str(e)[:60]}')
                    lines[status_idx] = '状态: 理解失败'

                # 🔴 CRITICAL: save after EVERY image so timeout/crash doesn't lose progress
                _do_save(proc_path, lines)
        i += 1

    print(f'\nDone: {processed}/{total_images} images processed')


def _do_save(proc_path, lines):
    """Incremental save — called after every image so timeout/crash loses at most one image."""
    with open(proc_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


if __name__ == '__main__':
    main()
