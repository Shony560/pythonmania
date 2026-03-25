from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
from kafka import KafkaProducer
import json
from psycopg2 import errors # Import psycopg2 errors for specific exception handling

app = Flask(__name__)
app.secret_key = os.environ.get('APP_SECRET_KEY', 'super_secret_attendance_key_123')
DATABASE_URL = os.environ.get('DATABASE_URL')

# Initialize Kafka Producer
try:
    producer = KafkaProducer(
        bootstrap_servers=['localhost:9092'],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
except Exception as e:
    print(f"Warning: Could not connect to Kafka: {e}")
    producer = None

def get_db():
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable is not set")
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def init_db():
    # In Postgres, we usually create tables if they don't exist
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
    
    # Check if users exist before inserting defaults
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()['count'] == 0:
        cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", ('user1', 'pass1'))
        cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", ('user2', 'pass2'))
    
    conn.commit()
    conn.close()

@app.route('/', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            
            # Send Kafka Event
            if producer:
                try:
                    event = {"username": user['username'], "action": "login", "status": "success"}
                    producer.send('user-events', event)
                    producer.flush()
                except Exception as e:
                    print(f"Kafka error: {e}")
                    
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials, please try again.")
            
    return render_template('login.html')
    
@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
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
            
            # Send Kafka Event
            if producer:
                try:
                    event = {"username": username, "action": "register", "status": "success"}
                    producer.send('user-events', event)
                    producer.flush()
                except Exception as e:
                    print(f"Kafka error: {e}")
                    
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
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    status = request.form.get('status', 'Present')
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO attendance (user_id, date, time, status) VALUES (%s, %s, %s, %s)", 
                   (session['user_id'], date_str, time_str, status))
    conn.commit()
    conn.close()
    
    # Send Kafka Event
    if producer:
        try:
            event = {
                "username": session['username'],
                "action": "check_in" if status == "Check In" else "check_out",
                "status": status,
                "date": date_str,
                "time": time_str
            }
            producer.send('user-events', event)
            producer.flush()
        except Exception as e:
            print(f"Kafka error: {e}")
            
    flash(f"Successfully marked '{status}' at {time_str}")
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# API Endpoints
@app.route('/api/attendance', methods=['GET'])
def api_get_attendance():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT date, time, status FROM attendance WHERE user_id = %s ORDER BY date DESC, time DESC", (user_id,))
    records = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(records)

@app.route('/api/attendance', methods=['POST'])
def api_post_attendance():
    user_id = session.get('user_id')
    if not user_id:
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

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=4567)
