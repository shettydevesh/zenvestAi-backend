from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uuid
import time
import os
from dotenv import load_dotenv
from config.global_logger import setup_logger
from routes import personaRoutes, mentorRoutes

load_dotenv()

logger = setup_logger(
    name="zenvest_ai",
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    log_file="logs/app.log",
    enable_console=True,
    enable_file=True,
    json_logs=False
)

app = FastAPI(
    title="Zenvest AI Backend",
    description="Backend API for Zenvest AI application",
    version="0.1.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(personaRoutes.router, prefix="/api/v1")
app.include_router(mentorRoutes.router, prefix="/api/v1")

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware to log all HTTP requests and responses"""
    request_id = str(uuid.uuid4())
    start_time = time.time()

    # Log request
    logger.info(
        f"Incoming Request | {request.method} {request.url.path} | Request ID: {request_id}",
        extra={
            "request_id": request_id,
            "endpoint": request.url.path,
            "method": request.method
        }
    )

    # Store request_id in request state for use in endpoints
    request.state.request_id = request_id

    # Process request
    try:
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000

        # Log response
        logger.info(
            f"Response | {request.method} {request.url.path} | Status: {response.status_code} | "
            f"Duration: {duration_ms:.2f}ms | Request ID: {request_id}",
            extra={
                "request_id": request_id,
                "endpoint": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms
            }
        )

        return response

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Request Failed | {request.method} {request.url.path} | "
            f"Error: {type(e).__name__}: {str(e)} | Duration: {duration_ms:.2f}ms | Request ID: {request_id}",
            exc_info=True,
            extra={
                "request_id": request_id,
                "endpoint": request.url.path,
                "duration_ms": duration_ms
            }
        )
        raise
