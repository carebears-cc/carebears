import os
import unittest
from unittest.mock import patch, MagicMock
import json
from fastapi.testclient import TestClient

# Initialize environment variables for testing
os.environ["GOOGLE_API_KEY"] = "test_api_key"
os.environ["LOGFIRE_TOKEN"] = "test_logfire_token"

# Import modules after setting environment variables
from .main import app
from .database import init_db, get_db_connection
from .models import PatientCreate, PromptRequest
from .services import process_prompt, extract_context

# Create a test client
client = TestClient(app)

class TestCareBears(unittest.TestCase):
    """Test suite for CareBears application"""
    
    def setUp(self):
        """Run before each test"""
        # Initialize test database in memory
        self.conn = get_db_connection()
        init_db()
        
        # Create a test patient
        self.test_patient = {
            "name": "Test Patient",
            "dob": "01/01/1980",
            "location": "12345",
            "diagnosis": "Diabetes",
            "care_gaps": "Missing regular checkups"
        }
        
    def tearDown(self):
        """Run after each test"""
        # Clean up database
        self.conn.close()
    
    def test_create_patient(self):
        """Test patient creation endpoint"""
        response = client.post("/api/patients", json=self.test_patient)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], self.test_patient["name"])
        self.assertEqual(data["diagnosis"], self.test_patient["diagnosis"])
        self.assertIn("id", data)
    
    @patch("app.services.gemini_client")
    def test_process_prompt(self, mock_gemini):
        """Test prompt processing with mocked Gemini API"""
        # Create a test patient first
        patient_response = client.post("/api/patients", json=self.test_patient)
        patient_id = patient_response.json()["id"]
        
        # Mock Gemini API response
        mock_response = MagicMock()
        mock_response.text = "This is a test response. <context>{'test_key': 'test_value'}</context>"
        mock_gemini.models.generate_content.return_value = mock_response
        
        # Test prompt processing
        prompt_request = {
            "prompt_type": "base",
            "patient_id": patient_id,
            "user_input": "This is a test prompt"
        }
        
        response = client.post("/api/prompts", json=prompt_request)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("This is a test response", data["response"])
        self.assertIn("test_key", data["updated_context"])
    
    def test_extract_context(self):
        """Test context extraction from response text"""
        # Test with JSON-like context
        response_text = "Some response <context>{'name': 'John', 'age': 30}</context>"
        context = extract_context(response_text)
        self.assertEqual(context["raw_context"], "{'name': 'John', 'age': 30}")
        
        # Test with no context
        response_text = "Some response without context"
        context = extract_context(response_text)
        self.assertIsNone(context)

    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

if __name__ == "__main__":
    unittest.main()