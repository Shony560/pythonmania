from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
# from kafka import KafkaProducer (REMOVED)
# import json (REMOVED)
from psycopg2 import errors # Import psycopg2 errors for specific exception handling
import logging
from logging.handlers import RotatingFileHandler
import sys
import traceback

# Top-level error catching to ensure something is logged even if startup fails
try:
    # Configure logging immediately
    logging.basicConfig(level=logging.DEBUG) # Set to DEBUG for maximum info
    logger = logging.getLogger('attendance_app')
    # Force log to stdout as well so app.log captures it
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    logger.addHandler(console_handler)
    
    handler = RotatingFileHandler('error.log', maxBytes=1000000, backupCount=3)
    handler.setLevel(logging.ERROR)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    logger.info("Python script started, logging initialized.")
except Exception as e:
    print(f"CRITICAL: Failed to initialize logging: {e}")
    sys.exit(1)

app = Flask(__name__)

@app.before_request
def log_request():
    logger.debug(f"Request: {request.method} {request.path}")
app.secret_key = os.environ.get('APP_SECRET_KEY', 'super_secret_attendance_key_123')
DATABASE_URL = os.environ.get('DATABASE_URL')

# Initialize Kafka Producer (REMOVED)
producer = None

def get_db():
    logger.debug("Attempting to connect to database using DATABASE_URL")
    if not DATABASE_URL:
        logger.error("DATABASE_URL environment variable is not set")
        raise ValueError("DATABASE_URL environment variable is not set")
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        logger.info("Database connection established")
        return conn
    except Exception as e:
        logger.exception("Failed to connect to database")
        raise e

def init_db():
    logger.info("Initializing database schema")
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                date TEXT,
                time TEXT,
                status TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()['count'] == 0:
            cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", ('user1', 'pass1'))
            cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", ('user2', 'pass2'))
        conn.commit()
        logger.info("Database initialized successfully")
        conn.close()
    except Exception as e:
        logger.exception("Error initializing database")
        raise e

@app.route('/', methods=['GET', 'POST'])
def login():
    logger.debug("Login endpoint accessed")
    if 'user_id' in session:
        logger.debug("User already logged in, redirecting to dashboard")
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        logger.info(f"Login attempt for username: {username}")
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            
            # Kafka Event Sending REMOVED
                    
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials, please try again.")
            
    return render_template('login.html')
    
@app.route('/register', methods=['GET', 'POST'])
def register():
    logger.debug("Register endpoint accessed")
    if 'user_id' in session:
        logger.debug("User already logged in, redirecting to dashboard")
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        logger.info(f"Registration attempt for username: {username}")
        
        if password != confirm_password:
            flash("Passwords do not match!")
            return render_template('register.html')
            
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
            conn.commit()
            
            # Auto-login after registration
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            session['user_id'] = user['id']
            session['username'] = username
            
            # Kafka Event Sending REMOVED
                    
            flash("Welcome! Your account has been created.")
            return redirect(url_for('dashboard'))
        except errors.UniqueViolation:
            flash("Username already exists. Please choose another.")
        finally:
            conn.close()
            
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM attendance WHERE user_id = %s ORDER BY date DESC, time DESC", (session['user_id'],))
    records = cursor.fetchall()
    conn.close()
    
    return render_template('dashboard.html', username=session['username'], records=records)

@app.route('/mark_attendance', methods=['POST'])
def mark_attendance():
    logger.debug("Mark attendance endpoint accessed")
    if 'user_id' not in session:
        logger.warning("Unauthenticated attempt to mark attendance")
        return redirect(url_for('login'))
    
    status = request.form.get('status', 'Present')
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    logger.info(f"User {session.get('username')} marking attendance: {status} at {date_str} {time_str}")
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO attendance (user_id, date, time, status) VALUES (%s, %s, %s, %s)", 
                   (session['user_id'], date_str, time_str, status))
    conn.commit()
    conn.close()
    
    # Kafka Event Sending REMOVED
            
    flash(f"Successfully marked '{status}' at {time_str}")
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# API Endpoints
@app.route('/api/attendance', methods=['GET'])
def api_get_attendance():
    logger.debug("API GET attendance called")
    user_id = session.get('user_id')
    if not user_id:
        logger.warning("Unauthorized API GET attendance request")
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT date, time, status FROM attendance WHERE user_id = %s ORDER BY date DESC, time DESC", (user_id,))
    records = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(records)

@app.route('/api/attendance', methods=['POST'])
def api_post_attendance():
    logger.debug("API POST attendance called")
    user_id = session.get('user_id')
    if not user_id:
        logger.warning("Unauthorized API POST attendance request")
        # For external API use without session, you'd normally use a token. 
        # But keeping it simple for now as per session-based app.
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    status = data.get('status', 'Present')
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO attendance (user_id, date, time, status) VALUES (%s, %s, %s, %s)", 
                   (user_id, date_str, time_str, status))
    conn.commit()
    conn.close()
    
    return jsonify({"message": "Attendance recorded", "status": status, "time": time_str}), 201

@app.errorhandler(Exception)
def handle_exception(e):
    logger.exception("Unhandled exception")
    return jsonify(error=str(e)), 500

if __name__ == '__main__':
    try:
        init_db()
        logger.info("Application starting on port 4567...")
        app.run(debug=False, host='0.0.0.0', port=4567)
    except Exception as e:
        logger.critical(f"FATAL: Application failed to start: {e}", exc_info=True)
        raise e
