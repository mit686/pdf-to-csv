# PDF Bank Statement to CSV Converter

A Flask-based web application that converts bank statements from PDF format to CSV, with a modern drag-and-drop interface and transaction preview functionality.

## Features

- Modern drag-and-drop interface for PDF uploads
- Intelligent table extraction from bank statements
- Transaction preview before conversion
- Automatic detection of date, description, and amount columns
- Support for multi-page PDFs
- Proper handling of transaction amounts (positive/negative)
- Beginning balance detection
- Total amount calculation
- Clean CSV export

## Requirements

- Python 3.x
- Flask
- pdfplumber
- pandas
- Werkzeug

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/pdf-to-csv.git
cd pdf-to-csv
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the Flask server:
```bash
python app.py
```

2. Open your web browser and navigate to:
```
http://localhost:5001
```

3. Drag and drop your PDF bank statement or click to select a file
4. Preview the extracted transactions
5. Click "Convert to CSV" to download the converted file

## Notes

- The application runs on port 5001 to avoid conflicts with AirPlay on macOS
- Uploaded files are temporarily stored in the `uploads` directory
- Files are automatically cleaned up after processing
- Maximum file size is limited to 16MB

## Security

- File uploads are secured using Werkzeug's `secure_filename`
- Temporary files are deleted after processing
- Session management is implemented for file handling

## License

MIT License 