from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from jose import jwt, JWTError
from dotenv import load_dotenv
from config.global_logger import get_logger
import os

logger = get_logger(__name__)
load_dotenv()

def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, os.getenv("SECRET_KEY"))
        return payload
    except JWTError:
        logger.error(f"Error while verifying jwt: {JWTError}", exc_info=True)
        return None

class JWTBearer(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)

    async def __call__(self, request: Request) -> dict:
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)

        if not credentials:
            raise HTTPException(status_code=403, detail="Invalid authorization")

        if credentials.scheme != "Bearer":
            raise HTTPException(status_code=403, detail="Invalid authentication scheme")

        payload = verify_token(credentials.credentials)
        if not payload:
            raise HTTPException(status_code=403, detail="Invalid or expired token")

        return payload  # Contains user_id, email, etc.
