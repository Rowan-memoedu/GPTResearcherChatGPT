"""Bounded SQLite snapshots for the upstream MCP's research IDs and topic cache.

Only research content is serialized. Runtime clients, configuration, headers and
account authorization never enter this store. Objects are rebuilt on demand so
completed research does not accumulate as live Python object graphs.
"""
from collections.abc import MutableMapping
from contextlib import closing
from enum import Enum
import json
from pathlib import Path
import sqlite3


class JsonStore(MutableMapping):
    def __init__(self, path, namespace, max_bytes=256 * 1024 * 1024):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.namespace = namespace
        self.max_bytes = max_bytes
        with closing(self.connect()) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS entries '
                       '(namespace TEXT, key TEXT, payload TEXT NOT NULL, PRIMARY KEY(namespace, key))')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        page_size = db.execute('PRAGMA page_size').fetchone()[0]
        db.execute(f'PRAGMA max_page_count={max(4, self.max_bytes // page_size)}')
        return db

    def __getitem__(self, key):
        with closing(self.connect()) as db:
            row = db.execute('SELECT payload FROM entries WHERE namespace=? AND key=?',
                             (self.namespace, key)).fetchone()
        if row is None:
            raise KeyError(key)
        return json.loads(row[0])

    def __setitem__(self, key, value):
        payload = json.dumps(value, ensure_ascii=False, allow_nan=False)
        try:
            with closing(self.connect()) as db, db:
                db.execute('INSERT OR REPLACE INTO entries VALUES(?,?,?)', (self.namespace, key, payload))
        except sqlite3.OperationalError as error:
            if 'full' in str(error).lower():
                raise RuntimeError('MCP research state reached its 256 MiB limit or the disk is full; '
                                   'existing results are retained. Review the local state database.') from error
            raise

    def __delitem__(self, key):
        with closing(self.connect()) as db, db:
            changed = db.execute('DELETE FROM entries WHERE namespace=? AND key=?', (self.namespace, key)).rowcount
        if not changed:
            raise KeyError(key)

    def __iter__(self):
        with closing(self.connect()) as db:
            rows = db.execute('SELECT key FROM entries WHERE namespace=?', (self.namespace,)).fetchall()
        return iter(row[0] for row in rows)

    def __len__(self):
        with closing(self.connect()) as db:
            return db.execute('SELECT COUNT(*) FROM entries WHERE namespace=?', (self.namespace,)).fetchone()[0]

    def __contains__(self, key):
        with closing(self.connect()) as db:
            return db.execute('SELECT 1 FROM entries WHERE namespace=? AND key=?',
                              (self.namespace, key)).fetchone() is not None


CONSTRUCTOR_FIELDS = ('query', 'report_type', 'report_format', 'report_source', 'source_urls',
                      'document_urls', 'complement_source_urls', 'query_domains', 'agent', 'role',
                      'parent_query', 'subtopics', 'context')
CONTENT_FIELDS = ('research_sources', 'research_images', 'research_costs', 'step_costs', 'available_images')


class DurableResearchers(JsonStore):
    def __init__(self, path, factory):
        super().__init__(path, 'researchers')
        self.factory = factory

    def __setitem__(self, key, researcher):
        constructor = {name: getattr(researcher, name) for name in CONSTRUCTOR_FIELDS}
        constructor['visited_urls'] = sorted(researcher.visited_urls)
        tone = researcher.tone
        constructor['tone'] = tone.value if isinstance(tone, Enum) else tone
        content = {name: getattr(researcher, name) for name in CONTENT_FIELDS}
        super().__setitem__(key, {'schema': 1, 'constructor': constructor, 'content': content})
        researcher._mcp_research_id = key

    def __getitem__(self, key):
        snapshot = super().__getitem__(key)
        if snapshot.get('schema') != 1:
            raise ValueError('Unsupported MCP research snapshot schema')
        constructor = snapshot['constructor']
        constructor['visited_urls'] = set(constructor['visited_urls'])
        researcher = self.factory(**constructor, verbose=False)
        for name in CONTENT_FIELDS:
            setattr(researcher, name, snapshot['content'][name])
        researcher._mcp_research_id = key
        return researcher
