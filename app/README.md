# CareBears AI Care Companion

CareBears is an AI companion for patients with chronic conditions and their caregivers, providing crucial support during the challenging transition from hospital to home and throughout the ongoing management of complex health conditions.

## Features

- Post-discharge navigation support
- Care coordination for caregivers
- Chronic condition management
- Medical record summarization
- Resource navigation
- Appointment management

## Technical Stack

- FastAPI
- Pydantic
- SQLite
- Google Generative AI (Gemini)
- Logfire for observability

## Project Structure

```
app/
   main.py           # FastAPI application entry point
   database.py       # SQLite database models and functions
   models.py         # Pydantic models for data validation
   services.py       # Services for interacting with Google AI
   templates/        # HTML templates
      index.html    # Home page
      patient.html  # Patient dashboard
   data/             # SQLite database (created at runtime)
```

## Prompt Architecture

The application uses a context-aware prompting system:

1. Each use case has a precise, actionable prompt template
2. Every LLM call updates the context on the patient
3. This context file is fed to every subsequent query
4. Example prompts:
   - Prompt_Base: General patient information
   - Prompt_find_care_groups: Finding support groups in patient's area
   - Prompt_medication_reminder: Medication schedules and reminders
   - Prompt_appointment_preparation: Preparation for medical appointments
   - Prompt_symptom_check: Symptom assessment and guidance

## Installation & Setup

1. Clone the repository
2. Install dependencies using uv:
   ```
   # Install uv if you don't have it already
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Install dependencies
   uv pip install -r requirements.txt
   # Or use the lockfile for reproducible installs
   uv pip sync
   ```
3. Set up environment variables:
   ```
   export GOOGLE_API_KEY="your-google-api-key"
   export LOGFIRE_TOKEN="your-logfire-token"  # Optional
   ```

## Running the Application

```bash
uvicorn app.main:app --reload
```

Visit `http://localhost:8000` in your browser.

## API Endpoints

- `POST /api/patients`: Create a new patient
- `GET /api/patients/{patient_id}`: Get patient details
- `GET /api/patients/{patient_id}/interactions`: Get patient interactions
- `POST /api/prompts`: Process a patient prompt

## Web UI Routes

- `GET /`: Home page with patient creation form
- `GET /patients/{patient_id}`: Patient dashboard
- `POST /patients/{patient_id}/prompt`: Process a prompt for a patient