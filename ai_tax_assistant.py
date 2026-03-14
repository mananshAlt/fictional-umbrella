import os
import sqlite3
from groq import Groq
from datetime import datetime
import json
import PyPDF2
from dotenv import dotenv_values
from PIL import Image
import pytesseract
from pathlib import Path


class AITaxAssistant:
    """AI-powered tax assistant that runs locally on your machine"""
    def __init__(self, api_key=None):
        """Initialize the tax assistant"""
        config = dotenv_values('.env')
        self.api_key = config.get("GROQ_API") or os.environ.get("GROQ_API")
        if not self.api_key:
            raise ValueError("GROQ_API must be set as environment variable or passed to constructor")
        
        self.client = Groq(api_key=self.api_key)
        self.db_path = 'tax_assistant.db'
        self.upload_folder = 'tax_documents'
        
        
        Path(self.upload_folder).mkdir(exist_ok=True)
        
        # Initialize database
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS documents
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id INTEGER NOT NULL,
                      filename TEXT NOT NULL,
                      doc_type TEXT,
                      file_path TEXT NOT NULL,
                      content_text TEXT,
                      uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      FOREIGN KEY (user_id) REFERENCES users(id))''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS tax_analyses
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id INTEGER NOT NULL,
                      analysis_data TEXT NOT NULL,
                      estimated_tax REAL,
                      potential_savings REAL,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      FOREIGN KEY (user_id) REFERENCES users(id))''')
        
        conn.commit()
        conn.close()
    
    def create_user(self, name="Default User"):
        """Create a new user"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('INSERT INTO users (name) VALUES (?)', (name,))
        conn.commit()
        user_id = c.lastrowid
        conn.close()
        print(f"✓ User created with ID: {user_id}")
        return user_id
    
    def extract_text_from_pdf(self, file_path):
        """Extract text from PDF file"""
        text = ""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"
        except Exception as e:
            return f"Error extracting PDF: {str(e)}"
        return text.strip()
    
    def extract_text_from_image(self, file_path):
        """Extract text from image using OCR"""
        try:
            img = Image.open(file_path)
            text = pytesseract.image_to_string(img)
            return text.strip()
        except Exception as e:
            return f"Error extracting image: {str(e)}"
    
    def upload_document(self, user_id, file_path, doc_type="other"):
        """Upload and process a tax document"""
        if not os.path.exists(file_path):
            print(f"✗ File not found: {file_path}")
            return None
        filename = os.path.basename(file_path)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        new_filename = f"{user_id}_{timestamp}_{filename}"
        new_path = os.path.join(self.upload_folder, new_filename)
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        
        if ext == 'pdf':
            content_text = self.extract_text_from_pdf(file_path)
        elif ext in ['jpg', 'jpeg', 'png']:
            content_text = self.extract_text_from_image(file_path)
        elif ext == 'txt':
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content_text = f.read()
        else:
            content_text = ""
        
        # Copy file
        import shutil
        shutil.copy2(file_path, new_path)
        
        # Save to database
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''INSERT INTO documents 
                     (user_id, filename, doc_type, file_path, content_text) 
                     VALUES (?, ?, ?, ?, ?)''',
                  (user_id, filename, doc_type, new_path, content_text))
        conn.commit()
        doc_id = c.lastrowid
        conn.close()
        
        print(f"✓ Document uploaded: {filename} (ID: {doc_id})")
        print(f"  Type: {doc_type}")
        print(f"  Text extracted: {len(content_text)} characters")
        return doc_id
    
    def get_user_documents(self, user_id):
        """Get all documents for a user"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''SELECT id, filename, doc_type, content_text, uploaded_at 
                     FROM documents 
                     WHERE user_id = ? 
                     ORDER BY uploaded_at DESC''', (user_id,))
        
        docs = []
        for row in c.fetchall():
            docs.append({
                'id': row[0],
                'filename': row[1],
                'doc_type': row[2],
                'content_text': row[3],
                'uploaded_at': row[4]
            })
        
        conn.close()
        return docs
    
    def analyze_taxes(self, user_id):
        """Analyze all documents and generate tax recommendations"""
        print("\n" + "="*60)
        print("🤖 Starting AI Tax Analysis...")
        print("="*60)
        
        # Get user documents
        documents = self.get_user_documents(user_id)
        
        if not documents:
            print("✗ No documents found for analysis")
            return None
        
        print(f"Analyzing {len(documents)} document(s)...\n")
        
        # Prepare document summary
        doc_summary = "Analyze the following tax-related documents:\n\n"
        
        for idx, doc in enumerate(documents, 1):
            doc_summary += f"--- Document {idx}: {doc['filename']} ({doc['doc_type']}) ---\n"
            doc_summary += f"{doc['content_text'][:3000]}\n\n"
        
        prompt =doc_summary + """

Based on these documents, provide a comprehensive tax analysis with:

1. **Estimated Tax Liability**: Calculate based on income, deductions, and credits found
2. **Potential Tax Savings**: Identify missed deductions, credits, and optimization opportunities
3. **Income Summary**: Summarize all income sources found
4. **Available Deductions**: List all applicable deductions
5. **Tax Credits**: Identify eligible tax credits
6. **Tax-Saving Strategies**: Provide actionable recommendations
7. **Concerns/Red Flags**: Note any issues or missing information
8. **Next Steps**: Recommend actions to optimize tax position

Return JSON with:

"yearly_tax": {
  "2022": {"before": <number>, "after": <number>},
  "2023": {"before": <number>, "after": <number>},
  "2024": {"before": <number>, "after": <number>},
  "2025": {"before": <number>, "after": <number>}
},

"weekly_breakdown": {
  "mon": {"salary": <number>, "investments": <number>, "expenses": <number>},
  "tue": {"salary": <number>, "investments": <number>, "expenses": <number>},
  "wed": {"salary": <number>, "investments": <number>, "expenses": <number>},
  "thu": {"salary": <number>, "investments": <number>, "expenses": <number>},
  "fri": {"salary": <number>, "investments": <number>, "expenses": <number>},
  "sat": {"salary": <number>, "investments": <number>, "expenses": <number>},
  "sun": {"salary": <number>, "investments": <number>, "expenses": <number>}
},

"credit_score": <number>,

"tax_timeline": {
  "current": <number>,
  "future": [<number>, <number>, <number>]
}"""

        try:
            completion = self.client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[{"role": "user", "content": prompt}],
                temperature=1,
                max_completion_tokens=4096,
                top_p=1,
                stream=True,
                stop=None
            )
            
            response_text=""
            for chunk in completion:
                content = chunk.choices[0].delta.content or ""
                response_text += content
            
            # Extract JSON
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                analysis = json.loads(json_str)
            else:
                analysis = {
                    "estimated_tax": 0,
                    "potential_savings": 0,
                    "income_summary": response_text,
                    "deductions": [],
                    "credits": [],
                    "strategies": [],
                    "concerns": ["Unable to parse structured response"],
                    "next_steps": []
                }
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('''INSERT INTO tax_analyses 
                         (user_id, analysis_data, estimated_tax, potential_savings) 
                         VALUES (?, ?, ?, ?)''',
                      (user_id, json.dumps(analysis),
                       analysis.get('estimated_tax', 0),
                       analysis.get('potential_savings', 0)))
            conn.commit()
            analysis_id = c.lastrowid
            conn.close()
            self._display_analysis(analysis)
            
            return json.dumps(analysis)
            
        except Exception as e:
            print(f"✗ Analysis error: {str(e)}")
            return None
    
    def _display_analysis(self, analysis):

        print("\nTAX OPTIMIZATION IMPACT")
        print(analysis["yearly_tax"])

        print("\nWEEKLY BREAKDOWN")
        print(analysis["weekly_breakdown"])

        print("\nCREDIT SCORE")
        print(analysis["credit_score"])

        print("\nTAX LIABILITY TIMELINE")
        print(analysis["tax_timeline"])

                
        print("\n" + "="*60)
    
    def get_all_analyses(self, user_id):
        """Get all tax analyses for a user"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''SELECT id, analysis_data, estimated_tax, potential_savings, created_at 
                     FROM tax_analyses 
                     WHERE user_id = ? 
                     ORDER BY created_at DESC''', (user_id,))
        
        analyses = []
        for row in c.fetchall():
            analyses.append({
                'id': row[0],
                'analysis': json.loads(row[1]),
                'estimated_tax': row[2],
                'potential_savings': row[3],
                'created_at': row[4]
            })
        
        conn.close()
        return analyses
    
    def delete_document(self, doc_id):
        """Delete a document"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('SELECT file_path FROM documents WHERE id = ?', (doc_id,))
        doc = c.fetchone()
        
        if doc:
            # Delete file
            if os.path.exists(doc[0]):
                os.remove(doc[0])
            
            # Delete from database
            c.execute('DELETE FROM documents WHERE id = ?', (doc_id,))
            conn.commit()
            print(f"✓ Document deleted (ID: {doc_id})")
        else:
            print(f"✗ Document not found (ID: {doc_id})")
        
        conn.close()


# Example usage
if __name__ == '__main__':
    print("="*60)
    print("🤖 AI TAX ASSISTANT - LOCAL VERSION")
    print("="*60)
    assistant = AITaxAssistant()
    user_id = assistant.create_user("John Doe")
    
    # Example: Upload documents
    print("\n📤 Upload your tax documents:")
    print("   assistant.upload_document(user_id, 'path/to/w2.pdf', 'W2')")
    print("   assistant.upload_document(user_id, 'path/to/1099.pdf', '1099')")
    print("   assistant.upload_document(user_id, 'path/to/receipt.jpg', 'receipt')")
    
    # Example: Analyze
    print("\n🔍 Analyze documents:")
    print("   assistant.analyze_taxes(user_id)")
    print("\n📋 View documents:")
    print("   docs = assistant.get_user_documents(user_id)")
    
    # Example: Get all analyses
    print("\n📊 View analyses:")
    print("   analyses = assistant.get_all_analyses(user_id)")
    
    print("\n" + "="*60)
    print("💡 Quick Start:")
    print("="*60)
    print("from ai_tax_assistant import AITaxAssistant")
    print()
    print("# Initialize")
    print("assistant = AITaxAssistant()")
    print()
    print("# Create user")
    print("user_id = assistant.create_user('Your Name')")
    print()
    print("# Upload documents")
    print("assistant.upload_document(user_id, 'w2.pdf', 'W2')")
    print("assistant.upload_document(user_id, 'expenses.jpg', 'receipt')")
    print()
    print("# Analyze and get recommendations")
    print("assistant.analyze_taxes(user_id)")
    print("="*60)
    # 1. Create/Get User
    user_id = assistant.create_user("John Doe")

    # 2. Upload a file (W2, 1099, or Receipt)
    # Provide the path to your actual file here
    file_path = "sample.txt" 
    doc_id = assistant.upload_document(user_id, file_path, doc_type="W2")

    print(f"✅ Document uploaded with ID: {doc_id}")

    # 3. Run AI Analysis
    print("\n🔍 Analyzing your documents for savings and recommendations...")
    analysis_results = assistant.analyze_taxes(user_id)

    # 4. Print the Recommendations
    print("\n" + "="*60)
    print("📊 AI TAX ANALYSIS & RECOMMENDATIONS")
    print("="*60)
    print(analysis_results)