import concurrent.futures
from app.core.db import connection
from app.api.schemas import DocumentInput
from app.services.documents import ingest


def add(client, data):
    response = client.post('/api/documents', json=data)
    assert response.status_code == 200, response.text
    return response.json()['document']

def test_repeated_concurrent_ingestion(client, rca):
    first = add(client, rca)
    assert client.post('/api/documents', json=rca).json()['outcome'] == 'unchanged'
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda _: ingest(DocumentInput(**rca)), range(30)))
    assert {r['document']['id'] for r in results} == {first['id']}
    with connection() as db:
        assert db.execute('SELECT count(*) FROM documents').fetchone()[0] == 1
        assert db.execute('SELECT count(*) FROM versions').fetchone()[0] == 1
        assert db.execute('SELECT count(*) FROM search_index').fetchone()[0] == 1

def test_duplicate_under_different_name(client, rca):
    first = add(client, rca)
    second = add(client, rca | {'source_key':'mirror/rca','title':'Renamed'})
    assert first['id'] == second['id']

def test_version_deletion_no_stale_chat(client, rca):
    first = add(client, rca)
    chat = client.post('/api/chat', json={'message':'why kafka', 'document_id':first['id']}).json()
    updated = add(client, rca | {'content':rca['content']+' New action: monitor offsets.'})
    assert updated['id'] == first['id'] and updated['version'] == 2
    current = client.post('/api/chat',json={'message':'what was the impact','session_id':chat['session_id']}).json()
    assert current['citations'][0]['version'] == 2
    assert client.delete('/api/documents/'+first['id']).status_code == 200
    assert client.get('/api/search',params={'q':first['id']}).json()['results'] == []
    assert client.get('/api/search',params={'q':'kafka'}).json()['results'] == []
    assert client.get('/api/documents/'+first['id']).status_code == 404
    assert client.post('/api/chat',json={'message':'why','session_id':chat['session_id']}).status_code == 404

def test_type_isolation_and_exact_order(client, rca, sop):
    r, s = add(client, rca), add(client, sop)
    result = client.get('/api/search',params={'q':'Kafka lag'}).json()
    assert result['ambiguous'] is True
    assert {d['kind'] for d in result['results']} == {'RCA','SOP'}
    answer = client.post('/api/chat',json={'message':'how to fix kafka', 'document_id':s['id']}).json()
    assert answer['answer'] == sop['content']
    assert answer['kind'] == 'SOP' and answer['citations'][0]['id'] == s['id']
    assert client.post('/api/chat',json={'message':'why kafka','document_id':s['id']}).status_code == 409
    missing = client.get('/api/search',params={'q':'DOC-MISSING kafka'}).json()
    assert missing['results'] == [] and missing['mode'] == 'identity'
    result = client.get('/api/search',params={'q':r['id'],'kind':'SOP'}).json()
    assert result['results'] == []

def test_context_switch(client, rca, sop):
    r,s = add(client,rca),add(client,sop)
    first = client.post('/api/chat',json={'message':'why kafka'}).json()
    second = client.post('/api/chat',json={'message':'and impact?','session_id':first['session_id']}).json()
    assert second['citations'][0]['id'] == r['id']
    third = client.post('/api/chat',json={'message':'how to fix kafka','session_id':first['session_id']}).json()
    assert third['kind']=='SOP' and third['citations'][0]['id']==s['id']

def test_mixed_unknown_near_duplicate_review(client, rca):
    original = add(client, rca)
    mixed = add(client, rca | {'source_key':'mixed','content':rca['content']+' Prerequisites: approval. Steps: restart. Rollback: restore.'})
    assert mixed['status']=='review'
    assert client.post('/api/documents/'+mixed['id']+'/review',json={'approve':True}).status_code==409
    unknown = add(client, {'source_key':'unknown','title':'Notes','content':'Restarting something helped last year, maybe.'})
    assert unknown['status']=='review'
    near = add(client, rca | {'source_key':'near','content':rca['content']+' Minor note.'})
    assert near['status']=='review'
    assert 'Near duplicate' in ' '.join(near['reasons'])
    assert client.get('/api/documents/'+mixed['id']).status_code==404
    assert len(client.get('/api/review').json()['documents'])==3

def test_secrets_and_access(client, rca):
    doc = add(client,rca | {'content':rca['content']+' password=supersecret Bearer abcdef 10.2.3.4 node.internal'})
    assert 'supersecret' not in str(doc) and '10.2.3.4' not in str(doc)
    with connection() as db:
        assert 'supersecret' not in db.execute('SELECT snapshot FROM versions').fetchone()[0]
    client.headers['X-API-Key']='reader-test'
    assert client.post('/api/documents',json=rca).status_code==403
    assert client.get('/api/review').status_code==403
    client.headers['X-API-Key']='wrong'
    assert client.get('/api/search',params={'q':'kafka'}).status_code==401

def test_upload_failure_and_path_safety(client):
    metadata={'source_key':'upload/runbook','title':'Uploaded notes'}
    assert client.post('/api/uploads',data=metadata,files={'file':('../../bad.exe',b'MZbinary')}).status_code==415
    assert client.post('/api/uploads',data=metadata,files={'file':('bad.pdf',b'%PDF-broken')}).status_code==422
    assert client.post('/api/uploads',data=metadata,files={'file':('bad.txt',b'\xff\xfe')}).status_code==422
    assert client.post('/api/uploads',data=metadata,files={'file':('large.txt',b'a'*(2*1024*1024+1))}).status_code==413
    response=client.post('/api/uploads',data=metadata,files={'file':('../../notes.txt',b'Root cause: cache eviction. Impact: sessions lost. Timeline: noon. Corrective actions: memory reserve.')})
    assert response.status_code==200
    assert response.json()['document']['status']=='published'

def test_abstention_clarification_and_metrics(client, rca):
    add(client,rca)
    assert client.post('/api/chat',json={'message':'help'}).json()['clarification']
    assert client.post('/api/chat',json={'message':'why volcano eruption'}).json()['abstained']
    assert client.get('/api/search',params={'q':'volcano eruption'}).json()['results']==[]
    assert client.get('/api/metrics').json()['llm_calls']==0
    assert client.get('/health/ready').status_code==200

def test_noisy_input(client, rca):
    add(client,rca)
    a=client.get('/api/suggest',params={'q':'kafka consumer saturation'}).json()
    b=client.get('/api/suggest',params={'q':('kafka consumer saturation\n'*60)}).json()
    assert a['RCA'][0]['id']==b['RCA'][0]['id']

def test_metadata_edit_and_revive(client, rca):
    first=add(client,rca)
    updated=add(client,rca|{'owner':'new-owner'})
    assert updated['id']==first['id'] and updated['version']==2
    client.delete('/api/documents/'+first['id'])
    revived=add(client,rca)
    assert revived['id']==first['id'] and revived['version']==3


def test_alias_edit_keeps_identity(client, rca):
    first=add(client,rca)
    add(client,rca|{'source_key':'mirror/source','title':'Another title'})
    edited=add(client,rca|{'source_key':'mirror/source','content':rca['content']+' Monitor queue age.'})
    assert edited['id']==first['id'] and edited['version']==2
    assert edited['source_key']==rca['source_key']


def test_new_topic_does_not_inherit_wrong_document(client, rca):
    add(client,rca)
    first=client.post('/api/chat',json={'message':'why kafka'}).json()
    second=client.post('/api/chat',json={'message':'why volcano','session_id':first['session_id']}).json()
    assert second['abstained'] and second['citations']==[]
    missing=client.post('/api/chat',json={'message':'why DOC-NONEXISTENT','session_id':first['session_id']}).json()
    assert missing['abstained']


def test_skipped_steps_quarantined_and_quoted_title(client, sop):
    d=add(client,sop|{'content':sop['content'].replace('2. Check','5. Check')})
    assert d['status']=='review'
    assert client.post('/api/documents/'+d['id']+'/review',json={'approve':True}).status_code==409
    assert client.get('/api/search',params={'q':'SOP "missing title" kafka'}).json()['results']==[]


def test_storage_outage_is_sanitized(client, monkeypatch):
    from app.core import config
    monkeypatch.setattr(config,'DB_PATH',config.DATA_DIR/'missing'/'missing.sqlite3')
    response=client.get('/api/search',params={'q':'kafka'})
    assert response.status_code==503
    assert 'Retry-After' in response.headers
    assert 'sqlite' not in response.text.lower()


def test_validation_does_not_echo_secret_body(client):
    response=client.post('/api/documents',json={'source_key':'unsafe space','content':'password=supersecret'})
    assert response.status_code==422 and 'supersecret' not in response.text


def test_chunked_request_limit(client):
    def chunks():
        yield b'{"content":"'
        for _ in range(35):
            yield b'a'*65536
        yield b'"}'
    response=client.post('/api/documents',content=chunks(),headers={'Content-Type':'application/json'})
    assert response.status_code==413


def test_concurrent_renamed_duplicates_from_empty_store(client, rca):
    def create(i):
        return ingest(DocumentInput(**(rca|{'source_key':f'mirror/{i}'})))
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        results=list(pool.map(create,range(20)))
    assert len({r['document']['id'] for r in results})==1
    with connection() as db:
        assert db.execute('SELECT count(*) FROM documents').fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM versions').fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM aliases').fetchone()[0]==20


def test_case_and_indentation_edits_are_real_versions(client, sop):
    first=add(client,sop)
    second=add(client,sop|{'content':sop['content'].replace('Record lag.', 'Record LAG.')})
    assert second['id']==first['id'] and second['version']==2
    third=add(client,sop|{'content':sop['content'].replace('1. Record','  1. Record')})
    assert third['version']==3
