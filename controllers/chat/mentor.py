from config.global_logger import get_logger
from config.database import get_db
import os
from dotenv import load_dotenv
import uuid
from pydantic import BaseModel
from google.generativeai.types import GenerationConfig
import google.generativeai as genai
from functions.mentor_prompt_builder import get_system_prompt
from functions.finance_analyzer import analyze_financial_data
from functions.fi_data import get_fi_data
from typing import Optional
import time

load_dotenv()

logger = get_logger(__name__)

class FinancialMentorRequest(BaseModel):
    id: str
    message: Optional[str] = "Analyze my financial behavior and provide mentorship advice"

class FinancialMentorResponse(BaseModel):
    id: str
    mentorResponse: str
    model: str = "gemini-2.5-flash"

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

async def financial_mentor(request: FinancialMentorRequest, user_id: str):
    db = get_db()
    request_id = str(uuid.uuid4())

    financial_data = get_fi_data(user_id=user_id)
    logger.info(
        f"Financial Mentor API called | User ID: {user_id} | Question: {request.message[:100]}... | Request ID: {request_id}",
        extra={"request_id": request_id, "user_id": user_id, "endpoint": "/api/v1/financial-mentor"}
    )


    try:
        # Step 1: Validate and analyze financial data
        logger.info(f"Step 1: Getting financial Data | Request ID: {request_id}", extra={"request_id": request_id})
        data = analyze_financial_data(financial_data)
        logger.info(f"Data: {data}")
        #Step 2: Build system prompt
        logger.info(f"Step 2: Building System Prompt | Request ID: {request_id}", extra={"request_id": request_id})
        system_prompt = get_system_prompt(data)

        # Step 3: Generate AI mentor response with optimized config
        logger.info(f"Step 3: Generating AI mentor response | Request ID: {request_id}", extra={"request_id": request_id})
        try:
            # Configure generation parameters for financial mentorship
            # Using slightly lower temperature for more consistent financial advice
            logger.debug(
                f"Configuring Gemini model | temperature=0.8, top_p=0.95, top_k=40 | Request ID: {request_id}",
                extra={"request_id": request_id}
            )

            generation_config = GenerationConfig(
                temperature=0.8,  # Slightly lower for financial advice consistency
                top_p=0.95,
                top_k=40,
                max_output_tokens=3000,  # Allow longer responses for detailed advice
            )

            # Initialize Gemini model with financial mentor persona
            model = genai.GenerativeModel(
                model_name='gemini-2.5-flash',
                system_instruction=system_prompt,
                generation_config=generation_config
            )

            logger.info(f"Calling Gemini API for financial mentorship | Request ID: {request_id}", extra={"request_id": request_id})

            # Generate response
            response = model.generate_content(request.message)
            mentor_response = response.text

            logger.info(
                f"Mentor response generated | Response length: {len(mentor_response)} chars | Request ID: {request_id}",
                extra={"request_id": request_id, "response_length": len(mentor_response)}
            )

        except Exception as error:
            extra = {"request_id": request_id} if request_id else {}
            logger.error(
                f"Error in financial_mentor: {type(error).__name__}: {str(error)}",
                exc_info=True,
                extra=extra
            )
            kwargs = {"request_id": request_id, "user_id": request.id}
            logger.error(f"Error context: {kwargs}", extra=extra)


        # Step 4: Save financial session to database
        logger.info(f"Saving financial session to database | Request ID: {request_id}", extra={"request_id": request_id})
        session_id = f"fin_session_{request.id}_{int(time.time())}"
        db.save_financial_session(
            user_id=request.id,
            session_id=session_id,
            question=request.message,
            financial_data=financial_data,
            analysis="",
            mentor_response=mentor_response,
            model="gemini-2.5-flash",
            data_quality={},
            metadata={"request_id": request_id}
        )

        # Step 5: Return comprehensive response
        logger.info(
            f"Financial mentor analysis completed and saved | User ID: {request.id} | Session ID: {session_id} | Request ID: {request_id}",
            extra={"request_id": request_id, "user_id": request.id, "session_id": session_id}
        )

        return FinancialMentorResponse(
            id=request.id,
            mentorResponse=mentor_response,
            model="gemini-2.5-flash",
        )

    except Exception as error:
        extra = {"request_id": request_id} if request_id else {}
        logger.error(
            f"Error in financial_mentor: {type(error).__name__}: {str(error)}",
            exc_info=True,
            extra=extra
        )
        kwargs = {"request_id": request_id, "user_id": request.id}
        logger.error(f"Error context: {kwargs}", extra=extra)
        return FinancialMentorResponse(id=request.id, mentorResponse="Sorry, something went wrong, so I will be on a break", model="gemini-2.5-flash",)
