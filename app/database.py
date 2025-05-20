import sqlite3
from contextlib import contextmanager
from pathlib import Path
import json

# Create the database directory if it doesn't exist
DB_DIR = Path("./data")
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "carebears.db"

@contextmanager
def get_db_connection():
    """Context manager for SQLite database connection"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Initialize the database with required tables"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Create patients table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            dob TEXT NOT NULL,
            location TEXT NOT NULL,
            diagnosis TEXT NOT NULL,
            care_gaps TEXT,
            context JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create interactions table to track patient interactions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            prompt_type TEXT NOT NULL,
            user_input TEXT NOT NULL,
            response TEXT NOT NULL,
            context_before JSON,
            context_after JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES patients (id)
        )
        ''')
        
        conn.commit()

def add_patient(name, dob, location, diagnosis, care_gaps=None, context=None):
    """Add a new patient to the database"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO patients (name, dob, location, diagnosis, care_gaps, context)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (name, dob, location, diagnosis, care_gaps, json.dumps(context or {}))
        )
        conn.commit()
        return cursor.lastrowid

def get_patient(patient_id):
    """Get patient information by ID"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM patients WHERE id = ?', (patient_id,))
        patient = cursor.fetchone()
        if patient:
            # Convert SQLite Row to dict
            patient_dict = dict(patient)
            # Parse JSON fields
            if patient_dict['context']:
                patient_dict['context'] = json.loads(patient_dict['context'])
            return patient_dict
        return None

def update_patient_context(patient_id, new_context):
    """Update a patient's context information"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE patients SET context = ? WHERE id = ?',
            (json.dumps(new_context), patient_id)
        )
        conn.commit()
        return cursor.rowcount > 0

def add_interaction(patient_id, prompt_type, user_input, response, context_before, context_after):
    """Record a patient interaction in the database"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO interactions 
            (patient_id, prompt_type, user_input, response, context_before, context_after)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (
                patient_id, 
                prompt_type, 
                user_input, 
                response, 
                json.dumps(context_before or {}),
                json.dumps(context_after or {})
            )
        )
        conn.commit()
        return cursor.lastrowid

def get_patient_interactions(patient_id, limit=10):
    """Get recent interactions for a patient"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT * FROM interactions
            WHERE patient_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            ''',
            (patient_id, limit)
        )
        interactions = cursor.fetchall()
        # Convert SQLite Row objects to dicts and parse JSON
        result = []
        for interaction in interactions:
            interaction_dict = dict(interaction)
            if interaction_dict['context_before']:
                interaction_dict['context_before'] = json.loads(interaction_dict['context_before'])
            if interaction_dict['context_after']:
                interaction_dict['context_after'] = json.loads(interaction_dict['context_after'])
            result.append(interaction_dict)
        return result
