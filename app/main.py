import os
import time
import logging
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# Import Google's Generative AI library
from google import genai

# Import Logfire
import logfire

# --- Logfire Configuration ---
# Logfire needs to be configured early.
# It typically picks up the LOGFIRE_TOKEN from environment variables.
# It also instruments FastAPI automatically if installed before app creation.
# For local development, you might use the `logfire dev` command.
LOGFIRE_TOKEN=os.environ.get("LOGFIRE_TOKEN")
logfire.configure(token=LOGFIRE_TOKEN)
# You can add default attributes to all logs/spans if needed:
# logfire.set_global_attributes({"app_name": "gemini-fastapi-app"})


# --- Standard Library Logging (Logfire integrates with this) ---
# Configure standard logging. Logfire will often enhance or capture these logs.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.info("Application starting up.")


# --- FastAPI App Initialization ---
# Logfire auto-instruments FastAPI, so instantiate the app after logfire.configure()
app = FastAPI(
    title="Gemini FastAPI App with Logfire",
    description="Simple API to query Google Gemini model with observability via Logfire.",
    version="1.0.0"
)

# --- Templating Setup ---
# Configure Jinja2Templates to look for templates in the "templates" directory
templates = Jinja2Templates(directory="templates")

# --- Pydantic Models for Request and Response ---

# Request body validation
class PromptRequest(BaseModel):
    prompt: str
    # Add other potential parameters here, e.g.:
    # temperature: float = 0.7
    # max_output_tokens: int = 100

# Response body structure
class GeminiResponse(BaseModel):
    input_prompt: str
    output_text: str
    duration_seconds: float
    model_name: str
    # You could add more fields captured from the API response or Logfire data


# --- Gemini Configuration (Global instance for simplicity) ---
# Get Google API key from environment variable
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# Define the model name
GEMINI_MODEL_NAME = "gemini-2.0-flash" # Or other available Gemini model

# Initialize the Gemini model instance (done once on startup)
gemini_model = None

# FastAPI Startup Event to initialize the Gemini model
@app.on_event("startup")
async def startup_event():
    global gemini_model
    if not GOOGLE_API_KEY:
        logger.error("GOOGLE_API_KEY environment variable is not set. Gemini model will not be initialized.")
        # Log this event with Logfire as well
        logfire.error("Gemini model initialization skipped - missing GOOGLE_API_KEY")
        return # Exit startup if key is missing

    try:
        gemini_model = genai.Client(api_key=GOOGLE_API_KEY)
        logger.info(f"Successfully initialized Gemini model: {GEMINI_MODEL_NAME}")
        # Log success with Logfire. Logfire understands dicts and Pydantic models.
        logfire.info("Gemini model initialized successfully", model_name=GEMINI_MODEL_NAME)
    except Exception as e:
         logger.error(f"Failed to initialize Gemini model: {e}", exc_info=True)
         # Log the failure with Logfire
         logfire.error("Failed to initialize Gemini model", error=str(e), model_name=GEMINI_MODEL_NAME)


# --- FastAPI Route to Generate Text ---
# Use logfire.instrument to automatically create a span for this function
# Logfire also instruments FastAPI request handling automatically
@app.post("/generate", response_model=GeminiResponse)
@logfire.instrument("POST /generate endpoint") # Adds a Logfire span around this handler
async def generate_text(request: PromptRequest):
    """
    Receives a prompt, queries the Gemini model, and returns the response.
    This function is instrumented by Logfire.
    """
    # Log the incoming prompt using Logfire - Logfire understands Pydantic models
    # logfire.info("Received prompt request", prompt_request=request) # Option 1: log the Pydantic model
    logfire.info("Received prompt request", prompt=request.prompt) # Option 2: log specific fields


    if gemini_model is None:
        error_msg = "Gemini model not initialized. Please ensure GOOGLE_API_KEY is set correctly."
        logger.error(error_msg)
        logfire.error("API call failed: Model not initialized", detail=error_msg) # Log error with Logfire
        raise HTTPException(status_code=500, detail=error_msg)

    start_time = time.time()
    response_text = None
    error_message = None

    try:
        # Use a Logfire span to time and add context to the external API call
        with logfire.span("Calling Gemini API", model=GEMINI_MODEL_NAME, prompt_length=len(request.prompt)):
             ai_response = gemini_model.models.generate_content(model=GEMINI_MODEL_NAME, contents=request.prompt)
             response_text = ai_response.text

        end_time = time.time()
        duration = end_time - start_time

        logger.info(f"Gemini call finished in {duration:.4f}s")
        # Log the successful API call details with Logfire
        logfire.info("Gemini API call successful",
                     model_name=GEMINI_MODEL_NAME,
                     duration_seconds=duration,
                     response_length=len(response_text),
                     # response_text=response_text # Be cautious logging full large responses
                     )

        # Return the structured response
        return GeminiResponse(
            input_prompt=request.prompt,
            output_text=response_text,
            duration_seconds=duration,
            model_name=GEMINI_MODEL_NAME
        )

    except Exception as e:
        end_time = time.time() # Capture end time even on error
        duration = end_time - start_time
        error_message = str(e)
        logger.error(f"Error during Gemini call: {e}", exc_info=True) # Log exception details in stdlib logs

        # Log the error event with Logfire, including relevant context
        logfire.error(
            "Error during Gemini API call",
            error_type=type(e).__name__,
            error_message=error_message,
            duration_seconds=duration,
            model_name=GEMINI_MODEL_NAME,
            prompt_preview=request.prompt[:100] + "..." if len(request.prompt) > 100 else request.prompt # Log preview
        )
        # Re-raise HTTPException to return a proper API error response
        raise HTTPException(status_code=500, detail=f"Error generating text: {error_message}")

# --- FastAPI Route for Web UI (GET) ---
# Handles displaying the HTML form
@app.get("/", response_class=HTMLResponse)
@logfire.instrument("GET / UI endpoint") # Logfire span
async def get_ui(request: Request):
    """
    Displays the HTML form for the UI.
    """
    # Render the template with no initial data
    return templates.TemplateResponse("index.html", {"request": request, "prompt": "", "response": None, "error": None, "duration_seconds": None})

# --- FastAPI Route for Web UI (POST) ---
# Handles processing the form submission and displaying result
@app.post("/", response_class=HTMLResponse)
@logfire.instrument("POST / UI endpoint") # Logfire span
async def post_ui(request: Request, prompt: str = Form(...)):
    """
    Processes the form submission from the UI, calls Gemini, and displays the result.
    Expects form data field: 'prompt'
    """
    logger.info(f"Received UI form submission.")
    # Using prompt variable captured by Form(...)
    logfire.info("Processing UI form submission", prompt=prompt)

    response_text, duration, error_message = await call_gemini_model(prompt)

    # Render the template with the submitted prompt and the result/error
    # The template will decide what to display based on which variables are not None
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "prompt": prompt,
            "response": response_text,
            "error": error_message,
            "duration_seconds": duration,
        }
    )

# --- Optional: Health Check Route ---
@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}

# To run this app, save it as main.py and use:
# GOOGLE_API_KEY="YOUR_GOOGLE_API_KEY" LOGFIRE_TOKEN="YOUR_LOGFIRE_TOKEN" uvicorn main:app --reload
# (Or set environment variables separately)
