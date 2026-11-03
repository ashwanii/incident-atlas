"""Small synthetic gate, not a representative production benchmark."""
import json
import os
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from fastapi.testclient import TestClient
from app.core import config
from app.main import app
from app.services.retrieval import intent


def main():
    root=Path(__file__).resolve().parents[1]
    cases=json.loads((root/'evaluation/cases.json').read_text())
    results=[]
    with tempfile.TemporaryDirectory() as directory:
        config.DATA_DIR=Path(directory)
        config.DB_PATH=Path(directory)/'eval.sqlite3'
        config.API_KEY='eval-reader'
        config.ADMIN_KEY='eval-admin'
        with TestClient(app) as client:
            client.headers['X-API-Key']='eval-admin'
            for document in json.loads((root/'examples/documents.json').read_text()):
                response=client.post('/api/documents',json=document)
                response.raise_for_status()
            for case in cases:
                start=time.perf_counter()
                task,q=case['task'],case['query']
                if task=='intent':
                    actual=intent(q)
                elif task=='chat':
                    response=client.post('/api/chat',json={'message':q})
                    response.raise_for_status()
                    data=response.json()
                    actual=data['kind'] if data.get('citations') else 'NONE'
                elif task=='suggest':
                    response=client.get('/api/suggest',params={'q':q})
                    response.raise_for_status()
                    data=response.json()
                    kinds=[k for k in ('RCA','SOP') if data[k]]
                    actual='BOTH' if len(kinds)==2 else kinds[0] if kinds else 'NONE'
                else:
                    response=client.get('/api/search',params={'q':q})
                    response.raise_for_status()
                    data=response.json()
                    actual='AMBIGUOUS' if data['ambiguous'] else data['results'][0]['kind'] if data['results'] else 'NONE'
                results.append(case|{'actual':actual,'passed':actual==case['expected'],'latency_ms':round((time.perf_counter()-start)*1000,3),'llm_calls':0,'llm_tokens':0,'llm_cost_usd':0})
    groups=defaultdict(list)
    for r in results:
        groups[(r['split'],r['origin'],r['task'])].append(r)
    summary=[{'split':k[0],'origin':k[1],'task':k[2],'n':len(v),'passed':sum(r['passed'] for r in v),'accuracy':sum(r['passed'] for r in v)/len(v)} for k,v in groups.items()]
    latencies=sorted(r['latency_ms'] for r in results if r['task']!='intent')
    report={'method':'Synthetic, local in-process TestClient; not network or load latency. No assignment query dataset was supplied. Holdout was declared before running; tiny sample is not statistically reliable.','results':results,'summary':summary,'p95_local_api_ms':latencies[min(len(latencies)-1,int(.95*len(latencies)))],'passed':all(r['passed'] for r in results)}
    (root/'evaluation/results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':report['passed'],'cases':len(results),'p95_local_api_ms':report['p95_local_api_ms']},indent=2))
    if not report['passed']:
        raise SystemExit(1)

if __name__=='__main__':
    main()
