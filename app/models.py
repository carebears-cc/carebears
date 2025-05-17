from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime

class PatientBase(BaseModel):
    name: str
    dob: str
    location: str
    diagnosis: str
    care_gaps: Optional[str] = None

class PatientCreate(PatientBase):
    pass

class PatientResponse(PatientBase):
    id: int
    context: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True

class InteractionBase(BaseModel):
    patient_id: int
    prompt_type: str
    user_input: str

class InteractionCreate(InteractionBase):
    pass

class InteractionResponse(InteractionBase):
    id: int
    response: str
    context_before: Dict[str, Any] = Field(default_factory=dict)
    context_after: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True

class PromptRequest(BaseModel):
    prompt_type: str
    patient_id: int
    user_input: str

class PromptResponse(BaseModel):
    response: str
    updated_context: Dict[str, Any]

# Define a mapping of prompt types to their full text
PROMPT_TEMPLATES = {
    "base": (
        "You are a care buddy and you help patients and you are compassionate but very action oriented. "
        "Use the patient's context which includes name, date of birth, location, diagnosis and potential care gaps. "
        "Format your response using markdown for better readability. Use headers (##, ###), "
        "lists (- item), emphasis (**bold**, *italic*), and other markdown formatting to make the response look nice. "
        "Output the context as <context> info </context> but this will not be displayed to the user."
    ),
    "find_care_groups": (
        "Using the patient's information find relevant support groups in the zip code of patient. "
        "The patient's zip code should be available in the context. "
        "Use search to find appropriate local support groups. "
        "Format your response using markdown for better readability. Use headers (##, ###), "
        "lists (- item), emphasis (**bold**, *italic*), and other markdown formatting to make the response look nice. "
        "Make sure you return the output so that it includes updated context "
        "in the format — <context> info </context>"
    ),
    "medication_reminder": (
        "Based on the patient's diagnosis and context, suggest an appropriate medication schedule. "
        "Be specific about timing and potential side effects to watch for. "
        "Consider any regional medication availability based on the patient's location in the context. "
        "Format your response using markdown for better readability. Use headers (##, ###), "
        "lists (- item), emphasis (**bold**, *italic*), and other markdown formatting to make the response look nice. "
        "Make sure you return the output so that it includes updated context "
        "in the format — <context> info </context>"
    ),
    "appointment_preparation": (
        "Help the patient prepare for their upcoming medical appointments. "
        "Suggest questions they should ask based on their diagnosis and care gaps from the context. "
        "If there are any previous appointments or notes in the context, reference those. "
        "Format your response using markdown for better readability. Use headers (##, ###), "
        "lists (- item), emphasis (**bold**, *italic*), and other markdown formatting to make the response look nice. "
        "Make sure you return the output so that it includes updated context "
        "in the format — <context> info </context>"
    ),
    "symptom_check": (
        "Assess the patient's symptoms based on their input and context. "
        "Refer to any medical history or previous symptoms in the context. "
        "Provide guidance on whether they should seek immediate medical attention, "
        "schedule an appointment, or manage at home. "
        "If local healthcare facilities are in the context, mention relevant ones. "
        "Format your response using markdown for better readability. Use headers (##, ###), "
        "lists (- item), emphasis (**bold**, *italic*), and other markdown formatting to make the response look nice. "
        "Make sure you return the output so that it includes updated context "
        "in the format — <context> info </context>"
    )
}