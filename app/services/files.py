import json
import subprocess
import sys
from pathlib import Path
from app.core.errors import AppError
from app.core.config import MAX_BYTES

def extract(filename, data):
    if not data or len(data) > MAX_BYTES:
        raise AppError(413, 'file_size', 'Upload must contain 1 byte to 2 MiB.')
    suffix = Path(filename or '').suffix.lower()
    try:
        if suffix in {'.md', '.txt'}:
            if b'\x00' in data:
                raise ValueError('binary file')
            text = data.decode('utf-8-sig')
        elif suffix == '.pdf':
            if not data.startswith(b'%PDF-'):
                raise ValueError('invalid PDF signature')
            process = subprocess.run([sys.executable, '-m', 'app.services.pdf_worker'], input=data,
                                     capture_output=True, timeout=10, check=True)
            text = json.loads(process.stdout)['text']
        else:
            raise AppError(415, 'file_type', 'Only UTF-8 .txt, .md and text-based .pdf files are accepted.')
    except AppError:
        raise
    except Exception:
        raise AppError(422, 'file_invalid', 'Unreadable file. Use UTF-8 text or an unencrypted text PDF of at most 40 pages.') from None
    if len(text.strip()) < 20 or len(text) > 200000:
        raise AppError(422, 'file_content', 'Extracted text must contain 20-200000 characters. Scanned PDFs need OCR before upload.')
    return text
