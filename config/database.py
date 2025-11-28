from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from config.global_logger import get_logger
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

logger = get_logger("database")

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)


class ChatDatabase:
    """
    Chat database using Supabase.

    Required Supabase tables:
    - conversations
    - messages
    - mentor_sessions
    """

    def __init__(self):
        self.supabase = supabase
        logger.info("Chat database initialized with Supabase")

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

        data = {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "persona": persona,
            "title": title,
            "metadata": metadata,
            "is_archived": False
        }

        response = (
            self.supabase.table("conversations")
            .insert(data)
            .execute()
        )

        if response.data:
            return response.data[0]
        return {}

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        response = (
            self.supabase.table("conversations")
            .select("*")
            .eq("conversation_id", conversation_id)
            .execute()
        )

        if response.data:
            return response.data[0]
        return None

    def get_user_conversations(
        self,
        user_id: str,
        include_archived: bool = False,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        logger.debug(f"Fetching conversations for user: {user_id}")

        query = (
            self.supabase.table("conversations")
            .select("*")
            .eq("user_id", user_id)
        )

        if not include_archived:
            query = query.eq("is_archived", False)

        response = (
            query
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
        )

        return response.data or []

    def update_conversation_title(self, conversation_id: str, title: str):
        logger.info(f"Updating conversation title | ID: {conversation_id} | Title: {title}")

        (
            self.supabase.table("conversations")
            .update({
                "title": title,
                "updated_at": datetime.utcnow().isoformat()
            })
            .eq("conversation_id", conversation_id)
            .execute()
        )

    def archive_conversation(self, conversation_id: str):
        logger.info(f"Archiving conversation | ID: {conversation_id}")

        (
            self.supabase.table("conversations")
            .update({
                "is_archived": True,
                "updated_at": datetime.utcnow().isoformat()
            })
            .eq("conversation_id", conversation_id)
            .execute()
        )

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

        # Add message
        data = {
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "model": model,
            "token_count": token_count,
            "metadata": metadata
        }

        response = (
            self.supabase.table("messages")
            .insert(data)
            .execute()
        )

        # Update conversation updated_at
        (
            self.supabase.table("conversations")
            .update({"updated_at": datetime.utcnow().isoformat()})
            .eq("conversation_id", conversation_id)
            .execute()
        )

        if response.data:
            return response.data[0]
        return {}

    def get_conversation_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        logger.debug(f"Fetching messages for conversation: {conversation_id}")

        query = (
            self.supabase.table("messages")
            .select("*")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=False)
        )

        if limit:
            query = query.limit(limit)

        response = query.execute()
        return response.data or []

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

        data = {
            "user_id": user_id,
            "session_id": session_id,
            "question": question,
            "financial_data": financial_data,
            "analysis": analysis,
            "mentor_response": mentor_response,
            "model": model,
            "data_quality": data_quality,
            "metadata": metadata
        }

        response = (
            self.supabase.table("mentor_sessions")
            .insert(data)
            .execute()
        )

        if response.data:
            return response.data[0]
        return {}

    def get_financial_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        response = (
            self.supabase.table("mentor_sessions")
            .select("*")
            .eq("session_id", session_id)
            .execute()
        )

        if response.data:
            return response.data[0]
        return None

    def get_user_financial_sessions(
        self,
        user_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        logger.debug(f"Fetching financial sessions for user: {user_id}")

        response = (
            self.supabase.table("mentor_sessions")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        return response.data or []

    # ==================== STATISTICS & ANALYTICS ====================

    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        # Total conversations
        conv_response = (
            self.supabase.table("conversations")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .execute()
        )
        total_conversations = conv_response.count or 0

        # Get conversation IDs for message count
        conv_ids_response = (
            self.supabase.table("conversations")
            .select("conversation_id")
            .eq("user_id", user_id)
            .execute()
        )
        conv_ids = [c["conversation_id"] for c in (conv_ids_response.data or [])]

        # Total messages
        total_messages = 0
        if conv_ids:
            msg_response = (
                self.supabase.table("messages")
                .select("id", count="exact")
                .in_("conversation_id", conv_ids)
                .execute()
            )
            total_messages = msg_response.count or 0

        # Total financial sessions
        sessions_response = (
            self.supabase.table("mentor_sessions")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .execute()
        )
        total_financial_sessions = sessions_response.count or 0

        return {
            "user_id": user_id,
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "total_financial_sessions": total_financial_sessions
        }

    def get_recent_activity(self, user_id: str, days: int = 7) -> Dict[str, Any]:
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

        # Recent conversations
        conv_response = (
            self.supabase.table("conversations")
            .select("conversation_id, persona, title, created_at, updated_at")
            .eq("user_id", user_id)
            .gte("updated_at", cutoff_date)
            .order("updated_at", desc=True)
            .execute()
        )
        recent_conversations = conv_response.data or []

        # Recent financial sessions
        sessions_response = (
            self.supabase.table("mentor_sessions")
            .select("session_id, question, created_at")
            .eq("user_id", user_id)
            .gte("created_at", cutoff_date)
            .order("created_at", desc=True)
            .execute()
        )
        recent_sessions = sessions_response.data or []

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
