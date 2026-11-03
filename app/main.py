import hmac
import logging
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends, UploadFile, File, Form, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from app.core import config
from app.core.db import initialize, connection
from app.core.errors import AppError
from app.api.schemas import DocumentInput, ChatInput, ReviewInput
from app.services import documents, retrieval, chat
from app.services.files import extract
from starlette.concurrency import run_in_threadpool

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger('atlas')

@asynccontextmanager
async def lifespan(app):
    if not config.API_KEY or not config.ADMIN_KEY or config.API_KEY == config.ADMIN_KEY:
        raise RuntimeError('Set distinct API_KEY and ADMIN_KEY values before starting.')
    initialize()
    yield

app = FastAPI(title='Incident Atlas', version='1.0.0', lifespan=lifespan)
static = Path(__file__).parent / 'static'
app.mount('/static', StaticFiles(directory=static), name='static')

def reader(x_api_key: str = Header(default='')):
    if not any(hmac.compare_digest(x_api_key, k) for k in (config.API_KEY, config.ADMIN_KEY) if k):
        raise AppError(401, 'unauthorized', 'A valid API key is required.')

def admin(x_api_key: str = Header(default='')):
    if not config.ADMIN_KEY or not hmac.compare_digest(x_api_key, config.ADMIN_KEY):
        raise AppError(403, 'forbidden', 'A curator key is required.')

@app.middleware('http')
async def observe(request: Request, call_next):
    rid = uuid.uuid4().hex
    request.state.request_id = rid
    length = request.headers.get('content-length')
    # ASGI body limiter below also enforces chunked uploads.
    if length and (not length.isdigit() or int(length) > config.MAX_BYTES + 65536):
        return JSONResponse({'error': {'code': 'request_size', 'message': 'Request too large.', 'request_id': rid}}, status_code=413)
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = round((time.perf_counter()-started)*1000, 3)
    response.headers.update({'X-Request-ID': rid, 'X-Latency-Ms': str(elapsed), 'X-LLM-Cost-USD': '0',
        'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
        'Content-Security-Policy': "default-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'"})
    route = request.scope.get('route')
    path = getattr(route, 'path', 'unmatched')
    logger.info('request_id=%s route=%s status=%s latency_ms=%s llm_cost_usd=0', rid, path, response.status_code, elapsed)
    if path.startswith('/api/') and path != '/api/metrics':
        try:
            with connection(write=True) as db:
                db.execute('INSERT INTO telemetry(route,status,latency_ms,at) VALUES (?,?,?,?)', (path, response.status_code, elapsed, documents.now()))
                db.execute('DELETE FROM telemetry WHERE id < (SELECT COALESCE(MAX(id),0)-10000 FROM telemetry)')
        except sqlite3.Error:
            logger.warning('telemetry_unavailable request_id=%s', rid)
    return response

class BodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        # Bound the body before JSON/multipart parsing can convert errors to 400.
        body = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            chunk = message.get('body', b'')
            if len(body) + len(chunk) > config.MAX_BYTES + 65536:
                rid = uuid.uuid4().hex
                response = JSONResponse({'error': {'code': 'request_size', 'message': 'Request too large.', 'request_id': rid}},
                                        status_code=413, headers={'X-Request-ID': rid})
                return await response(scope, receive, send)
            body.extend(chunk)
            if not message.get('more_body', False):
                break
        delivered = False
        async def replay():
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
        await self.app(scope, replay, send)

app.add_middleware(BodyLimit)

@app.exception_handler(AppError)
async def known(request, exc):
    return JSONResponse({'error': {'code': exc.code, 'message': exc.message, 'request_id': getattr(request.state, 'request_id', '')}}, status_code=exc.status)

@app.exception_handler(RequestValidationError)
async def invalid(request, exc):
    return JSONResponse({'error': {'code': 'validation', 'message': 'Invalid input.', 'fields': [{'location': e['loc'], 'message': e['msg']} for e in exc.errors()]}}, status_code=422)

@app.exception_handler(sqlite3.OperationalError)
async def database_error(request, exc):
    return JSONResponse({'error': {'code': 'storage_unavailable', 'message': 'Storage is temporarily unavailable. Retry shortly.'}}, status_code=503, headers={'Retry-After': '2'})

@app.exception_handler(Exception)
async def unexpected(request, exc):
    logger.error('unexpected_error request_id=%s type=%s', getattr(request.state, 'request_id', ''), type(exc).__name__)
    return JSONResponse({'error': {'code': 'internal_error', 'message': 'Unexpected failure. Contact the operator with the request ID.', 'request_id': getattr(request.state, 'request_id', '')}}, status_code=500)

@app.get('/', include_in_schema=False)
def home():
    return FileResponse(static / 'index.html')

@app.get('/health/live')
def live():
    return {'status': 'ok'}

@app.get('/health/ready')
def ready():
    with connection() as db:
        db.execute('SELECT count(*) FROM documents').fetchone()
    return {'status': 'ready', 'retrieval': 'lexical', 'generation': 'extractive', 'external_dependencies': []}

@app.post('/api/documents', dependencies=[Depends(admin)])
def ingest(payload: DocumentInput):
    return documents.ingest(payload)

@app.post('/api/uploads', dependencies=[Depends(admin)])
async def upload(file: UploadFile = File(...), source_key: str = Form(...), title: str = Form(...), services: str = Form('')):
    try:
        data = await file.read(config.MAX_BYTES+1)
        content = await run_in_threadpool(extract, file.filename, data)
        try:
            payload = DocumentInput(source_key=source_key, title=title, content=content, services=[s.strip() for s in services.split(',') if s.strip()])
        except ValueError:
            raise AppError(422, 'metadata_invalid', 'Invalid source key, title or services.') from None
        return await run_in_threadpool(documents.ingest, payload)
    finally:
        await file.close()

@app.get('/api/documents', dependencies=[Depends(reader)])
def listing():
    with connection() as db:
        return {'documents': [documents.public(r) for r in db.execute("SELECT * FROM documents WHERE deleted=0 AND status='published' ORDER BY updated_at DESC LIMIT 100")]}

@app.get('/api/review', dependencies=[Depends(admin)])
def review_queue():
    with connection() as db:
        return {'documents': [documents.public(r) for r in db.execute("SELECT * FROM documents WHERE deleted=0 AND status='review' ORDER BY updated_at DESC LIMIT 100")]}

@app.post('/api/documents/{doc_id}/review', dependencies=[Depends(admin)])
def review(doc_id: str, payload: ReviewInput):
    return documents.review(doc_id, payload.approve)

@app.get('/api/documents/{doc_id}', dependencies=[Depends(reader)])
def detail(doc_id: str):
    return documents.get_document(doc_id)

@app.delete('/api/documents/{doc_id}', dependencies=[Depends(admin)])
def delete(doc_id: str):
    documents.delete(doc_id)
    return {'deleted': True}

@app.get('/api/search', dependencies=[Depends(reader)])
def search(q: str = Query(min_length=1, max_length=12000), kind: str | None = Query(default=None, pattern='^(RCA|SOP)$')):
    return retrieval.search(q, kind)

@app.get('/api/suggest', dependencies=[Depends(reader)])
def suggest(q: str = Query(min_length=1, max_length=12000)):
    return {kind: retrieval.search(q, kind)['results'] for kind in ('RCA', 'SOP')}

@app.post('/api/chat', dependencies=[Depends(reader)])
def converse(payload: ChatInput):
    return chat.answer(payload)

@app.get('/api/metrics', dependencies=[Depends(admin)])
def metrics():
    with connection() as db:
        rows = [dict(r) for r in db.execute('SELECT route,count(*) requests,round(avg(latency_ms),2) mean_ms,sum(status>=500) errors FROM telemetry GROUP BY route')]
    return {'routes': rows, 'retention': 'last 10000 requests', 'llm_calls': 0, 'llm_tokens': 0, 'llm_cost_usd': 0, 'infrastructure_cost': 'Measure host cost separately; not included.'}
