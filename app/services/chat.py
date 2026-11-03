import uuid
from app.core.db import connection
from app.core.errors import AppError
from app.services.documents import get_document, now
from datetime import datetime, timezone, timedelta
import re
from app.services.retrieval import intent, search, tokens

def answer(request):
    with connection() as db:
        prior = db.execute('SELECT * FROM sessions WHERE id=?', (request.session_id or '',)).fetchone()
    if prior and datetime.fromisoformat(prior['updated_at']) < datetime.now(timezone.utc)-timedelta(hours=24):
        prior = None
    kind = request.kind or intent(request.message, prior['kind'] if prior else None)
    sid = request.session_id or uuid.uuid4().hex
    if request.session_id and not prior:
        raise AppError(404, 'session_missing', 'Conversation expired or does not exist; start a new conversation.')
    if not kind:
        return {'session_id': sid, 'clarification': 'Choose RCA for incident analysis or SOP for operating procedures.', 'citations': [], 'answer': ''}
    doc = None
    if request.document_id:
        doc = get_document(request.document_id)
        if doc['kind'] != kind:
            raise AppError(409, 'type_mismatch', 'Selected document does not match the requested topic.')
    elif prior and prior['document_id'] and prior['kind'] == kind and not re.search(r'\bDOC-[A-Za-z0-9]+\b', request.message, re.I) and (request.message.strip().lower().strip('?') in {'why','impact','rollback','prerequisites','steps','timeline'} or request.message.lower().startswith(('and ', 'what was the impact', 'what is the rollback'))):
        doc = get_document(prior['document_id'])
    else:
        hits = search(request.message, kind)
        if hits['ambiguous']:
            return {'session_id': sid, 'clarification': 'Several documents match. Select a document to continue.', 'candidates': hits['results'], 'citations': [], 'answer': ''}
        if hits['results']:
            doc = hits['results'][0]
    if not doc:
        return {'session_id': sid, 'kind': kind, 'answer': 'No supporting published document found. Add a service, error, or document ID.', 'citations': [], 'abstained': True}
    with connection(write=True) as db:
        db.execute('DELETE FROM sessions WHERE updated_at < ?', ((datetime.now(timezone.utc)-timedelta(hours=24)).isoformat(),))
        db.execute('INSERT OR REPLACE INTO sessions VALUES (?,?,?,?)', (sid, kind, doc['id'], now()))
    # Extractive response: full authoritative, redacted body. No generated/reordered steps.
    return {'session_id': sid, 'kind': kind, 'answer': doc['content'], 'extractive': True,
            'notice': 'Source excerpt; verify service, version and review date before action.',
            'citations': [{'id': doc['id'], 'version': doc['version'], 'title': doc['title'], 'stale': doc['stale'], 'url': '/api/documents/' + doc['id']}]}
