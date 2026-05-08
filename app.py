from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.utils import secure_filename
import os
import re
from datetime import datetime
import sqlite3
import hashlib

# Get the absolute path to your project folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Create Flask app with explicit paths
app = Flask(__name__, 
            template_folder=os.path.join(BASE_DIR, 'templates'),
            static_folder=os.path.join(BASE_DIR, 'static'))
app.secret_key = 'your-secret-key-here-change-in-production'

# Upload configuration
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'epub', 'txt', 'doc', 'docx', 'mobi'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create folders if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'templates'), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'static'), exist_ok=True)

# Database functions
def get_db_connection():
    conn = sqlite3.connect(os.path.join(BASE_DIR, 'books.db'))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            description TEXT,
            file_path TEXT,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hash_value):
    return hash_password(password) == hash_value

def create_user(username, email, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
            (username, email, hash_password(password))
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_user_by_username(username):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return user

def add_book(user_id, title, author, description, file_path=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO books (user_id, title, author, description, file_path) VALUES (?, ?, ?, ?, ?)',
        (user_id, title, author, description, file_path)
    )
    conn.commit()
    book_id = cursor.lastrowid
    conn.close()
    return book_id

def get_user_books(user_id):
    conn = get_db_connection()
    books = conn.execute(
        'SELECT * FROM books WHERE user_id = ? ORDER BY created_at DESC',
        (user_id,)
    ).fetchall()
    conn.close()
    return books

def update_book(book_id, user_id, title, author, description):
    conn = get_db_connection()
    conn.execute(
        'UPDATE books SET title = ?, author = ?, description = ? WHERE id = ? AND user_id = ?',
        (title, author, description, book_id, user_id)
    )
    conn.commit()
    conn.close()

def delete_book(book_id, user_id):
    conn = get_db_connection()
    book = conn.execute('SELECT file_path FROM books WHERE id = ? AND user_id = ?', 
                        (book_id, user_id)).fetchone()
    if book and book['file_path']:
        try:
            os.remove(book['file_path'])
        except:
            pass
    conn.execute('DELETE FROM books WHERE id = ? AND user_id = ?', (book_id, user_id))
    conn.commit()
    conn.close()

def get_book(book_id, user_id):
    conn = get_db_connection()
    book = conn.execute('SELECT * FROM books WHERE id = ? AND user_id = ?', 
                        (book_id, user_id)).fetchone()
    conn.close()
    return book

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def sanitize_input(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]*>', '', text)
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return text.strip()

def validate_username(username):
    if not username or len(username) < 3 or len(username) > 20:
        return False
    return bool(re.match(r'^[a-zA-Z0-9_]+$', username))

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_password(password):
    return password and len(password) >= 6

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('admin'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = sanitize_input(request.form.get('username', ''))
        email = sanitize_input(request.form.get('email', ''))
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        errors = []
        if not validate_username(username):
            errors.append("Username must be 3-20 characters and contain only letters, numbers, and underscores")
        if not validate_email(email):
            errors.append("Please enter a valid email address")
        if not validate_password(password):
            errors.append("Password must be at least 6 characters")
        if password != confirm_password:
            errors.append("Passwords do not match")
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('register.html')
        
        if create_user(username, email, password):
            flash('Account created successfully! Please login.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Username or email already exists. Please try different ones.', 'error')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = sanitize_input(request.form.get('username', ''))
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Please enter both username and password', 'error')
            return render_template('login.html')
        
        user = get_user_by_username(username)
        if user and verify_password(password, user['password_hash']):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash(f'Welcome back, {username}!', 'success')
            return redirect(url_for('admin'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/admin')
def admin():
    if 'user_id' not in session:
        flash('Please login to access the admin page.', 'error')
        return redirect(url_for('login'))
    
    books = get_user_books(session['user_id'])
    return render_template('admin.html', books=books, username=session['username'])

@app.route('/add_book', methods=['POST'])
def add_book_route():
    if 'user_id' not in session:
        return {'error': 'Not authenticated'}, 401
    
    title = sanitize_input(request.form.get('title', ''))
    author = sanitize_input(request.form.get('author', ''))
    description = sanitize_input(request.form.get('description', ''))
    
    if not title or len(title) < 1 or len(title) > 200:
        flash('Title is required and must be less than 200 characters', 'error')
        return redirect(url_for('admin'))
    
    if not author or len(author) > 100:
        flash('Author is required', 'error')
        return redirect(url_for('admin'))
    
    file_path = None
    if 'book_file' in request.files:
        file = request.files['book_file']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(f"{session['user_id']}_{datetime.now().timestamp()}_{file.filename}")
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
        elif file and file.filename:
            flash('File type not allowed. Allowed types: PDF, EPUB, TXT, DOC, DOCX, MOBI', 'error')
            return redirect(url_for('admin'))
    
    add_book(session['user_id'], title, author, description, file_path)
    flash(f'Book "{title}" added successfully!', 'success')
    return redirect(url_for('admin'))

@app.route('/update_book/<int:book_id>', methods=['POST'])
def update_book_route(book_id):
    if 'user_id' not in session:
        return {'error': 'Not authenticated'}, 401
    
    title = sanitize_input(request.form.get('title', ''))
    author = sanitize_input(request.form.get('author', ''))
    description = sanitize_input(request.form.get('description', ''))
    
    if not title or not author:
        flash('Title and author are required', 'error')
        return redirect(url_for('admin'))
    
    update_book(book_id, session['user_id'], title, author, description)
    flash('Book updated successfully!', 'success')
    return redirect(url_for('admin'))

@app.route('/delete_book/<int:book_id>', methods=['POST'])
def delete_book_route(book_id):
    if 'user_id' not in session:
        return {'error': 'Not authenticated'}, 401
    
    delete_book(book_id, session['user_id'])
    flash('Book deleted successfully!', 'success')
    return redirect(url_for('admin'))

@app.route('/download_book/<int:book_id>')
def download_book(book_id):
    if 'user_id' not in session:
        flash('Please login to download books', 'error')
        return redirect(url_for('login'))
    
    book = get_book(book_id, session['user_id'])
    if not book:
        flash('Book not found', 'error')
        return redirect(url_for('admin'))
    
    if book['file_path'] and os.path.exists(book['file_path']):
        return send_file(
            book['file_path'],
            as_attachment=True,
            download_name=f"{book['title']}_{book['author']}.{book['file_path'].split('.')[-1]}"
        )
    else:
        flash('No file available for download for this book', 'error')
        return redirect(url_for('admin'))

if __name__ == '__main__':
    init_db()
    print(f"Base directory: {BASE_DIR}")
    print(f"Templates path: {os.path.join(BASE_DIR, 'templates')}")
    print(f"Templates exist: {os.path.exists(os.path.join(BASE_DIR, 'templates'))}")
    app.run(debug=True)