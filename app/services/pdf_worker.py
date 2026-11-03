"""Isolated PDF extraction; input and output are anonymous pipes, never filenames."""
import io
import json
import sys


def main():
    if sys.platform == 'linux':
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (384 * 1024 * 1024, 384 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    try:
        from pypdf import PdfReader
        data = sys.stdin.buffer.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024:
            raise ValueError('too large')
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted or len(reader.pages) > 40:
            raise ValueError('unsupported document')
        pages = []
        size = 0
        for page in reader.pages:
            text = page.extract_text() or ''
            size += len(text)
            if size > 200000:
                raise ValueError('extracted text too large')
            pages.append(text)
        sys.stdout.write(json.dumps({'text': '\n'.join(pages)}))
    except Exception:
        sys.stdout.write(json.dumps({'error': 'invalid PDF'}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
