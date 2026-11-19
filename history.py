"""SQLite conversation archive; no third-party dependencies.

This stores the visible transcript, not raw audio, model weights or secrets.
Model tool-message state is intentionally not reconstructed from UI transcripts.
"""
import sqlite3
import threading
from pathlib import Path

class ChatHistory:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS conversations(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL DEFAULT 'New conversation',
                    project_path TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS messages(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
                    role TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id,id);
            """)

    def _connect(self):
        db = sqlite3.connect(str(self.path), timeout=10)
        db.execute('PRAGMA foreign_keys=ON')
        return db

    def create(self, project_path=''):
        with self.lock, self._connect() as db:
            cursor = db.execute('INSERT INTO conversations(project_path) VALUES(?)',
                                (str(project_path),))
            return cursor.lastrowid

    def add(self, conversation_id, role, body):
        if not body or not body.strip():
            return
        with self.lock, self._connect() as db:
            db.execute('INSERT INTO messages(conversation_id,role,body) VALUES(?,?,?)',
                       (conversation_id, role, body))
            if role == 'you':
                count = db.execute("SELECT COUNT(*) FROM messages WHERE conversation_id=? AND role='you'",
                                   (conversation_id,)).fetchone()[0]
                if count == 1:
                    title = ' '.join(body.split())[:65] or 'New conversation'
                    db.execute('UPDATE conversations SET title=? WHERE id=?', (title, conversation_id))
            db.execute("UPDATE conversations SET updated_at=CURRENT_TIMESTAMP WHERE id=?",
                       (conversation_id,))

    def list_conversations(self):
        with self.lock, self._connect() as db:
            return db.execute('SELECT id,title,project_path FROM conversations ORDER BY updated_at DESC,id DESC').fetchall()

    def messages(self, conversation_id):
        with self.lock, self._connect() as db:
            return db.execute('SELECT role,body FROM messages WHERE conversation_id=? ORDER BY id',
                              (conversation_id,)).fetchall()

    def project(self, conversation_id):
        with self.lock, self._connect() as db:
            row = db.execute('SELECT project_path FROM conversations WHERE id=?', (conversation_id,)).fetchone()
            return row[0] if row else ''

    def set_project(self, conversation_id, path):
        with self.lock, self._connect() as db:
            db.execute('UPDATE conversations SET project_path=? WHERE id=?',
                       (str(path), conversation_id))
