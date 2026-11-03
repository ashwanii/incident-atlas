import json
import os
from pathlib import Path
import httpx

if __name__ == '__main__':
    with httpx.Client(base_url=os.getenv('BASE_URL','http://localhost:8000'), headers={'X-API-Key': os.environ['ADMIN_KEY']}, timeout=20) as client:
        for payload in json.loads(Path('examples/documents.json').read_text()):
            response = client.post('/api/documents', json=payload)
            response.raise_for_status()
            data = response.json()
            print(data['outcome'], data['document']['id'], data['document']['status'])
