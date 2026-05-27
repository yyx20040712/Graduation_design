"""
OCR Pipeline for 2019 Heilongjiang Municipal Engineering Consumption Quota PDFs.
Processes scanned PDFs using Tesseract OCR (chi_sim) and saves raw text.
"""
import os
import sys
import re
import json
import time
import pytesseract
import pypdfium2 as pdfium
from pathlib import Path

# === CONFIGURATION ===
os.environ['TESSDATA_PREFIX'] = r'C:\Users\Administrator\tessdata'
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

DOCS_DIR = Path(r'D:\python_code\Graduation_design\docs')
OUTPUT_DIR = Path(r'D:\python_code\Graduation_design\.sisyphus\notepads\pdf-knowledge\ocr_output')
SCALE = 2.5  # Render scale for OCR quality
LANG = 'chi_sim'  # Chinese simplified


def ocr_page(page, page_num):
    """OCR a single PDF page, return text."""
    try:
        bitmap = page.render(scale=SCALE)
        pil_image = bitmap.to_pil()
        text = pytesseract.image_to_string(pil_image, lang=LANG)
        return text.strip()
    except Exception as e:
        return f"[OCR ERROR on page {page_num}: {e}]"


def process_pdf(pdf_path, output_dir):
    """Process a single PDF file, save OCR text per page."""
    pdf_name = pdf_path.stem
    pdf_output_dir = output_dir / pdf_name
    pdf_output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Processing: {pdf_path.name}")
    pdf = pdfium.PdfDocument(str(pdf_path))
    total_pages = len(pdf)
    print(f"Total pages: {total_pages}")

    all_text = []
    start_time = time.time()

    for i in range(total_pages):
        page_text = ocr_page(pdf[i], i + 1)
        all_text.append(page_text)

        # Save individual page
        page_file = pdf_output_dir / f"page_{i+1:04d}.txt"
        with open(page_file, 'w', encoding='utf-8') as f:
            f.write(page_text)

        elapsed = time.time() - start_time
        pages_done = i + 1
        rate = pages_done / elapsed if elapsed > 0 else 0
        eta = (total_pages - pages_done) / rate if rate > 0 else 0

        if (i + 1) % 10 == 0 or i == 0 or i == total_pages - 1:
            print(f"  Page {i+1}/{total_pages} | "
                  f"Chars: {len(page_text)} | "
                  f"Rate: {rate:.1f} p/min | "
                  f"ETA: {eta/60:.1f} min")

    # Save combined text
    combined_file = pdf_output_dir / "_combined.txt"
    with open(combined_file, 'w', encoding='utf-8') as f:
        for i, text in enumerate(all_text):
            f.write(f"\n{'='*60}\n")
            f.write(f"PAGE {i+1}\n")
            f.write(f"{'='*60}\n")
            f.write(text + "\n")

    total_time = time.time() - start_time
    print(f"Complete! {total_pages} pages in {total_time/60:.1f} min "
          f"({total_pages/total_time*60:.1f} pages/min)")

    # Save metadata
    meta = {
        'pdf_name': pdf_path.name,
        'total_pages': total_pages,
        'processing_time_seconds': total_time,
        'chars_total': sum(len(t) for t in all_text),
        'non_empty_pages': sum(1 for t in all_text if len(t) > 20),
    }
    with open(pdf_output_dir / "_metadata.json", 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return meta


def process_volume(volume_dir_name, output_dir):
    """Process all PDFs in a volume directory."""
    volume_path = DOCS_DIR / volume_dir_name
    if not volume_path.exists():
        print(f"Volume not found: {volume_path}")
        return []

    pdf_files = sorted(volume_path.glob("*.pdf"))
    print(f"\n{'#'*60}")
    print(f"VOLUME: {volume_dir_name}")
    print(f"Files: {len(pdf_files)}")
    print(f"{'#'*60}")

    results = []
    for pdf_file in pdf_files:
        meta = process_pdf(pdf_file, output_dir)
        results.append(meta)

    # Volume summary
    total_pages = sum(r['total_pages'] for r in results)
    total_chars = sum(r['chars_total'] for r in results)
    total_time = sum(r['processing_time_seconds'] for r in results)
    print(f"\nVolume Summary: {total_pages} pages, {total_chars} chars, {total_time/60:.1f} min")

    return results


def main():
    """Main processing pipeline."""
    # Define volumes to process
    volumes = [
        # Priority 1: Most relevant to drainage pipe project
        "2019年版黑龙江省市政工程消耗量定额--第五册：市政管网工程",

        # Priority 2: General municipal works
        ("2019年版黑龙江省市政工程消耗量定额--第一册：土石方工程 "
         "第二册：道路工程 第三册：桥涵工程 第四册：隧道工程"),

        # Priority 3: Water treatment and other ancillary
        ("2019年版黑龙江省市政工程消耗量定额--第六册水处理工程 "
         "第七册：生活垃圾处理工程 第八册：路灯工程 "
         "第九册：钢筋工程  第十册：拆除工程 第十一册 措施项目"),
    ]

    all_meta = {}
    for vol in volumes:
        vol_name_short = vol.split('--')[-1].strip() if '--' in vol else vol
        print(f"\n{'*'*60}")
        print(f"Starting: {vol_name_short}")
        print(f"{'*'*60}")
        results = process_volume(vol, OUTPUT_DIR)
        all_meta[vol_name_short] = results

    # Save overall summary
    summary_file = OUTPUT_DIR / "_pipeline_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(all_meta, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"PIPELINE COMPLETE")
    print(f"Summary saved to: {summary_file}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
