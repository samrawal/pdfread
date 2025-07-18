# ReadPDF
*Note: this app is essentially entirely vibe-coded in a short amount of time. Thus, no assurances about anything are made :)*

Check it out at https://readpdf.fly.dev/

A web application for reading PDFs, taking notes, and chatting with AI about the document content.

## Features

- **PDF Viewer (Pane A - 40%)**: Drag-and-drop PDF upload, page navigation, zoom controls
- **Notes (Pane B - 40%)**: Take notes tied to specific PDFs, auto-saved to localStorage
- **AI Chat (Pane C - 20%)**: Chat with Gemini AI about your PDF content

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Gemini AI

1. Get your API key from [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Set the environment variable:

**Windows:**
```cmd
set GEMINI_API_KEY=your_api_key_here
```

**macOS/Linux:**
```bash
export GEMINI_API_KEY=your_api_key_here
```

### 3. Run the Application

```bash
python app.py
```

The application will be available at `http://localhost:5000`

## Usage

1. **Upload PDF**: Drag and drop a PDF file into the left pane or click to browse
2. **Take Notes**: Use the middle pane to take notes about your PDF
3. **Chat with AI**: Ask questions about your PDF in the right pane chat interface

## Features Details

- **PDF Highlighting**: Coming soon - will be integrated with PDF.js annotation features
- **Notes Persistence**: Notes are automatically saved to localStorage and restored when you reload the same PDF
- **Responsive Chat**: AI responses are powered by Gemini 2.5 Flash for fast, accurate analysis

## Browser Requirements

- Modern browser with JavaScript enabled
- Support for HTML5 Canvas (for PDF rendering)
- LocalStorage support (for notes persistence)

## Technical Stack

- **Backend**: Flask (Python)
- **Frontend**: HTML5, CSS3, JavaScript
- **PDF Rendering**: PDF.js
- **AI Integration**: Google Gemini API
- **Storage**: LocalStorage for client-side persistence 