import os
import re
import json
import logging
import time
from typing import Dict, Tuple, Any, Optional

from google import genai
import logfire

from models import PROMPT_TEMPLATES
from database import get_patient, update_patient_context, add_interaction

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the Gemini client
gemini_client = None

def initialize_gemini():
    """Initialize the Gemini client if API key is available"""
    global gemini_client

    # Initialize the Gemini model
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    GEMINI_MODEL_NAME = "gemini-2.0-flash"  # or any other appropriate model

    if GOOGLE_API_KEY:
        try:
            gemini_client = genai.Client(api_key=GOOGLE_API_KEY)
            logfire.info("Gemini model initialized successfully", model_name=GEMINI_MODEL_NAME)
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Gemini model: {e}")
            logfire.error("Failed to initialize Gemini model", error=str(e))
    else:
        logger.error("GOOGLE_API_KEY is not set")
        logfire.error("GOOGLE_API_KEY not set, Gemini model not initialized")
    return False

def extract_context(response_text: str) -> Optional[Dict[str, Any]]:
    """Extract context information from the model response"""
    if not response_text:
        return None
        
    # Use regex to extract content between <context> and </context> tags
    context_pattern = r'<context>(.*?)</context>'
    match = re.search(context_pattern, response_text, re.DOTALL)
    
    if match:
        context_text = match.group(1).strip()
        try:
            # Try to parse as JSON first
            return json.loads(context_text)
        except json.JSONDecodeError:
            # If not valid JSON, create a simple dict with the text
            return {"raw_context": context_text}
    
    return None
    
def extract_patient_info_from_text(text: str) -> Dict[str, Any]:
    """
    Use LLM to extract patient information from text file
    
    Args:
        text: Raw text containing patient information
        
    Returns:
        Dictionary with extracted patient information
    """
    if gemini_client is None:
        if not initialize_gemini():
            return {"error": "Unable to initialize AI model. Please check API key."}
    
    # Create a prompt for the LLM to extract patient info
    extraction_prompt = f"""
    Extract the following patient information from the text below:
    1. Full Name
    2. Date of Birth (in MM/DD/YYYY format)
    3. Location (including ZIP code if available)
    4. Primary Diagnosis
    5. Care Gaps (if any)
    
    Provide the output in the following JSON format:
    {{
        "name": "Patient Name",
        "dob": "MM/DD/YYYY",
        "location": "City, State ZIP",
        "diagnosis": "Primary diagnosis",
        "care_gaps": "Description of care gaps"
    }}
    
    If any field is not present in the text, use null for that field.
    Do not hallucinate information that is not in the text.
    Only include the JSON in your response, no additional text.
    
    TEXT:
    {text}
    """
    
    try:
        # Call the Gemini API
        with logfire.span("Calling Gemini API for patient extraction", model=GEMINI_MODEL_NAME):
            response = gemini_client.models.generate_content(model=GEMINI_MODEL_NAME, contents=extraction_prompt)
            response_text = response.text
            
        # Try to parse the response as JSON
        try:
            # Clean up the response to extract just the JSON part (if there's any extra text)
            json_pattern = r'{[\s\S]*}'
            json_match = re.search(json_pattern, response_text)
            if json_match:
                response_text = json_match.group(0)
                
            patient_data = json.loads(response_text)
            logfire.info("Successfully extracted patient information from text", fields=list(patient_data.keys()))
            return patient_data
        except json.JSONDecodeError as e:
            logfire.error("Failed to parse patient JSON from model response", error=str(e))
            return {"error": f"Failed to parse extracted patient data: {str(e)}"}
    except Exception as e:
        logfire.error("Error during Gemini API call for patient extraction", error=str(e))
        return {"error": f"Error extracting patient data: {str(e)}"}

def process_prompt(
    prompt_type: str,
    patient_id: int,
    user_input: str
) -> Tuple[str, Dict[str, Any]]:
    """Process a prompt with the LLM and update patient context"""
    # Ensure Gemini is initialized
    if gemini_client is None:
        if not initialize_gemini():
            return "Error: Unable to initialize AI model. Please check API key.", {}
    
    # Get the patient data
    patient = get_patient(patient_id)
    if not patient:
        return f"Error: Patient with ID {patient_id} not found.", {}
    
    # Get the current context
    current_context = patient.get('context', {})
    
    # Get the prompt template
    prompt_template = PROMPT_TEMPLATES.get(prompt_type)
    if not prompt_template:
        return f"Error: Prompt type '{prompt_type}' not recognized.", current_context
    
    # Enhance the context with patient information for more personalized responses
    enhanced_context = {
        **current_context,
        "name": patient["name"],
        "dob": patient["dob"],
        "location": patient["location"],
        "diagnosis": patient["diagnosis"]
    }
    
    # Add care gaps if available
    if patient.get("care_gaps"):
        enhanced_context["care_gaps"] = patient["care_gaps"]
    
    # Try to extract zip code from location if not already in context
    if "zip_code" not in enhanced_context and patient["location"]:
        # Simple regex to extract US zip code pattern
        zip_match = re.search(r'(\d{5}(?:-\d{4})?)', patient["location"])
        if zip_match:
            enhanced_context["zip_code"] = zip_match.group(1)
    
    # Construct the full prompt with enhanced patient context and user input
    context_json = json.dumps(enhanced_context, indent=2)
    full_prompt = f"""
{prompt_template}

PATIENT CONTEXT:
{context_json}

USER INPUT:
{user_input}
"""
    
    # Record the start time for performance monitoring
    start_time = time.time()
    
    try:
        # Log the prompt being sent (be careful not to log sensitive data)
        logfire.info(
            "Sending prompt to Gemini",
            prompt_type=prompt_type,
            patient_id=patient_id,
            model=GEMINI_MODEL_NAME
        )
        
        # Call the Gemini API
        with logfire.span("Calling Gemini API", model=GEMINI_MODEL_NAME):
            response = gemini_client.models.generate_content(model=GEMINI_MODEL_NAME, contents=full_prompt)
            response_text = response.text
        
        # Calculate duration
        duration = time.time() - start_time
        logfire.info(
            "Gemini API call successful",
            duration_seconds=duration,
            prompt_type=prompt_type,
            patient_id=patient_id
        )
        
        # Extract context from the response
        updated_context = extract_context(response_text)
        
        # If context was extracted, update the patient's context
        if updated_context:
            # Merge the updated context with the enhanced context
            merged_context = {**enhanced_context, **updated_context}
            update_patient_context(patient_id, merged_context)
            
            # Record the interaction in the database
            add_interaction(
                patient_id=patient_id,
                prompt_type=prompt_type,
                user_input=user_input,
                response=response_text,
                context_before=current_context,
                context_after=merged_context
            )
            
            return response_text, merged_context
        else:
            # If no context was extracted, still record the interaction and update with enhanced context
            add_interaction(
                patient_id=patient_id,
                prompt_type=prompt_type,
                user_input=user_input,
                response=response_text,
                context_before=current_context,
                context_after=enhanced_context
            )
            
            # Always update with at least the enhanced context
            update_patient_context(patient_id, enhanced_context)
            
            return response_text, enhanced_context
            
    except Exception as e:
        # Log the error
        error_message = str(e)
        logfire.error(
            "Error during Gemini API call",
            error=error_message,
            prompt_type=prompt_type,
            patient_id=patient_id
        )
        return f"Error processing prompt: {error_message}", current_context
