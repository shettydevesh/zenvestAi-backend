from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from controllers.chat.persona import persona_chat

class ChatResponse(BaseModel):
    id: str
    response: str
    model: str = "gemini-2.5-flash"
    conversation_id: Optional[str] = None  # Returned conversation ID for reference

router = APIRouter(prefix= "/persona")

router.add_api_route("/chat", persona_chat, methods=["POST"], response_model=ChatResponse)
