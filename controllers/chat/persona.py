from config.global_logger import get_logger
from config.database import get_db
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from google.generativeai.types import GenerationConfig
import google.generativeai as genai
from constants.persona_message import sharan
from typing import Optional
import time
import random

load_dotenv()

logger = get_logger(__name__)

class ChatMessage(BaseModel):
    role: str  # "user" or "model"
    parts: str  # message content

class ChatRequest(BaseModel):
    id: str
    message: str
    conversation_id: Optional[str] = None  # For continuing existing conversations
    save_conversation: bool = True  # Whether to save the conversation to database

class ChatResponse(BaseModel):
    id: str
    response: str
    model: str = "gemini-2.5-flash"
    conversation_id: Optional[str] = None  # Returned conversation ID for reference

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

async def persona_chat(request: ChatRequest):
    request_id = random.randint(3, 99999)
    db = get_db()

    # Determine conversation ID
    conversation_id = request.conversation_id or f"conv_{request.id}_{int(time.time())}"

    logger.info(
        f"Chat API called | User ID: {request.id} | Message length: {len(request.message)} chars | "
        f"Conversation ID: {conversation_id} | Request ID: {request_id}",
        extra={"request_id": request_id, "user_id": request.id, "endpoint": "/api/v1/chat"}
    )

    if not os.getenv("GEMINI_API_KEY"):
        logger.error(f"GEMINI_API_KEY not configured | Request ID: {request_id}", extra={"request_id": request_id})

    try:
        existing_conversation = db.get_conversation(conversation_id)
        if not existing_conversation:
            logger.info(f"Creating new conversation | ID: {conversation_id} | Request ID: {request_id}", extra={"request_id": request_id})
            db.create_conversation(
                user_id=request.id,
                conversation_id=conversation_id,
                persona="sharan",
                title=request.message[:100] if len(request.message) <= 100 else request.message[:97] + "..."
            )
        else:
            logger.info(f"Continuing existing conversation | ID: {conversation_id} | Request ID: {request_id}", extra={"request_id": request_id})

        # Step 2: Load conversation history from database
        history_messages = []
        if request.conversation_id:
            logger.info(f"Loading conversation history from database | Request ID: {request_id}", extra={"request_id": request_id})
            stored_messages = db.get_conversation_messages(conversation_id)
            logger.info(f"Loaded {len(stored_messages)} messages from history | Request ID: {request_id}", extra={"request_id": request_id})

            # Convert database messages to API format
            for msg in stored_messages:
                history_messages.append({
                    "role": msg['role'],
                    "parts": [msg['content']]
                })

        # Step 3: Save user message to database
        db.add_message(
            conversation_id=conversation_id,
            role="user",
            content=request.message,
            metadata={"request_id": request_id}
        )

        # Step 4: Configure and call Gemini API
        logger.debug(
            f"Configuring Gemini model | temperature=1.0, top_p=0.95, top_k=40 | Request ID: {request_id}",
            extra={"request_id": request_id}
        )

        generation_config = GenerationConfig(
            temperature=1.0,  # Default for Gemini 2.5 models
            top_p=0.95,
            top_k=40,
            max_output_tokens=2048,
        )

        # Initialize Gemini model with system instruction
        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            system_instruction=sharan,
            generation_config=generation_config
        )

        logger.info(f"Gemini model initialized successfully | Request ID: {request_id}", extra={"request_id": request_id})

        # Build conversation content with history
        if history_messages:
            logger.info(
                f"Building conversation with history | History messages: {len(history_messages)} | Request ID: {request_id}",
                extra={"request_id": request_id}
            )

            # Add current message
            history_messages.append({
                "role": "user",
                "parts": [request.message]
            })

            # Generate response with full conversation context
            logger.info(f"Calling Gemini API with conversation context | Request ID: {request_id}", extra={"request_id": request_id})
            response = model.generate_content(history_messages)
        else:
            # Single turn conversation
            logger.info(f"Calling Gemini API for single-turn chat | Request ID: {request_id}", extra={"request_id": request_id})
            response = model.generate_content(request.message)

        response_text = response.text

        # Step 5: Save AI response to database
        if request.save_conversation:
            logger.debug(f"Saving AI response to database | Request ID: {request_id}", extra={"request_id": request_id})
            db.add_message(
                conversation_id=conversation_id,
                role="model",
                content=response_text,
                model="gemini-2.5-flash",
                metadata={"request_id": request_id}
            )

        logger.info(
            f"Chat response generated and saved | User ID: {request.id} | Response length: {len(response_text)} chars | "
            f"Conversation ID: {conversation_id} | Request ID: {request_id}",
            extra={"request_id": request_id, "user_id": request.id, "response_length": len(response_text)}
        )

        return ChatResponse(
            id=request.id,
            response=response_text,
            model="gemini-2.5-flash",
            conversation_id=conversation_id
        )

    except Exception as error:
        extra = {"request_id": request_id} if request_id else {}
        logger.error(
            f"Error in persona_chat: {type(error).__name__}: {str(error)}",
            exc_info=True,
            extra=extra
        )
        kwargs = {"request_id": request_id, "user_id": request.id}
        logger.error(f"Error context: {kwargs}", extra=extra)
        return None
