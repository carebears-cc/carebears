import os
import logging
import json
import re
from fastapi import FastAPI, HTTPException, Request, Form, Depends, File, UploadFile
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from tempfile import NamedTemporaryFile
from pathlib import Path
from markupsafe import Markup
from dotenv import load_dotenv

# Import local modules
from .models import (
    PatientCreate, PatientResponse, 
    InteractionCreate, InteractionResponse,
    PromptRequest, PromptResponse
)
from .database import (
    init_db, add_patient, get_patient, 
    get_patient_interactions, update_patient_context
)
from .services import process_prompt, initialize_gemini, extract_patient_info_from_text

# Import Logfire for observability
import logfire

# load_dotenv
load_dotenv()

# --- Logfire Configuration ---
LOGFIRE_TOKEN = os.getenv("LOGFIRE_TOKEN")
logfire.configure(
    token=LOGFIRE_TOKEN,
    service_name="carebears-app"
)

# Configure standard logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.info("CareBears application starting up.")

# Get the absolute path to the directory where this file (main.py) resides.
# Inside the container, this will be /app/
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Construct the absolute path to the 'static' directory
# This correctly points to /app/static
STATIC_FILES_DIR = os.path.join(BASE_DIR, "static")
# --- NEW: Construct the absolute path to the 'templates' directory ---
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# --- FastAPI App Initialization ---
app = FastAPI(
    title="CareBears",
    description="AI companion for patients with chronic conditions and their caregivers.",
    version="1.0.0"
)

# --- Helper Functions for Templating ---
def format_llm_response(text):
    """
    Format LLM response by:
    1. Extracting and formatting the 'response' field from JSON if present
    2. Detecting and formatting JSON blocks
    3. Converting markdown-like formatting to HTML
    4. Hiding context tags from display
    """
    if not text:
        return ""
    
    # First, check if the entire text is a JSON object with a 'response' field
    try:
        # Try to parse the entire text as JSON
        json_obj = json.loads(text)
        # If it's a JSON object with a 'response' key, extract and process that
        if isinstance(json_obj, dict) and 'response' in json_obj:
            # The 'response' field might contain markdown, so we'll process it
            response_text = json_obj['response']
            # Continue processing with the extracted response text
            text = response_text
    except json.JSONDecodeError:
        # Not a JSON object, continue with normal processing
        pass
    
    # Remove context sections as they're displayed separately
    text = re.sub(r'<context>.*?</context>', '', text, flags=re.DOTALL)
    
    # Function to replace JSON blocks with formatted HTML
    def replace_json(match):
        try:
            # Try to parse the JSON
            json_str = match.group(1).strip()
            parsed = json.loads(json_str)
            
            # Apply syntax highlighting with classes
            def highlight_json(obj, indent=0):
                result = ""
                if isinstance(obj, dict):
                    result += "{\n"
                    items = list(obj.items())
                    for i, (key, value) in enumerate(items):
                        result += " " * ((indent + 1) * 2)
                        result += f'<span class="key">"{key}"</span>: '
                        result += highlight_json(value, indent + 1)
                        if i < len(items) - 1:
                            result += ","
                        result += "\n"
                    result += " " * (indent * 2) + "}"
                elif isinstance(obj, list):
                    result += "[\n"
                    for i, item in enumerate(obj):
                        result += " " * ((indent + 1) * 2)
                        result += highlight_json(item, indent + 1)
                        if i < len(obj) - 1:
                            result += ","
                        result += "\n"
                    result += " " * (indent * 2) + "]"
                elif isinstance(obj, str):
                    result += f'<span class="string">"{obj}"</span>'
                elif isinstance(obj, (int, float)):
                    result += f'<span class="number">{obj}</span>'
                elif isinstance(obj, bool):
                    result += f'<span class="boolean">{str(obj).lower()}</span>'
                elif obj is None:
                    result += f'<span class="null">null</span>'
                return result
            
            # Format with syntax highlighting
            formatted = highlight_json(parsed)
            
            # Wrap in a styled div
            return f'<div class="json-block"><pre>{formatted}</pre></div>'
        except json.JSONDecodeError:
            # If it's not valid JSON, return the original text
            return match.group(0)
    
    # Find and format JSON-like blocks (enclosed in ```json or just {})
    text = re.sub(r'```json\s*(.*?)\s*```', replace_json, text, flags=re.DOTALL)
    text = re.sub(r'```\s*({.*?})\s*```', replace_json, text, flags=re.DOTALL)
    
    # Handle generic code blocks, removing the code fence markers
    def replace_generic_code_block(match):
        language = match.group(1) or ""
        code_content = match.group(2)
        if language and language != "json":  # JSON already handled above
            return f'<div class="code-block {language}"><pre>{code_content}</pre></div>'
        return code_content  # Just return the content without the fences
        
    # Remove triple backticks with language specifier
    text = re.sub(r'```(\w*)\s*(.*?)\s*```', replace_generic_code_block, text, flags=re.DOTALL)
    
    # Also catch standalone JSON objects
    standalone_json_pattern = r'^\s*({[\s\S]*})\s*$'
    if re.match(standalone_json_pattern, text):
        text = re.sub(standalone_json_pattern, replace_json, text, flags=re.DOTALL)
    
    # Convert markdown-style formatting
    # Bold
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    # Italic
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
    # Headers
    text = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)
    
    # Lists
    def replace_list(match):
        items = match.group(0).split('\n')
        list_html = '<ul>'
        for item in items:
            if item.strip().startswith('- '):
                list_item = item.strip()[2:]
                list_html += f'<li>{list_item}</li>'
        list_html += '</ul>'
        return list_html
    
    text = re.sub(r'(^- .*?$\n?)+', replace_list, text, flags=re.MULTILINE)
    
    # Convert newlines to <br> for HTML display
    text = text.replace('\n', '<br>')
    
    return Markup(text)

# --- Templating and Static Files Setup ---
templates = Jinja2Templates(directory=TEMPLATES_DIR)
app.mount("/static", StaticFiles(directory=STATIC_FILES_DIR), name="static")

# Register custom filters
templates.env.filters["format_llm_response"] = format_llm_response

# --- Startup Event to Initialize Database and Gemini ---
@app.on_event("startup")
async def startup_event():
    init_db()
    initialize_gemini()
    logger.info("Database and Gemini model initialized")

# --- API Routes ---

# Patient routes
@app.post("/api/patients", response_model=PatientResponse)
@logfire.instrument("Create patient")
async def create_patient(patient: PatientCreate):
    """Create a new patient record"""
    try:
        patient_id = add_patient(
            name=patient.name,
            dob=patient.dob,
            location=patient.location,
            diagnosis=patient.diagnosis,
            care_gaps=patient.care_gaps
        )
        
        # Get the created patient to return
        created_patient = get_patient(patient_id)
        if created_patient:
            return created_patient
        else:
            raise HTTPException(status_code=500, detail="Failed to retrieve created patient")
    except Exception as e:
        logger.error(f"Error creating patient: {e}")
        logfire.error("Patient creation failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create patient: {str(e)}")

@app.get("/api/patients/{patient_id}", response_model=PatientResponse)
@logfire.instrument("Get patient")
async def get_patient_info(patient_id: int):
    """Get a patient's information"""
    patient_data = get_patient(patient_id)
    if patient_data:
        return patient_data
    raise HTTPException(status_code=404, detail=f"Patient with ID {patient_id} not found")

@app.get("/api/patients/{patient_id}/interactions")
@logfire.instrument("Get patient interactions")
async def get_interactions(patient_id: int, limit: int = 10):
    """Get a patient's recent interactions"""
    patient_data = get_patient(patient_id)
    if not patient_data:
        raise HTTPException(status_code=404, detail=f"Patient with ID {patient_id} not found")
        
    interactions = get_patient_interactions(patient_id, limit)
    return {"interactions": interactions}

# Prompt processing route
@app.post("/api/prompts", response_model=PromptResponse)
@logfire.instrument("Process prompt")
async def process_user_prompt(request: PromptRequest):
    """Process a user prompt with the Gemini model and update patient context"""
    try:
        # Process the prompt and get response with updated context
        response_text, updated_context = process_prompt(
            prompt_type=request.prompt_type,
            patient_id=request.patient_id,
            user_input=request.user_input
        )
        
        # Return the model response and updated context
        return PromptResponse(
            response=response_text,
            updated_context=updated_context
        )
    except Exception as e:
        logger.error(f"Error processing prompt: {e}")
        logfire.error("Prompt processing failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to process prompt: {str(e)}")

# --- Web UI Routes ---

@app.get("/", response_class=HTMLResponse)
@logfire.instrument("Get home page")
async def get_home(request: Request):
    """Display the home page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload-patient-file", response_class=HTMLResponse)
@logfire.instrument("Upload patient file")
async def upload_patient_file(request: Request, file: UploadFile = File(...)):
    """
    Process a text file containing patient information, extract data using LLM,
    and create a new patient record
    """
    try:
        # Create a temporary file to store the uploaded content
        with NamedTemporaryFile(delete=False) as temp_file:
            # Read content from the uploaded file
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
            
        # Read the temporary file content as text
        with open(temp_file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
            
        # Delete the temporary file
        os.unlink(temp_file_path)
        
        # Extract patient information using the LLM
        patient_data = extract_patient_info_from_text(file_content)
        
        # Check if extraction was successful
        if "error" in patient_data:
            return templates.TemplateResponse(
                "index.html", 
                {"request": request, "error": patient_data["error"]}
            )
        
        # Create the patient record
        patient_id = add_patient(
            name=patient_data.get("name", ""),
            dob=patient_data.get("dob", ""),
            location=patient_data.get("location", ""),
            diagnosis=patient_data.get("diagnosis", ""),
            care_gaps=patient_data.get("care_gaps", None),
            context={"source": "file_upload", "raw_text": file_content}
        )
        
        # Redirect to the patient page
        return RedirectResponse(url=f"/patients/{patient_id}", status_code=303)
        
    except Exception as e:
        logger.error(f"Error processing patient file: {e}")
        logfire.error("Patient file processing failed", error=str(e))
        return templates.TemplateResponse(
            "index.html", 
            {"request": request, "error": f"Failed to process file: {str(e)}"}
        )

@app.get("/patients/{patient_id}", response_class=HTMLResponse)
@logfire.instrument("Get patient UI")
async def get_patient_ui(request: Request, patient_id: int):
    """Display the patient interface"""
    patient_data = get_patient(patient_id)
    if not patient_data:
        return RedirectResponse(url="/")
        
    return templates.TemplateResponse(
        "patient.html", 
        {"request": request, "patient": patient_data}
    )

@app.post("/patients/{patient_id}/prompt", response_class=HTMLResponse)
@logfire.instrument("Patient prompt UI")
async def post_patient_prompt(
    request: Request, 
    patient_id: int, 
    prompt_type: str = Form(...),
    user_input: str = Form(...)
):
    """Process a patient prompt from the UI"""
    patient_data = get_patient(patient_id)
    if not patient_data:
        return RedirectResponse(url="/")
    
    # Process the prompt
    response_text, updated_context = process_prompt(
        prompt_type=prompt_type,
        patient_id=patient_id,
        user_input=user_input
    )
    
    # Get the patient's updated information
    updated_patient = get_patient(patient_id)
    
    # Get recent interactions
    interactions = get_patient_interactions(patient_id, limit=5)
    
    return templates.TemplateResponse(
        "patient.html", 
        {
            "request": request, 
            "patient": updated_patient,
            "interactions": interactions,
            "response": response_text,
            "prompt_type": prompt_type,
            "user_input": user_input
        }
    )

# Health check endpoint
@app.get("/health")
def health_check():
    """Simple health check endpoint"""
    return {"status": "ok"}

# Run the application using:
# GOOGLE_API_KEY="YOUR_GOOGLE_API_KEY" LOGFIRE_TOKEN="YOUR_LOGFIRE_TOKEN" uvicorn app.main:app --reload
