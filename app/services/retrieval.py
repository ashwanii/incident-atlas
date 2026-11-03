import re
from app.core.db import connection
from app.services.documents import public
STOP = set('the a an is are was were what why how do i we to for of in on and or this that it please show find me happened cause caused steps procedure rollback prerequisites impact'.split())

def tokens(text):
    # Deduplicate stacktrace repetition; preserve identifiers and error words.
    return list(dict.fromkeys(t.lower() for t in re.findall(r'[a-zA-Z][a-zA-Z0-9_-]{1,60}', text) if t.lower() not in STOP))[:64]

def search(query, kind=None, limit=10):
    with connection() as db:
        # Explicit identities never fall through to semantic/fuzzy lookup.
        ids = re.findall(r'\bDOC-[A-Za-z0-9]+\b', query, re.I)
        if ids:
            rows = db.execute("SELECT * FROM documents WHERE upper(id)=? AND deleted=0 AND status='published'", (ids[0].upper(),)).fetchall()
            hits = [public(r) | {'score': 1.0, 'why': 'Exact stable identity'} for r in rows if not kind or r['kind'] == kind]
            return {'results': hits, 'ambiguous': False, 'mode': 'identity'}
        quoted = re.search(r'"([^"]+)"', query)
        title_query = quoted.group(1) if quoted else query.strip()
        rows = db.execute("SELECT * FROM documents WHERE lower(title)=lower(?) AND deleted=0 AND status='published'", (title_query,)).fetchall()
        exact = [public(r) | {'score': 1.0, 'why': 'Exact title'} for r in rows if not kind or r['kind'] == kind]
        if exact or quoted:
            return {'results': exact, 'ambiguous': len(exact) > 1, 'mode': 'title'}
        words = tokens(query)
        if not words:
            return {'results': [], 'ambiguous': False, 'mode': 'lexical'}
        expression = ' OR '.join('"' + w.replace('"', '') + '"' for w in words)
        rows = db.execute("""SELECT d.*, bm25(search_index,0,5,3,1) rank
            FROM search_index JOIN documents d ON d.id=search_index.document_id
            WHERE search_index MATCH ? AND d.deleted=0 AND d.status='published'
            AND (? IS NULL OR d.kind=?) ORDER BY rank LIMIT 50""", (expression, kind, kind)).fetchall()
        hits = []
        for row in rows:
            doc = public(row)
            available = set(tokens(doc['title'] + ' ' + ' '.join(doc['services']) + ' ' + doc['content']))
            matched = sorted(set(words) & available)
            coverage = len(matched) / len(words)
            if coverage < .22 or not matched:
                continue
            doc.update(score=round(coverage, 3), why='Matched: ' + ', '.join(matched[:8]))
            hits.append(doc)
        hits.sort(key=lambda d: d['score'], reverse=True)
        return {'results': hits[:limit], 'ambiguous': len(hits)>1 and abs(hits[0]['score']-hits[1]['score']) < .15, 'mode': 'lexical'}

def intent(text, previous=None):
    lower = text.lower()
    sop = bool(re.search(r'\b(how|steps?|rollback|prerequisites?|procedure|runbook|sop|recover)\b', lower))
    rca = bool(re.search(r'\b(why|caus\w*|impact|timeline|incident|rca|happened)\b', lower))
    if sop and rca:
        return None
    if sop:
        return 'SOP'
    if rca:
        return 'RCA'
    return previous
