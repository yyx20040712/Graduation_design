"""OCR processing for Volume 5: 市政管网工程 (Municipal Pipe Network)"""
import os, sys, time, json
import pytesseract, pypdfium2 as pdfium
from pathlib import Path

os.environ['TESSDATA_PREFIX'] = r'C:\Users\Administrator\tessdata'
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

vol_path = Path(r'D:\python_code\Graduation_design\docs\2019年版黑龙江省市政工程消耗量定额--第五册：市政管网工程')
output_dir = Path(r'D:\python_code\Graduation_design\.sisyphus\notepads\pdf-knowledge\ocr_output\vol5_市政管网工程')
output_dir.mkdir(parents=True, exist_ok=True)

pdf_files = sorted(vol_path.glob('*.pdf'))
print(f'Found {len(pdf_files)} PDFs')

total_start = time.time()
all_meta = []

for pdf_path in pdf_files:
    pdf_name = pdf_path.stem
    print(f'\n--- {pdf_path.name} ---')
    pdf = pdfium.PdfDocument(str(pdf_path))
    total = len(pdf)
    pages_text = []
    start = time.time()
    
    for i in range(total):
        bitmap = pdf[i].render(scale=2.5)
        text = pytesseract.image_to_string(bitmap.to_pil(), lang='chi_sim')
        pages_text.append(text)
        
        elapsed = time.time() - start
        rate = (i+1) / elapsed * 60 if elapsed > 0 else 0
        eta_min = (total - i - 1) / rate if rate > 0 else 0
        
        if (i+1) % 10 == 0 or i == total-1:
            eta_str = f"{eta_min:.1f}min" 
            print(f'  {i+1}/{total} | {len(text)}c | {rate:.0f}p/min | ETA {eta_str}')
    
    # Save per-page
    pdf_out = output_dir / pdf_name
    pdf_out.mkdir(exist_ok=True)
    for i, text in enumerate(pages_text):
        with open(pdf_out / 'page_{:04d}.txt'.format(i+1), 'w', encoding='utf-8') as f:
            f.write(text)
    
    # Save combined
    with open(pdf_out / '_combined.txt', 'w', encoding='utf-8') as f:
        for i, text in enumerate(pages_text):
            f.write('\n{}\nPAGE {}\n{}\n{}\n'.format('='*60, i+1, '='*60, text))
    
    dt = time.time() - start
    meta = {
        'file': pdf_path.name,
        'pages': total,
        'time_sec': dt,
        'chars': sum(len(t) for t in pages_text),
        'non_empty': sum(1 for t in pages_text if len(t) > 20)
    }
    all_meta.append(meta)
    print(f'  Done: {dt/60:.1f}min | {meta["non_empty"]}/{total} pages with text')

# Summary
total_pages = sum(m['pages'] for m in all_meta)
total_time = time.time() - total_start
print('\n===== VOLUME 5 SUMMARY =====')
print('Files: {} | Pages: {} | Time: {:.1f}min'.format(len(all_meta), total_pages, total_time/60))
print('Rate: {:.0f} pages/min'.format(total_pages/total_time*60))

with open(output_dir / '_summary.json', 'w', encoding='utf-8') as f:
    json.dump(all_meta, f, ensure_ascii=False, indent=2)
print('Summary saved to _summary.json')
