"""Synthetic retrieval scale check, not ingestion or semantic evaluation."""
import concurrent.futures
import json
import logging
import platform
import tempfile
import time
from pathlib import Path
from fastapi.testclient import TestClient
from app.core import config
from app.core.db import connection
from app.main import app
from app.services.documents import fingerprint, now


def main():
    logging.getLogger('atlas').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    with tempfile.TemporaryDirectory() as temp:
        config.DATA_DIR=Path(temp)
        config.DB_PATH=Path(temp)/'bench.sqlite3'
        config.API_KEY='bench-reader'
        config.ADMIN_KEY='bench-admin'
        with TestClient(app) as client:
            client.headers['X-API-Key']='bench-reader'
            with connection(write=True) as db:
                for i in range(3000):
                    doc_id,service=f'DOC-BENCH{i}',f'service{i}'
                    title=f'{service} memory incident'
                    content=f'Root cause: {service} memory exhaustion. Impact: delayed tasks. Timeline: noon. Corrective actions: capacity review.'
                    db.execute('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (doc_id,f'bench/{i}',title,'RCA',json.dumps([service]),content,fingerprint(content),1,'published',.9,'[]','greenfield',now(),'sre','2026-10-01',0))
                    db.execute('INSERT INTO search_index VALUES (?,?,?,?)',(doc_id,title,service,content))
            def run(i):
                start=time.perf_counter()
                task='identity' if i%2==0 else 'lexical'
                query=f'DOC-BENCH{i}' if task=='identity' else f'service{i} memory exhaustion'
                response=client.get('/api/search',params={'q':query})
                data=response.json()
                return {'task':task,'status':response.status_code,'latency_ms':round((time.perf_counter()-start)*1000,3),
                        'correct_top1':bool(data.get('results')) and data['results'][0]['id']==f'DOC-BENCH{i}','llm_cost_usd':0}
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                results=list(pool.map(run,range(200)))
    def percentile(values,p):
        return sorted(values)[min(len(values)-1,int(p*len(values)))]
    summary={task:{'n':sum(r['task']==task for r in results),
                   'p95_ms':percentile([r['latency_ms'] for r in results if r['task']==task],.95),
                   'p99_ms':percentile([r['latency_ms'] for r in results if r['task']==task],.99)} for task in ['identity','lexical']}
    report={'environment':{'python':platform.python_version(),'platform':platform.platform()},
            'method':'3000 short synthetic published RCA fixtures inserted directly, 200 in-process GET requests, 8 client threads. Includes telemetry writes. Excludes network/TLS/container and ingestion. Not a 400-user load test or semantic benchmark.',
            'search_p95_budget_ms':1000, 'latency_gate_passed':all(v['p95_ms']<1000 for v in summary.values()),
            'summary':summary,'results':results,'all_correct':all(r['correct_top1'] and r['status']==200 for r in results)}
    Path(__file__).with_name('benchmark-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('summary','all_correct')},indent=2))
    if not report['all_correct'] or not report['latency_gate_passed']:
        raise SystemExit(1)

if __name__=='__main__':
    main()
