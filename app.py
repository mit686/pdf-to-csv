import os
from flask import Flask, render_template, request, send_file, jsonify
import pdfplumber
import pandas as pd
from werkzeug.utils import secure_filename
import json
import re
from flask_talisman import Talisman
import time

app = Flask(__name__)

# Basic configuration
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize Talisman for security headers
Talisman(app, 
         force_https=True,  # Force HTTPS
         content_security_policy={
             'default-src': "'self'",
             'script-src': "'self' 'unsafe-inline'",
             'style-src': "'self' 'unsafe-inline'"
         })

def allowed_file(filename):
    """Check if the file extension is allowed."""
    return filename.lower().endswith('.pdf')

def clean_old_files():
    """Clean files older than 30 minutes."""
    current_time = time.time()
    for file in os.listdir(app.config['UPLOAD_FOLDER']):
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file)
        try:
            if os.path.isfile(file_path):
                # Remove if older than 30 minutes
                if current_time - os.path.getmtime(file_path) > 1800:
                    os.remove(file_path)
        except Exception as e:
            print(f"Error cleaning up file {file_path}: {e}")

def process_pdf(pdf_path):
    print(f"Processing PDF file: {pdf_path}")
    all_transactions = []  # Store all transactions from all pages
    beginning_balance = None
    
    with pdfplumber.open(pdf_path) as pdf:
        print(f"PDF has {len(pdf.pages)} pages")
        for page_num, page in enumerate(pdf.pages, 1):
            print(f"\nProcessing page {page_num}")
            
            # Extract all text from the page for debugging
            page_text = page.extract_text()
            print("\nPage text preview:")
            print(page_text[:500])
            
            # Look for beginning balance in the first page
            if page_num == 1:
                for line in page_text.split('\n'):
                    if 'Beginning Balance' in line:
                        # Extract amount using regex
                        match = re.search(r'Beginning Balance.*?\$([\d,]+\.\d{2})', line)
                        if match:
                            beginning_balance = match.group(0)
                            print(f"Found beginning balance: {beginning_balance}")
            
            # First try to find the transaction section using text markers
            lines = page_text.split('\n')
            transaction_start = -1
            transaction_data = []
            header_found = False
            
            for i, line in enumerate(lines):
                line_lower = line.lower().strip()
                
                # Look for transaction section markers
                if 'transactions' in line_lower or (
                    'date' in line_lower and 
                    'description' in line_lower and 
                    'amount' in line_lower
                ):
                    transaction_start = i
                    header_found = True
                    continue
                
                if header_found and i > transaction_start:
                    # Skip empty lines and section markers
                    if not line.strip() or any(marker in line_lower for marker in ['page', 'banking services', 'envelopes']):
                        continue
                        
                    # Check if this line looks like a transaction
                    # Transaction lines typically start with a date (MM/DD/YYYY)
                    if line.strip() and (
                        len(line.split()) >= 3 and  # At least date, description, amount
                        ('/' in line or '$' in line)  # Contains date separator or dollar sign
                    ):
                        transaction_data.append(line.strip())
            
            if transaction_data:
                print("\nFound transaction data through text analysis:")
                for line in transaction_data:
                    print(line)
                
                # Process transaction data into a structured format
                current_transaction = None
                
                for line in transaction_data:
                    # Check if line starts with a date pattern (MM/DD/YYYY)
                    if len(line) >= 10 and line[2] == '/' and line[5] == '/':
                        # If we have a previous transaction, add it
                        if current_transaction:
                            all_transactions.append(current_transaction)
                        
                        # Start new transaction
                        parts = line.split()
                        date = parts[0]
                        
                        # Find amount (look for $ sign and +/- signs)
                        amount = ''
                        amount_index = -1
                        for i, part in enumerate(reversed(parts)):
                            if '$' in part:
                                amount_index = len(parts) - i - 1
                                # Look for sign in current or previous part
                                if i < len(parts) - 1 and parts[-(i+2)] in ['+', '-']:
                                    amount = parts[-(i+2)] + part
                                    amount_index -= 1  # Move back one more to exclude the sign
                                elif part.startswith('+') or part.startswith('-'):
                                    amount = part
                                else:
                                    amount = part
                                break
                        
                        # Description is everything between date and amount, excluding the sign
                        desc_start = line.find(parts[1])  # Start after date
                        desc_end = line.find(parts[amount_index])  # End before amount and sign
                        description = line[desc_start:desc_end].strip()
                        
                        current_transaction = [date, description, amount]
                    elif current_transaction:
                        # This line is a continuation of the previous description
                        # Only add if it doesn't contain amount-related symbols
                        continuation = line.strip()
                        if not any(symbol in continuation for symbol in ['$', '+', '-']):
                            current_transaction[1] += ' ' + continuation
                
                # Don't forget to add the last transaction
                if current_transaction:
                    all_transactions.append(current_transaction)
    
    if all_transactions:
        # Calculate total amount
        total_amount = 0
        for transaction in all_transactions:
            amount_str = transaction[2]
            # Remove $ and convert to float
            amount = float(amount_str.replace('$', '').replace(',', ''))
            total_amount += amount

        # Format total amount with proper sign and dollar sign
        if total_amount >= 0:
            total_amount_str = f"${total_amount:,.2f}"
        else:
            total_amount_str = f"-${abs(total_amount):,.2f}"

        # Create a single table with all transactions
        table_info = {
            'page': 'all',  # Indicate this contains transactions from all pages
            'table_number': 1,
            'rows': [['DATE', 'DESCRIPTION', 'AMOUNT']] + all_transactions,  # Don't include total in rows
            'row_count': len(all_transactions) + 1,
            'col_count': 3,
            'preview': [['DATE', 'DESCRIPTION', 'AMOUNT']] + all_transactions[:4] + [['', 'Total amount', total_amount_str]],  # Include total only in preview
            'total_amount': total_amount_str,  # Store total amount separately
            'beginning_balance': beginning_balance  # Add beginning balance to table info
        }
        print(f"\nProcessed {len(all_transactions)} transactions total")
        print("Preview:")
        for row in table_info['preview']:
            print(row)
        return [table_info]
    
    return []

def convert_table_to_csv(table_data, column_mapping=None):
    if not table_data or not table_data['rows']:
        return None
    
    # Convert to DataFrame using only the transaction rows (excluding total)
    df = pd.DataFrame(table_data['rows'][1:], columns=table_data['rows'][0])
    
    if column_mapping:
        # Use specified column mapping
        try:
            result_df = df[[column_mapping['date'], column_mapping['description'], column_mapping['amount']]]
            result_df.columns = ['Date', 'Description', 'Amount']
        except KeyError:
            # If mapping fails, use first three columns
            if len(df.columns) >= 3:
                result_df = df.iloc[:, :3]
                result_df.columns = ['Date', 'Description', 'Amount']
            else:
                return None
    else:
        # Use first three columns
        if len(df.columns) >= 3:
            result_df = df.iloc[:, :3]
            result_df.columns = ['Date', 'Description', 'Amount']
        else:
            return None
    
    # Remove empty rows
    result_df = result_df.replace('', pd.NA).dropna(how='all')
    
    return result_df if not result_df.empty else None

@app.route('/')
def index():
    clean_old_files()
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            temp_file = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(temp_file)
            
            # Process the PDF file immediately
            tables = process_pdf(temp_file)
            if not tables:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                return jsonify({'error': 'No tables found in the PDF'}), 400
            
            return jsonify({
                'message': 'File uploaded successfully',
                'tables': tables,
                'filename': filename  # Send filename back to client
            })
            
        except Exception as e:
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return jsonify({'error': str(e)}), 500
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/convert', methods=['POST'])
def convert_to_csv():
    try:
        data = request.json
        filename = data.get('filename')
        table_index = data.get('tableIndex')
        column_mapping = data.get('mapping')
        
        if not filename:
            return jsonify({'error': 'No filename provided'}), 400
        
        temp_file = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
        
        if not os.path.exists(temp_file):
            return jsonify({'error': 'File not found. Please upload the file again.'}), 400
        
        # Process the PDF file again
        tables = process_pdf(temp_file)
        if not tables:
            return jsonify({'error': 'Could not process PDF file'}), 400
        
        if table_index is None:
            return jsonify({'error': 'No table selected'}), 400
        
        if table_index >= len(tables):
            return jsonify({'error': 'Invalid table index'}), 400
        
        # Convert the selected table
        selected_table = tables[table_index]
        df = convert_table_to_csv(selected_table, column_mapping)
        
        if df is None:
            return jsonify({'error': 'Could not convert table to CSV'}), 400
        
        # Save as CSV
        csv_filename = os.path.splitext(filename)[0] + '.csv'
        csv_filepath = os.path.join(app.config['UPLOAD_FOLDER'], csv_filename)
        df.to_csv(csv_filepath, index=False)
        
        # Clean up the PDF file
        if os.path.exists(temp_file):
            os.remove(temp_file)
        
        return send_file(
            csv_filepath,
            mimetype='text/csv',
            as_attachment=True,
            download_name=csv_filename
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    host = '0.0.0.0'
    debug = False
    
    # SSL context
    ssl_context = ('ssl/cert.pem', 'ssl/key.pem')
    
    print(f"Starting Flask application on {host}:{port} (HTTPS)")
    app.run(host=host, port=port, debug=debug, ssl_context=ssl_context) 