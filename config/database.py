import sqlite3
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from contextlib import contextmanager
from config.global_logger import get_logger
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

logger = get_logger("database")


url= os.getenv("SUPABASE_URL")
key= os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)


class ChatDatabase:
    def __init__(self, db_path: str = "data/chats.db"):
        self.db_path = db_path
        self._ensure_db_directory()
        self._initialize_database()
        logger.info(f"Chat database initialized at {db_path}")

    def _ensure_db_directory(self):
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {str(e)}", exc_info=True)
            raise
        finally:
            conn.close()

    def _initialize_database(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Conversations table - stores conversation metadata
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    conversation_id TEXT UNIQUE NOT NULL,
                    persona TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    title TEXT,
                    is_archived BOOLEAN DEFAULT 0,
                    metadata TEXT
                )
            """)

            # Messages table - stores individual messages
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    model TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    token_count INTEGER,
                    metadata TEXT,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
                )
            """)

            # Financial mentor sessions table - stores financial analysis sessions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS financial_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    session_id TEXT UNIQUE NOT NULL,
                    question TEXT NOT NULL,
                    financial_data TEXT NOT NULL,
                    analysis TEXT NOT NULL,
                    mentor_response TEXT NOT NULL,
                    model TEXT NOT NULL,
                    data_quality TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """)

            # Create indexes for better query performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_user_id
                ON conversations(user_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_created_at
                ON conversations(created_at DESC)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_conversation_id
                ON messages(conversation_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_created_at
                ON messages(created_at)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_financial_sessions_user_id
                ON financial_sessions(user_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_financial_sessions_created_at
                ON financial_sessions(created_at DESC)
            """)

            conn.commit()
            logger.info("Database tables initialized successfully")

    # ==================== CONVERSATION OPERATIONS ====================

    def create_conversation(
        self,
        user_id: str,
        conversation_id: str,
        persona: str = "sharan",
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        logger.info(f"Creating conversation | User: {user_id} | ID: {conversation_id} | Persona: {persona}")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO conversations (user_id, conversation_id, persona, title, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (
                user_id,
                conversation_id,
                persona,
                title,
                json.dumps(metadata) if metadata else None
            ))

        # Query outside of the context to ensure commit happens first
        return self.get_conversation(conversation_id)

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM conversations WHERE conversation_id = ?
            """, (conversation_id,))

            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_user_conversations(
        self,
        user_id: str,
        include_archived: bool = False,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        logger.debug(f"Fetching conversations for user: {user_id}")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            if include_archived:
                cursor.execute("""
                    SELECT * FROM conversations
                    WHERE user_id = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                """, (user_id, limit))
            else:
                cursor.execute("""
                    SELECT * FROM conversations
                    WHERE user_id = ? AND is_archived = 0
                    ORDER BY updated_at DESC
                    LIMIT ?
                """, (user_id, limit))

            return [dict(row) for row in cursor.fetchall()]

    def update_conversation_title(self, conversation_id: str, title: str):
        logger.info(f"Updating conversation title | ID: {conversation_id} | Title: {title}")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE conversations
                SET title = ?, updated_at = CURRENT_TIMESTAMP
                WHERE conversation_id = ?
            """, (title, conversation_id))

    def archive_conversation(self, conversation_id: str):
        logger.info(f"Archiving conversation | ID: {conversation_id}")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE conversations
                SET is_archived = 1, updated_at = CURRENT_TIMESTAMP
                WHERE conversation_id = ?
            """, (conversation_id,))

    # ==================== MESSAGE OPERATIONS ====================

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        model: Optional[str] = None,
        token_count: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        logger.debug(f"Adding message | Conversation: {conversation_id} | Role: {role} | Length: {len(content)} chars")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Add message
            cursor.execute("""
                INSERT INTO messages (conversation_id, role, content, model, token_count, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                conversation_id,
                role,
                content,
                model,
                token_count,
                json.dumps(metadata) if metadata else None
            ))

            message_id = cursor.lastrowid

            # Update conversation updated_at
            cursor.execute("""
                UPDATE conversations
                SET updated_at = CURRENT_TIMESTAMP
                WHERE conversation_id = ?
            """, (conversation_id,))

            # Fetch and return the created message
            cursor.execute("SELECT * FROM messages WHERE id = ?", (message_id,))
            return dict(cursor.fetchone())

    def get_conversation_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        logger.debug(f"Fetching messages for conversation: {conversation_id}")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            if limit:
                cursor.execute("""
                    SELECT * FROM messages
                    WHERE conversation_id = ?
                    ORDER BY created_at ASC
                    LIMIT ?
                """, (conversation_id, limit))
            else:
                cursor.execute("""
                    SELECT * FROM messages
                    WHERE conversation_id = ?
                    ORDER BY created_at ASC
                """, (conversation_id,))

            return [dict(row) for row in cursor.fetchall()]

    def get_conversation_with_messages(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return None

        messages = self.get_conversation_messages(conversation_id)
        conversation['messages'] = messages

        return conversation

    # ==================== FINANCIAL SESSION OPERATIONS ====================

    def save_financial_session(
        self,
        user_id: str,
        session_id: str,
        question: str,
        financial_data: Dict[str, Any],
        analysis: Dict[str, Any],
        mentor_response: str,
        model: str,
        data_quality: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        logger.info(f"Saving financial session | User: {user_id} | Session: {session_id}")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO financial_sessions
                (user_id, session_id, question, financial_data, analysis,
                 mentor_response, model, data_quality, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                session_id,
                question,
                json.dumps(financial_data),
                json.dumps(analysis),
                mentor_response,
                model,
                json.dumps(data_quality),
                json.dumps(metadata) if metadata else None
            ))

            session_id_db = cursor.lastrowid

            cursor.execute("SELECT * FROM financial_sessions WHERE id = ?", (session_id_db,))
            return dict(cursor.fetchone())

    def get_financial_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM financial_sessions WHERE session_id = ?
            """, (session_id,))

            row = cursor.fetchone()
            if row:
                record = dict(row)
                # Parse JSON fields
                record['financial_data'] = json.loads(record['financial_data'])
                record['analysis'] = json.loads(record['analysis'])
                record['data_quality'] = json.loads(record['data_quality'])
                if record['metadata']:
                    record['metadata'] = json.loads(record['metadata'])
                return record
            return None

    def get_user_financial_sessions(
        self,
        user_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        logger.debug(f"Fetching financial sessions for user: {user_id}")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM financial_sessions
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (user_id, limit))

            sessions = []
            for row in cursor.fetchall():
                record = dict(row)
                # Parse JSON fields
                record['financial_data'] = json.loads(record['financial_data'])
                record['analysis'] = json.loads(record['analysis'])
                record['data_quality'] = json.loads(record['data_quality'])
                if record['metadata']:
                    record['metadata'] = json.loads(record['metadata'])
                sessions.append(record)

            return sessions

    # ==================== STATISTICS & ANALYTICS ====================

    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Total conversations
            cursor.execute("""
                SELECT COUNT(*) as total_conversations
                FROM conversations
                WHERE user_id = ?
            """, (user_id,))
            total_conversations = cursor.fetchone()['total_conversations']

            # Total messages
            cursor.execute("""
                SELECT COUNT(*) as total_messages
                FROM messages m
                JOIN conversations c ON m.conversation_id = c.conversation_id
                WHERE c.user_id = ?
            """, (user_id,))
            total_messages = cursor.fetchone()['total_messages']

            # Total financial sessions
            cursor.execute("""
                SELECT COUNT(*) as total_sessions
                FROM financial_sessions
                WHERE user_id = ?
            """, (user_id,))
            total_financial_sessions = cursor.fetchone()['total_sessions']

            return {
                "user_id": user_id,
                "total_conversations": total_conversations,
                "total_messages": total_messages,
                "total_financial_sessions": total_financial_sessions
            }

    def get_recent_activity(self, user_id: str, days: int = 7) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Recent conversations
            cursor.execute("""
                SELECT conversation_id, persona, title, created_at, updated_at
                FROM conversations
                WHERE user_id = ?
                AND datetime(updated_at) >= datetime('now', '-' || ? || ' days')
                ORDER BY updated_at DESC
            """, (user_id, days))
            recent_conversations = [dict(row) for row in cursor.fetchall()]

            # Recent financial sessions
            cursor.execute("""
                SELECT session_id, question, created_at
                FROM financial_sessions
                WHERE user_id = ?
                AND datetime(created_at) >= datetime('now', '-' || ? || ' days')
                ORDER BY created_at DESC
            """, (user_id, days))
            recent_sessions = [dict(row) for row in cursor.fetchall()]

            return {
                "user_id": user_id,
                "days": days,
                "recent_conversations": recent_conversations,
                "recent_financial_sessions": recent_sessions
            }


# Global database instance
_db_instance = None


def get_db() -> ChatDatabase:
    global _db_instance
    if _db_instance is None:
        _db_instance = ChatDatabase()
    return _db_instance
