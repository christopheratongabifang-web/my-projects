import sqlite3
import hashlib
import os
from datetime import datetime

def get_db_connection():
    conn = sqlite3.connect('books.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Books table
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
    # Get file path before deleting
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