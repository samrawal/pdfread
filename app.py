import os
import base64
from flask import Flask, render_template, request, jsonify, session, send_from_directory
from werkzeug.utils import secure_filename
import google.generativeai as genai
from datetime import datetime
import uuid
import PyPDF2
import io
import requests
import re
import urllib.parse

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('templates', exist_ok=True)

# Configure Gemini AI
def configure_gemini():
    """Configure Gemini AI with API key from environment variable"""
    api_key = os.getenv('GEMINI_API_KEY')
    if api_key:
        genai.configure(api_key=api_key)
        return True
    return False

def extract_text_from_pdf(pdf_path):
    """Extract text content from PDF file"""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return None

def get_chat_history():
    """Get chat history from session"""
    if 'chat_history' not in session:
        session['chat_history'] = []
    return session['chat_history']

def add_to_chat_history(user_message, ai_response):
    """Add a message pair to chat history"""
    chat_history = get_chat_history()
    chat_history.append({
        'user': user_message,
        'ai': ai_response,
        'timestamp': datetime.now().isoformat()
    })
    session['chat_history'] = chat_history
    session.modified = True

def clear_chat_history():
    """Clear chat history while preserving other session data"""
    session['chat_history'] = []
    session.modified = True

def build_conversation_context(pdf_text, current_message, chat_history):
    """Build conversation context including PDF content and chat history"""
    context_parts = []
    
    # Always include PDF content first
    if pdf_text:
        pdf_excerpt = pdf_text[:8000] if len(pdf_text) > 8000 else pdf_text
        context_parts.append(f"""PDF Document Content:
{pdf_excerpt}
""")
    
    # Add conversation history if exists
    if chat_history:
        context_parts.append("Previous Conversation:")
        for i, exchange in enumerate(chat_history[-5:], 1):  # Include last 5 exchanges to avoid token limits
            context_parts.append(f"User: {exchange['user']}")
            context_parts.append(f"Assistant: {exchange['ai']}")
        context_parts.append("")
    
    # Add current question
    context_parts.append(f"Current Question: {current_message}")
    
    prompt = f"""You are an AI assistant helping a user analyze a PDF document. You maintain conversation context and can refer to previous exchanges.

{chr(10).join(context_parts)}

Please provide a helpful response based on the PDF content and conversation history. Format your response using markdown for better readability (use **bold**, *italics*, bullet points, numbered lists, code blocks, etc. as appropriate)."""
    
    return prompt

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_arxiv_url(url):
    """Parse arXiv URL and return paper ID"""
    # Remove any trailing whitespace
    url = url.strip()
    
    # Handle different arXiv URL formats
    patterns = [
        r'arxiv\.org/abs/([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?)',
        r'arxiv\.org/pdf/([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?)(?:\.pdf)?',
        r'([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?)'  # Just the paper ID
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

def download_arxiv_pdf(paper_id):
    """Download PDF from arXiv given paper ID"""
    try:
        # Construct PDF URL
        pdf_url = f"https://arxiv.org/pdf/{paper_id}.pdf"
        
        # Download PDF
        response = requests.get(pdf_url, timeout=30)
        response.raise_for_status()
        
        # Verify it's a PDF
        if not response.content.startswith(b'%PDF'):
            raise ValueError("Downloaded file is not a valid PDF")
        
        return response.content
    except requests.RequestException as e:
        raise Exception(f"Failed to download PDF: {str(e)}")
    except Exception as e:
        raise Exception(f"Error processing arXiv PDF: {str(e)}")

@app.route('/')
def index():
    """Serve the main application page"""
    return render_template('index.html')

@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    """Handle PDF file upload"""
    try:
        if 'pdf' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['pdf']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Add timestamp to prevent conflicts
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
            filename = timestamp + filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Clear chat history when new PDF is uploaded
            clear_chat_history()
            
            return jsonify({
                'success': True, 
                'filename': filename,
                'filepath': filepath
            })
        else:
            return jsonify({'error': 'Invalid file type'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat requests with Gemini AI - now with conversation history"""
    try:
        data = request.json
        message = data.get('message', '')
        pdf_filename = data.get('pdf_filename', '')
        
        if not message:
            return jsonify({'error': 'No message provided'}), 400
        
        # Check if Gemini is configured
        if not configure_gemini():
            return jsonify({'error': 'Gemini API key not configured. Set GEMINI_API_KEY environment variable.'}), 500
        
        try:
            # Initialize the model
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            # Get chat history
            chat_history = get_chat_history()
            
            # If there's a PDF, extract text and include in the context
            if pdf_filename:
                pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_filename)
                if os.path.exists(pdf_path):
                    # Extract text from PDF
                    pdf_text = extract_text_from_pdf(pdf_path)
                    
                    if pdf_text:
                        # Build conversation context with PDF and history
                        prompt = build_conversation_context(pdf_text, message, chat_history)
                        response = model.generate_content(prompt)
                        
                        # Add to chat history
                        add_to_chat_history(message, response.text)
                    else:
                        response_text = f"I couldn't extract text from the PDF file. The file might be image-based or corrupted. Your question was: **{message}**\n\nPlease try uploading a different PDF file or ensure the PDF contains selectable text."
                        response = model.generate_content(response_text)
                        add_to_chat_history(message, response_text)
                else:
                    response_text = f"I don't have access to the PDF file. Please re-upload your PDF and try again. Your question was: **{message}**"
                    response = model.generate_content(response_text)
                    add_to_chat_history(message, response_text)
            else:
                response_text = f"Please upload a PDF first so I can help you analyze it. Your question was: **{message}**\n\n📄 Upload a PDF using the drag-and-drop area in the left pane, then I'll be able to answer questions about its content!"
                response = model.generate_content(response_text)
                add_to_chat_history(message, response_text)
            
            return jsonify({
                'success': True,
                'response': response.text
            })
            
        except Exception as e:
            return jsonify({'error': f'Gemini API error: {str(e)}'}), 500
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/clear_chat', methods=['POST'])
def clear_chat():
    """Clear chat history while preserving PDF context"""
    try:
        clear_chat_history()
        return jsonify({
            'success': True,
            'message': 'Chat history cleared. PDF context is preserved for new conversation.'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_chat_history', methods=['GET'])
def get_chat_history_endpoint():
    """Get current chat history"""
    try:
        chat_history = get_chat_history()
        return jsonify({
            'success': True,
            'chat_history': chat_history
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/save_notes', methods=['POST'])
def save_notes():
    """Save notes for a specific PDF (backup endpoint, mainly using localStorage)"""
    try:
        data = request.json
        pdf_id = data.get('pdf_id', '')
        notes = data.get('notes', '')
        
        # This could be expanded to save to a database
        # For now, just return success as we're using localStorage on frontend
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/save_highlights', methods=['POST'])
def save_highlights():
    """Save highlights for a specific PDF (backup endpoint, mainly using localStorage)"""
    try:
        data = request.json
        pdf_id = data.get('pdf_id', '')
        highlights = data.get('highlights', [])
        
        # This could be expanded to save to a database
        # For now, just return success as we're using localStorage on frontend
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/upload_arxiv', methods=['POST'])
def upload_arxiv():
    """Handle arXiv URL upload"""
    try:
        data = request.json
        arxiv_url = data.get('url', '').strip()
        
        if not arxiv_url:
            return jsonify({'error': 'No arXiv URL provided'}), 400
        
        # Parse arXiv URL
        paper_id = parse_arxiv_url(arxiv_url)
        if not paper_id:
            return jsonify({'error': 'Invalid arXiv URL format'}), 400
        
        # Download PDF
        pdf_content = download_arxiv_pdf(paper_id)
        
        # Create filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        filename = f"{timestamp}arxiv_{paper_id}.pdf"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Save PDF
        with open(filepath, 'wb') as f:
            f.write(pdf_content)
        
        # Clear chat history when new PDF is uploaded
        clear_chat_history()
        
        return jsonify({
            'success': True,
            'filename': filename,
            'filepath': filepath,
            'paper_id': paper_id
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True) 