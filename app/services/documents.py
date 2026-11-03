import hashlib
import json
import re
import uuid
from datetime import datetime, timezone, date
from difflib import SequenceMatcher
from app.core.db import connection
from app.core.errors import AppError

def now():
    return datetime.now(timezone.utc).isoformat()

def redact(text):
    patterns = [
        (r'(?i)\b(password|passwd|api[_-]?key|token|secret)\s*[:=]\s*[^\s,;]+', r'\1=[REDACTED]'),
        (r'\bAKIA[0-9A-Z]{16}\b', '[REDACTED_AWS_KEY]'),
        (r'(?i)Bearer\s+[A-Za-z0-9._~+/=-]+', 'Bearer [REDACTED]'),
        (r'-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----', '[REDACTED_PRIVATE_KEY]'),
        (r'\b(?:10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)\b', '[REDACTED_PRIVATE_IP]'),
        (r'(?i)\b[a-z0-9.-]+\.(?:internal|local|corp)\b', '[REDACTED_INTERNAL_HOST]'),
    ]
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text)
    return text

def fingerprint(text):
    return hashlib.sha256(text.replace('\r\n', '\n').replace('\r', '\n').encode()).hexdigest()

def assess(content, kind):
    lower = content.lower()
    rca = sum(bool(re.search(p, lower)) for p in [r'root cause', r'timeline', r'impact', r'corrective action'])
    sop = sum(bool(re.search(p, lower)) for p in [r'prerequisite', r'rollback', r'\bsteps\b', r'verification'])
    reasons = []
    inferred = 'SOP' if sop > rca else 'RCA'
    if rca >= 2 and sop >= 2:
        reasons.append('Mixed RCA and SOP: curator must split into independently identified documents.')
    if max(rca, sop) < 2:
        reasons.append('Insufficient structural evidence.')
    if kind and kind != inferred:
        reasons.append('Declared type conflicts with detected structure.')
    actual = kind or inferred
    if actual == 'SOP':
        numbers = [int(n) for n in re.findall(r'^\s*(\d+)[.)]\s', content, re.M)]
        if numbers != list(range(1, len(numbers)+1)):
            reasons.append('SOP step numbers must be consecutive and unique.')
    if actual == 'SOP' and (not re.search(r'^\s*1[.)]\s', content, re.M) or not all(s in lower for s in ['prerequisite', 'rollback', 'verification'])):
        reasons.append('SOP needs ordered steps, prerequisites, verification and rollback.')
    # Confidence is a heuristic score, not a calibrated probability.
    return actual, (0.45 if reasons else 0.9), reasons

def public(row):
    d = dict(row)
    d['services'] = json.loads(d['services'])
    d['reasons'] = json.loads(d['reasons'])
    d.pop('digest', None)
    d['stale'] = not d['reviewed_on'] or (date.today() - date.fromisoformat(d['reviewed_on'])).days > 180
    return d

def index(db, doc_id):
    db.execute('DELETE FROM search_index WHERE document_id=?', (doc_id,))
    r = db.execute("SELECT * FROM documents WHERE id=? AND deleted=0 AND status='published'", (doc_id,)).fetchone()
    if r:
        db.execute('INSERT INTO search_index VALUES (?,?,?,?)', (r['id'], r['title'], r['services'], r['content']))

def audit(db, doc_id, action):
    db.execute('INSERT INTO audit(document_id,action,at) VALUES (?,?,?)', (doc_id, action, now()))

def ingest(payload):
    raw = payload.model_dump()
    content, title = redact(raw['content']), redact(raw['title'])
    services = [redact(s) for s in raw['services']]
    kind, confidence, reasons = assess(content, raw['kind'])
    if raw['origin'] == 'greenfield' and (not raw['kind'] or not raw['owner'] or not raw['reviewed_on'] or not services):
        raise AppError(422, 'template_incomplete', 'Greenfield requires type, service, owner and review date.')
    if '[REDACTED' in content:
        reasons.append('Sensitive material redacted; verify procedure remains safe.')
    digest = fingerprint(content)
    with connection(write=True) as db:
        old = db.execute('SELECT d.* FROM documents d LEFT JOIN aliases a ON a.document_id=d.id WHERE d.source_key=? OR a.source_key=?', (raw['source_key'], raw['source_key'])).fetchone()
        duplicate = db.execute('SELECT * FROM documents WHERE digest=? AND deleted=0 AND id!=?', (digest, old['id'] if old else '')).fetchone()
        if duplicate:
            if old:
                raise AppError(409, 'duplicate_target', 'Edited source duplicates another document; reconcile explicitly.')
            db.execute('INSERT OR IGNORE INTO aliases VALUES (?,?)', (raw['source_key'], duplicate['id']))
            return {'document': public(duplicate), 'outcome': 'duplicate'}
        if old and not old['deleted'] and all([
            old['digest'] == digest, old['title'] == title, old['services'] == json.dumps(services),
            old['owner'] == redact(raw['owner']), old['reviewed_on'] == (str(raw['reviewed_on']) if raw['reviewed_on'] else ''),
            old['kind'] == kind, old['origin'] == raw['origin']]):
            return {'document': public(old), 'outcome': 'unchanged'}
        for row in db.execute('SELECT id,content FROM documents WHERE deleted=0'):
            if (not old or row['id'] != old['id']) and SequenceMatcher(None, content[:12000], row['content'][:12000], autojunk=True).ratio() >= .88:
                reasons.append('Near duplicate of ' + row['id'] + '; reconcile before publication.')
                break
        doc_id = old['id'] if old else 'DOC-' + uuid.uuid4().hex[:12].upper()
        version = old['version'] + 1 if old else 1
        values = (doc_id, old['source_key'] if old else raw['source_key'], title, kind, json.dumps(services), content, digest, version,
                  'review' if reasons else 'published', confidence, json.dumps(reasons), raw['origin'], now(), redact(raw['owner']), str(raw['reviewed_on']) if raw['reviewed_on'] else '', 0)
        db.execute('''INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET title=excluded.title,kind=excluded.kind,services=excluded.services,
            content=excluded.content,digest=excluded.digest,version=excluded.version,status=excluded.status,
            confidence=excluded.confidence,reasons=excluded.reasons,origin=excluded.origin,updated_at=excluded.updated_at,
            owner=excluded.owner,reviewed_on=excluded.reviewed_on,deleted=excluded.deleted''', values)
        db.execute('INSERT OR IGNORE INTO aliases VALUES (?,?)', (raw['source_key'], doc_id))
        result = dict(db.execute('SELECT * FROM documents WHERE id=?', (doc_id,)).fetchone())
        db.execute('INSERT INTO versions VALUES (?,?,?)', (doc_id, version, json.dumps(result)))
        index(db, doc_id)
        audit(db, doc_id, 'updated' if old else 'created')
        return {'document': public(result), 'outcome': 'updated' if old else 'created'}

def get_document(doc_id, include_review=False):
    with connection() as db:
        row = db.execute('SELECT * FROM documents WHERE id=? AND deleted=0', (doc_id,)).fetchone()
        if not row or (not include_review and row['status'] != 'published'):
            raise AppError(404, 'not_found', 'Document unavailable or awaiting review.')
        return public(row)

def delete(doc_id):
    with connection(write=True) as db:
        row = db.execute('SELECT id FROM documents WHERE id=? AND deleted=0', (doc_id,)).fetchone()
        if not row:
            raise AppError(404, 'not_found', 'Document unavailable.')
        db.execute('UPDATE documents SET deleted=1 WHERE id=?', (doc_id,))
        db.execute('DELETE FROM search_index WHERE document_id=?', (doc_id,))
        db.execute('DELETE FROM sessions WHERE document_id=?', (doc_id,))
        audit(db, doc_id, 'deleted')

def review(doc_id, approve):
    with connection(write=True) as db:
        row = db.execute('SELECT * FROM documents WHERE id=? AND deleted=0', (doc_id,)).fetchone()
        if not row:
            raise AppError(404, 'not_found', 'Document unavailable.')
        # Structural safety cannot be overridden by clicking approve.
        _, _, structural = assess(row['content'], row['kind'])
        if approve and structural:
            raise AppError(409, 'needs_edit', 'Correct or split the source and re-ingest first: ' + '; '.join(structural))
        db.execute('UPDATE documents SET status=? WHERE id=?', ('published' if approve else 'review', doc_id))
        index(db, doc_id)
        audit(db, doc_id, 'approved' if approve else 'quarantined')
    return get_document(doc_id, True)
