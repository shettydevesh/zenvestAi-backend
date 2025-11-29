from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from controllers.chat.mentor import financial_mentor
from auth.jwt_bearer import verify_token
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class FinancialMentorRequest(BaseModel):
    id: str
    message: Optional[str] = "Analyze my financial behavior and provide mentorship advice"


class FinancialMentorResponse(BaseModel):
    id: str
    user_id: str
    mentorResponse: str
    model: str = "gemini-2.5-flash"

router = APIRouter(prefix= "/mentor")

async def mentor_route(request: FinancialMentorRequest, token: str = Depends(oauth2_scheme)):
    print(request, token)
    token_data = verify_token(token=token)
    user_id = token_data.get("user_id")
    return await financial_mentor(request, user_id)

router.add_api_route("/chat", mentor_route, methods=["POST"], response_model=FinancialMentorResponse)
