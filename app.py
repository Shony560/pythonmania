from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'super_secret_attendance_key_123'
DATABASE = 'attendance.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if not os.path.exists(DATABASE):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                date TEXT,
                time TEXT,
                status TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        # Insert exactly 2 users
        cursor.execute("INSERT INTO users (username, password) VALUES ('user1', 'pass1')")
        cursor.execute("INSERT INTO users (username, password) VALUES ('user2', 'pass2')")
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
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
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
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            
            # Auto-login after registration
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()
            session['user_id'] = user['id']
            session['username'] = username
            flash("Welcome! Your account has been created.")
            return redirect(url_for('dashboard'))
        except sqlite3.IntegrityError:
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
    cursor.execute("SELECT * FROM attendance WHERE user_id = ? ORDER BY date DESC, time DESC", (session['user_id'],))
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
    cursor.execute("INSERT INTO attendance (user_id, date, time, status) VALUES (?, ?, ?, ?)", 
                   (session['user_id'], date_str, time_str, status))
    conn.commit()
    conn.close()
    
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
    cursor.execute("SELECT date, time, status FROM attendance WHERE user_id = ? ORDER BY date DESC, time DESC", (user_id,))
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
    cursor.execute("INSERT INTO attendance (user_id, date, time, status) VALUES (?, ?, ?, ?)", 
                   (user_id, date_str, time_str, status))
    conn.commit()
    conn.close()
    
    return jsonify({"message": "Attendance recorded", "status": status, "time": time_str}), 201

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=4567)
