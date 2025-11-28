from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from controllers.chat.persona import persona_chat, ChatRequest
from auth.jwt_bearer import verify_token
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class ChatResponse(BaseModel):
    id: str
    response: str
    model: str = "gemini-2.5-flash"
    conversation_id: Optional[str] = None  # Returned conversation ID for reference

router = APIRouter(prefix= "/persona")

async def persona_route(request: ChatRequest, token: str = Depends(oauth2_scheme)):
    print(request, token)
    token_data = verify_token(token=token)
    user_id = token_data.get("user_id")
    return await persona_chat(request, user_id)

router.add_api_route("/chat", persona_route, methods=["POST"], response_model=ChatResponse)
