import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json
import csv
import io
from datetime import datetime, date, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, make_response
)
from werkzeug.security import check_password_hash, generate_password_hash

import urllib.request
import urllib.error

from flask import send_from_directory

import database

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

STATIC_DIRS = [
    os.path.join(BASE_DIR, 'static'),
    os.path.join(BASE_DIR, 'api', 'static'),
    os.path.join(os.getcwd(), 'static'),
    os.path.join(os.getcwd(), 'api', 'static')
]
STATIC_DIR = next((d for d in STATIC_DIRS if os.path.exists(d)), os.path.join(BASE_DIR, 'static'))

TEMPLATE_DIRS = [
    os.path.join(BASE_DIR, 'templates'),
    os.path.join(BASE_DIR, 'api', 'templates'),
    os.path.join(os.getcwd(), 'templates'),
    os.path.join(os.getcwd(), 'api', 'templates')
]
TEMPLATE_DIR = next((d for d in TEMPLATE_DIRS if os.path.exists(d)), os.path.join(BASE_DIR, 'templates'))

app = Flask(
    __name__,
    static_folder=STATIC_DIR,
    static_url_path='/static',
    template_folder=TEMPLATE_DIR
)
app.secret_key = os.environ.get('SECRET_KEY', 'college_mess_secret_key_2026_antigravity')

# Explicit static handler with text/css Content-Type enforcement
@app.route('/static/<path:filename>')
def serve_custom_static(filename):
    for s_dir in STATIC_DIRS:
        target = os.path.join(s_dir, filename)
        if os.path.exists(target):
            response = make_response(send_from_directory(s_dir, filename))
            if filename.endswith('.css'):
                response.headers['Content-Type'] = 'text/css; charset=utf-8'
            elif filename.endswith('.js'):
                response.headers['Content-Type'] = 'application/javascript; charset=utf-8'
            response.headers['Cache-Control'] = 'public, max-age=3600'
            return response
    return "Static file not found", 404

# Firebase Configuration provided by user
FIREBASE_CONFIG = {
    "apiKey": os.environ.get("FIREBASE_API_KEY", "AIzaSyCUe_XSf4gcOHZfTsLzjFHAo1hfJMs9444"),
    "authDomain": os.environ.get("FIREBASE_AUTH_DOMAIN", "messmaster-c8b62.firebaseapp.com"),
    "projectId": os.environ.get("FIREBASE_PROJECT_ID", "messmaster-c8b62"),
    "storageBucket": os.environ.get("FIREBASE_STORAGE_BUCKET", "messmaster-c8b62.firebasestorage.app"),
    "messagingSenderId": os.environ.get("FIREBASE_MESSAGING_SENDER_ID", "937370272941"),
    "appId": os.environ.get("FIREBASE_APP_ID", "1:937370272941:web:e1b284f69e12a2fbe87224")
}

# Context processor for global template variables
@app.context_processor
def inject_global_data():
    conn = database.get_db_connection()
    mess_name = database.get_setting('mess_name', 'Campus Royal Mess & Dining Hall')
    college_name = database.get_setting('college_name', 'Engineering & Technology Campus')
    currency_symbol = database.get_setting('currency_symbol', '₹')
    user = None
    if 'user_id' in session:
        user = conn.execute("SELECT id, username, full_name, role FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    
    # Check count of pending absence adjustments and expiring students for sidebar badges
    today_str = date.today().isoformat()
    three_days_later = (date.today() + timedelta(days=3)).isoformat()
    
    expiring_count = conn.execute("""
        SELECT COUNT(*) as count FROM mess_plans 
        WHERE is_current = 1 AND current_expiry_date >= ? AND current_expiry_date <= ? AND status = 'Active'
    """, (today_str, three_days_later)).fetchone()['count']

    expired_count = conn.execute("""
        SELECT COUNT(*) as count FROM students WHERE status = 'Expired'
    """).fetchone()['count']

    conn.close()

    return {
        'mess_name': mess_name,
        'college_name': college_name,
        'currency_symbol': currency_symbol,
        'current_user': user,
        'today_date': date.today().isoformat(),
        'badge_expiring_count': expiring_count,
        'badge_expired_count': expired_count,
        'firebase_config': FIREBASE_CONFIG
    }

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please sign in to access the Mess Management System.", "warning")
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# ----------------- AUTHENTICATION ROUTES ----------------- #

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        if session.get('role') == 'student':
            return redirect(url_for('student_dashboard'))
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        # 1. If username is an email, try Firebase Auth sign-in with password first
        if '@' in username:
            try:
                fb_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_CONFIG['apiKey']}"
                req_data = json.dumps({"email": username, "password": password, "returnSecureToken": True}).encode('utf-8')
                req = urllib.request.Request(fb_url, data=req_data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    fb_res = json.loads(resp.read().decode('utf-8'))
                    verified_email = fb_res.get('email', username)
                    display_name = fb_res.get('displayName') or verified_email.split('@')[0]

                    conn = database.get_db_connection()
                    cursor = conn.cursor()
                    user = cursor.execute("SELECT * FROM users WHERE username = ?", (verified_email,)).fetchone()
                    if not user:
                        cursor.execute("""
                            INSERT INTO users (username, password_hash, full_name, role)
                            VALUES (?, ?, ?, 'admin')
                        """, (verified_email, generate_password_hash(password), display_name))
                        conn.commit()
                        user = cursor.execute("SELECT * FROM users WHERE username = ?", (verified_email,)).fetchone()
                    conn.close()

                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    session['full_name'] = user['full_name']
                    session['role'] = user['role']
                    session['student_id'] = dict(user).get('student_id') if 'student_id' in user.keys() else None
                    session['auth_provider'] = 'firebase'
                    flash(f"Welcome back, {user['full_name']} (Firebase Auth)!", "success")
                    next_page = request.args.get('next')
                    if user['role'] == 'student':
                        return redirect(next_page or url_for('student_dashboard'))
                    return redirect(next_page or url_for('dashboard'))
            except Exception as e:
                print(f"Firebase password auth notice: {e}")

        # 2. Local database user lookup (e.g., admin / admin123 or student1 / password123)
        conn = database.get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            session['student_id'] = dict(user).get('student_id') if 'student_id' in user.keys() else None
            session['auth_provider'] = 'local'
            flash(f"Welcome back, {user['full_name']}!", "success")
            next_page = request.args.get('next')
            if user['role'] == 'student':
                return redirect(next_page or url_for('student_dashboard'))
            return redirect(next_page or url_for('dashboard'))
        else:
            flash("Invalid username or password. Please try again.", "danger")

    return render_template('login.html', firebase_config=FIREBASE_CONFIG)

@app.route('/api/firebase-login', methods=['POST'])
def api_firebase_login():
    """Handles client-side Firebase token authentication (Google Sign-In / Firebase Auth)"""
    data = request.get_json() or {}
    id_token = data.get('idToken')
    email = data.get('email', '').strip()
    display_name = data.get('displayName') or (email.split('@')[0] if email else 'Firebase Admin')

    if not id_token:
        return jsonify({'success': False, 'message': 'Missing Firebase ID token'}), 400

    verified_email = email
    try:
        # Verify with Google Identity Toolkit
        lookup_url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={FIREBASE_CONFIG['apiKey']}"
        req_body = json.dumps({"idToken": id_token}).encode('utf-8')
        req = urllib.request.Request(lookup_url, data=req_body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            lookup_res = json.loads(resp.read().decode('utf-8'))
            users_list = lookup_res.get('users', [])
            if users_list:
                verified_email = users_list[0].get('email', email)
                if users_list[0].get('displayName'):
                    display_name = users_list[0]['displayName']
    except Exception as e:
        print(f"Google Token Verification Notice: {e}")
        if not verified_email:
            return jsonify({'success': False, 'message': f'Authentication failed: {str(e)}'}), 401

    # Ensure user exists in SQLite database
    conn = database.get_db_connection()
    cursor = conn.cursor()
    user = cursor.execute("SELECT * FROM users WHERE username = ?", (verified_email,)).fetchone()
    if not user:
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, role)
            VALUES (?, ?, ?, 'admin')
        """, (verified_email, generate_password_hash(os.urandom(16).hex()), display_name))
        conn.commit()
        user = cursor.execute("SELECT * FROM users WHERE username = ?", (verified_email,)).fetchone()
    conn.close()

    # Create session
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['full_name'] = user['full_name']
    session['role'] = user['role']
    session['auth_provider'] = 'firebase'

    return jsonify({'success': True, 'redirect': url_for('dashboard')})

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for('login'))

# ----------------- USER REGISTRATION WITH MEAL SELECTION ----------------- #

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        if session.get('role') == 'student':
            return redirect(url_for('student_dashboard'))
        return redirect(url_for('dashboard'))

    conn = database.get_db_connection()
    default_veg = float(database.get_setting('veg_monthly_fee', '3200'))
    default_nonveg = float(database.get_setting('nonveg_monthly_fee', '4200'))
    currency_symbol = database.get_setting('currency_symbol', '₹')

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        mobile = request.form.get('mobile', '').strip()
        college_name = request.form.get('college_name', '').strip()
        username = request.form.get('username', '').strip() or mobile
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        # Meal selection options
        mess_type = request.form.get('mess_type', 'Veg')
        meal_preference = request.form.get('meal_preference', 'Both')
        start_date_str = request.form.get('start_date', '').strip() or date.today().isoformat()
        
        try:
            plan_duration = int(request.form.get('plan_duration', 30))
            base_fee = default_veg if mess_type == 'Veg' else default_nonveg
            calc_fee = (base_fee / 30.0) * plan_duration
            if meal_preference in ('Lunch', 'Dinner'):
                calc_fee = calc_fee * 0.6  # 40% reduction for single session
            
            total_fee = float(request.form.get('total_fee', calc_fee))
            amount_paid = float(request.form.get('amount_paid', 0.0))
        except ValueError:
            flash("Invalid numeric value for duration or fee amount.", "danger")
            conn.close()
            return redirect(url_for('register'))

        payment_method = request.form.get('payment_method', 'UPI')
        notes = request.form.get('notes', 'Initial student admission registration')

        # Validation checks
        if not full_name or not mobile or not college_name or not password:
            flash("Please complete all required fields (Name, Mobile, College, Password).", "danger")
            conn.close()
            return redirect(url_for('register'))

        if password != confirm_password:
            flash("Passwords do not match. Please verify and try again.", "danger")
            conn.close()
            return redirect(url_for('register'))

        if len(mobile) < 10:
            flash("Please enter a valid 10-digit mobile number.", "danger")
            conn.close()
            return redirect(url_for('register'))

        dup_user = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if dup_user:
            flash(f"The username '{username}' is already in use. Please select another.", "danger")
            conn.close()
            return redirect(url_for('register'))

        dup_stu = conn.execute("SELECT id FROM students WHERE mobile = ?", (mobile,)).fetchone()
        if dup_stu:
            flash(f"A student account with mobile {mobile} already exists. Please sign in.", "warning")
            conn.close()
            return redirect(url_for('login'))

        student_id = database.generate_student_id()
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        expiry_date = start_date + timedelta(days=plan_duration)
        expiry_date_str = expiry_date.isoformat()

        cursor = conn.cursor()
        # 1. Insert student record
        cursor.execute("""
            INSERT INTO students (student_id, full_name, mobile, college_name, mess_type, meal_preference, status, admission_date)
            VALUES (?, ?, ?, ?, ?, ?, 'Active', ?)
        """, (student_id, full_name, mobile, college_name, mess_type, meal_preference, start_date_str))

        # 2. Insert initial mess plan
        cursor.execute("""
            INSERT INTO mess_plans (
                student_id, plan_duration_days, start_date, original_expiry_date,
                current_expiry_date, total_extension_days, mess_type, total_fee, status, is_current
            ) VALUES (?, ?, ?, ?, ?, 0, ?, ?, 'Active', 1)
        """, (student_id, plan_duration, start_date_str, expiry_date_str, expiry_date_str, mess_type, total_fee))
        plan_id = cursor.lastrowid

        # 3. Insert payment if any initial amount was paid
        if amount_paid > 0:
            receipt_no = database.generate_receipt_no()
            cursor.execute("""
                INSERT INTO payments (receipt_no, student_id, plan_id, amount, payment_date, payment_method, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (receipt_no, student_id, plan_id, amount_paid, start_date_str, payment_method, notes))

        # 4. Insert student user account
        hashed_pw = generate_password_hash(password)
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, role, student_id)
            VALUES (?, ?, ?, 'student', ?)
        """, (username, hashed_pw, full_name, student_id))
        new_user_id = cursor.lastrowid

        conn.commit()
        conn.close()

        # Log in newly registered student
        session['user_id'] = new_user_id
        session['username'] = username
        session['full_name'] = full_name
        session['role'] = 'student'
        session['student_id'] = student_id
        session['auth_provider'] = 'local'

        flash(f"Account created successfully! Welcome to MessMaster, {full_name} (ID: {student_id}).", "success")
        return redirect(url_for('student_dashboard'))

    conn.close()
    return render_template('register.html',
        default_veg=default_veg,
        default_nonveg=default_nonveg,
        currency_symbol=currency_symbol,
        today_date=date.today().isoformat()
    )

# ----------------- DEDICATED STUDENT USER DASHBOARD ----------------- #

@app.route('/student/dashboard')
@app.route('/my-dashboard')
@login_required
def student_dashboard():
    database.update_all_mess_expiries()
    
    # If admin, allow inspecting a specific student via ?student_id=...
    student_id = request.args.get('student_id')
    if not student_id or session.get('role') == 'student':
        student_id = session.get('student_id')

    if not student_id:
        conn = database.get_db_connection()
        first_stu = conn.execute("SELECT student_id FROM students WHERE status = 'Active' LIMIT 1").fetchone()
        conn.close()
        if first_stu:
            student_id = first_stu['student_id']
        else:
            flash("No student record found to display.", "warning")
            return redirect(url_for('students'))

    data = database.get_student_dashboard_data(student_id)
    if not data:
        flash(f"Student record {student_id} not found.", "danger")
        return redirect(url_for('dashboard'))

    currency_symbol = database.get_setting('currency_symbol', '₹')
    mess_name = database.get_setting('mess_name', 'Campus Dining Facility')
    college_name = database.get_setting('college_name', 'Campus Institution')

    return render_template('student_dashboard.html',
        **data,
        currency_symbol=currency_symbol,
        mess_name=mess_name,
        college_name=college_name
    )

# ----------------- QUICK QR CHECK-IN API ----------------- #

@app.route('/api/qr-checkin', methods=['POST'])
@login_required
def api_qr_checkin():
    data = request.get_json() or {}
    student_id = data.get('student_id')
    meal_session = data.get('meal_session', 'Lunch')
    today_str = date.today().isoformat()

    if not student_id:
        student_id = session.get('student_id')

    if not student_id:
        return jsonify({'success': False, 'message': 'Student ID is required'}), 400

    conn = database.get_db_connection()
    student = conn.execute("SELECT full_name, status, mess_type FROM students WHERE student_id = ?", (student_id,)).fetchone()
    if not student:
        conn.close()
        return jsonify({'success': False, 'message': 'Student record not found'}), 404

    if student['status'] == 'Expired':
        conn.close()
        return jsonify({'success': False, 'message': f"Student plan has expired. Please renew plan before {meal_session} check-in."}), 400

    if student['status'] == 'Deactivated':
        conn.close()
        return jsonify({'success': False, 'message': 'Student account is deactivated. Contact mess office.'}), 400

    # Record attendance safely
    cursor = conn.cursor()
    existing = cursor.execute("SELECT id FROM attendance WHERE student_id = ? AND date = ?", (student_id, today_str)).fetchone()
    if existing:
        cursor.execute("""
            UPDATE attendance 
            SET status = 'Present', meal_session = ?, marked_by = ?, created_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (meal_session, session.get('username', 'qr-scanner'), existing['id']))
    else:
        cursor.execute("""
            INSERT INTO attendance (student_id, date, meal_session, status, marked_by)
            VALUES (?, ?, ?, 'Present', ?)
        """, (student_id, today_str, meal_session, session.get('username', 'qr-scanner')))
    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'message': f"Check-in verified for {student['full_name']} ({student['mess_type']} Mess - {meal_session})!",
        'student_id': student_id,
        'student_name': student['full_name'],
        'meal_session': meal_session,
        'date': today_str,
        'status': 'Present'
    })

# ----------------- ADMIN DASHBOARD ----------------- #

@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    if session.get('role') == 'student':
        return redirect(url_for('student_dashboard'))
    database.update_all_mess_expiries()
    conn = database.get_db_connection()
    today_str = date.today().isoformat()
    three_days_str = (date.today() + timedelta(days=3)).isoformat()

    # Metrics
    total_admitted = conn.execute("SELECT COUNT(*) as c FROM students").fetchone()['c']
    active_students = conn.execute("SELECT COUNT(*) as c FROM students WHERE status = 'Active'").fetchone()['c']
    veg_students = conn.execute("SELECT COUNT(*) as c FROM students WHERE status = 'Active' AND mess_type = 'Veg'").fetchone()['c']
    nonveg_students = conn.execute("SELECT COUNT(*) as c FROM students WHERE status = 'Active' AND mess_type = 'Non-Veg'").fetchone()['c']
    expired_students = conn.execute("SELECT COUNT(*) as c FROM students WHERE status = 'Expired'").fetchone()['c']

    # Financials
    total_fees_row = conn.execute("SELECT COALESCE(SUM(total_fee), 0) as total FROM mess_plans").fetchone()
    total_fees_expected = total_fees_row['total']
    total_collected_row = conn.execute("SELECT COALESCE(SUM(amount), 0) as total FROM payments").fetchone()
    total_fees_collected = total_collected_row['total']
    pending_payments = max(0.0, total_fees_expected - total_fees_collected)

    # Today's attendance
    absent_today = conn.execute("""
        SELECT COUNT(*) as c FROM attendance a 
        JOIN students s ON a.student_id = s.student_id 
        WHERE a.date = ? AND a.status = 'Absent' AND s.status = 'Active'
    """, (today_str,)).fetchone()['c']

    present_today = conn.execute("""
        SELECT COUNT(*) as c FROM attendance a 
        JOIN students s ON a.student_id = s.student_id 
        WHERE a.date = ? AND a.status = 'Present' AND s.status = 'Active'
    """, (today_str,)).fetchone()['c']

    # Expiring soon (1 to 3 days remaining)
    expiring_soon = conn.execute("""
        SELECT s.student_id, s.full_name, s.mobile, s.mess_type, p.current_expiry_date,
               (julianday(p.current_expiry_date) - julianday(?)) as days_left
        FROM mess_plans p
        JOIN students s ON p.student_id = s.student_id
        WHERE p.is_current = 1 AND p.current_expiry_date >= ? AND p.current_expiry_date <= ? AND s.status = 'Active'
        ORDER BY p.current_expiry_date ASC
    """, (today_str, today_str, three_days_str)).fetchall()

    # Eligible consecutive absences
    eligible_absences = database.detect_all_eligible_absences()

    # 7-day attendance trend data for Chart.js
    chart_dates = []
    chart_presents = []
    chart_absents = []
    for i in range(6, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        chart_dates.append(datetime.strptime(d, "%Y-%m-%d").strftime("%d %b"))
        p_count = conn.execute("SELECT COUNT(*) as c FROM attendance WHERE date = ? AND status = 'Present'", (d,)).fetchone()['c']
        a_count = conn.execute("SELECT COUNT(*) as c FROM attendance WHERE date = ? AND status = 'Absent'", (d,)).fetchone()['c']
        chart_presents.append(p_count)
        chart_absents.append(a_count)

    # Recent payments for Dashboard Recent Activity / Transactions list
    recent_payments = conn.execute("""
        SELECT p.*, s.full_name, s.mess_type 
        FROM payments p
        JOIN students s ON p.student_id = s.student_id
        ORDER BY p.payment_date DESC, p.id DESC
        LIMIT 4
    """).fetchall()

    conn.close()

    return render_template('dashboard.html',
        total_admitted=total_admitted,
        active_students=active_students,
        veg_students=veg_students,
        nonveg_students=nonveg_students,
        expired_students=expired_students,
        total_fees_collected=total_fees_collected,
        pending_payments=pending_payments,
        absent_today=absent_today,
        present_today=present_today,
        expiring_soon=expiring_soon,
        eligible_absences=eligible_absences,
        recent_payments=recent_payments,
        chart_dates=json.dumps(chart_dates),
        chart_presents=json.dumps(chart_presents),
        chart_absents=json.dumps(chart_absents)
    )

# ----------------- STUDENT ADMISSION ----------------- #

@app.route('/admission', methods=['GET', 'POST'])
@login_required
def admission():
    conn = database.get_db_connection()
    default_veg = float(database.get_setting('veg_monthly_fee', '3200'))
    default_nonveg = float(database.get_setting('nonveg_monthly_fee', '4200'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        mobile = request.form.get('mobile', '').strip()
        college_name = request.form.get('college_name', '').strip()
        admission_date_str = request.form.get('admission_date', '').strip() or date.today().isoformat()
        mess_start_date_str = request.form.get('mess_start_date', '').strip() or date.today().isoformat()
        mess_type = request.form.get('mess_type', 'Veg')
        
        try:
            plan_duration = int(request.form.get('plan_duration', 30))
            total_fee = float(request.form.get('total_fee', default_veg if mess_type == 'Veg' else default_nonveg))
            amount_paid = float(request.form.get('amount_paid', 0.0))
        except ValueError:
            flash("Invalid numbers provided for duration or fee.", "danger")
            return redirect(url_for('admission'))

        payment_method = request.form.get('payment_method', 'UPI')
        notes = request.form.get('notes', 'Admission payment')

        # Validations
        if not full_name or not mobile or not college_name:
            flash("Please fill in all required fields (Name, Mobile, College).", "danger")
            return redirect(url_for('admission'))

        if len(mobile) < 10:
            flash("Please enter a valid mobile number.", "danger")
            return redirect(url_for('admission'))

        if amount_paid < 0:
            flash("Amount paid cannot be negative.", "danger")
            return redirect(url_for('admission'))

        if amount_paid > total_fee:
            flash("Amount paid cannot exceed total mess fee.", "danger")
            return redirect(url_for('admission'))

        # Check duplicate mobile
        dup = conn.execute("SELECT id FROM students WHERE mobile = ?", (mobile,)).fetchone()
        if dup:
            flash(f"A student record with mobile number {mobile} already exists!", "danger")
            conn.close()
            return redirect(url_for('admission'))

        student_id = database.generate_student_id()
        start_date = datetime.strptime(mess_start_date_str, "%Y-%m-%d").date()
        expiry_date = start_date + timedelta(days=plan_duration)
        expiry_date_str = expiry_date.isoformat()

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO students (student_id, full_name, mobile, college_name, mess_type, status, admission_date)
            VALUES (?, ?, ?, ?, ?, 'Active', ?)
        """, (student_id, full_name, mobile, college_name, mess_type, admission_date_str))

        cursor.execute("""
            INSERT INTO mess_plans (
                student_id, plan_duration_days, start_date, original_expiry_date,
                current_expiry_date, total_extension_days, mess_type, total_fee, status, is_current
            ) VALUES (?, ?, ?, ?, ?, 0, ?, ?, 'Active', 1)
        """, (student_id, plan_duration, mess_start_date_str, expiry_date_str, expiry_date_str, mess_type, total_fee))

        plan_id = cursor.lastrowid

        # Record payment if paid
        receipt_no = None
        if amount_paid > 0:
            receipt_no = database.generate_receipt_no()
            cursor.execute("""
                INSERT INTO payments (receipt_no, student_id, plan_id, amount, payment_date, payment_method, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (receipt_no, student_id, plan_id, amount_paid, admission_date_str, payment_method, notes))

        conn.commit()
        conn.close()

        flash(f"Student {full_name} admitted successfully with ID: {student_id}!", "success")
        if receipt_no:
            return redirect(url_for('view_receipt', receipt_no=receipt_no))
        return redirect(url_for('student_profile', student_id=student_id))

    next_student_id = database.generate_student_id()
    conn.close()
    return render_template('admission.html',
        next_student_id=next_student_id,
        default_veg_fee=default_veg,
        default_nonveg_fee=default_nonveg
    )

# ----------------- ALL STUDENTS MANAGEMENT ----------------- #

@app.route('/students')
@login_required
def students():
    database.update_all_mess_expiries()
    conn = database.get_db_connection()
    search = request.args.get('search', '').strip()
    mess_filter = request.args.get('mess_type', 'all')
    status_filter = request.args.get('status', 'all')
    payment_filter = request.args.get('payment_status', 'all')
    sort_by = request.args.get('sort_by', 'admission_date_desc')

    query = """
        SELECT s.id, s.student_id, s.full_name, s.mobile, s.college_name, s.mess_type, s.status, s.admission_date,
               p.id as plan_id, p.plan_duration_days, p.start_date, p.current_expiry_date, p.total_fee, p.total_extension_days,
               COALESCE((SELECT SUM(amount) FROM payments WHERE student_id = s.student_id), 0) as total_paid,
               (p.total_fee - COALESCE((SELECT SUM(amount) FROM payments WHERE student_id = s.student_id), 0)) as balance,
               (julianday(p.current_expiry_date) - julianday(date('now'))) as remaining_days
        FROM students s
        LEFT JOIN mess_plans p ON s.student_id = p.student_id AND p.is_current = 1
        WHERE 1=1
    """
    params = []

    if search:
        query += " AND (s.student_id LIKE ? OR s.full_name LIKE ? OR s.mobile LIKE ? OR s.college_name LIKE ?)"
        like_term = f"%{search}%"
        params.extend([like_term, like_term, like_term, like_term])

    if mess_filter in ('Veg', 'Non-Veg'):
        query += " AND s.mess_type = ?"
        params.append(mess_filter)

    if status_filter in ('Active', 'Expired', 'Deactivated'):
        query += " AND s.status = ?"
        params.append(status_filter)

    # Sorting
    if sort_by == 'name_asc':
        query += " ORDER BY s.full_name ASC"
    elif sort_by == 'id_asc':
        query += " ORDER BY s.student_id ASC"
    elif sort_by == 'remaining_days_asc':
        query += " ORDER BY remaining_days ASC"
    elif sort_by == 'balance_desc':
        query += " ORDER BY balance DESC"
    else:
        query += " ORDER BY s.admission_date DESC"

    all_records = conn.execute(query, params).fetchall()

    # Filter payment status in Python if requested
    filtered_list = []
    for r in all_records:
        bal = r['balance'] if r['balance'] is not None else 0
        paid = r['total_paid']
        fee = r['total_fee'] if r['total_fee'] is not None else 0

        if bal <= 0 and paid > 0:
            p_status = 'Paid'
        elif paid > 0 and bal > 0:
            p_status = 'Partially Paid'
        else:
            p_status = 'Pending'

        if payment_filter == 'Paid' and p_status != 'Paid':
            continue
        if payment_filter == 'Partially Paid' and p_status != 'Partially Paid':
            continue
        if payment_filter == 'Pending' and p_status != 'Pending':
            continue

        item = dict(r)
        item['payment_status'] = p_status
        filtered_list.append(item)

    conn.close()

    return render_template('students.html',
        students=filtered_list,
        search=search,
        mess_filter=mess_filter,
        status_filter=status_filter,
        payment_filter=payment_filter,
        sort_by=sort_by
    )

@app.route('/student/<student_id>')
@login_required
def student_profile(student_id):
    database.update_all_mess_expiries()
    conn = database.get_db_connection()
    today_str = date.today().isoformat()

    student = conn.execute("SELECT * FROM students WHERE student_id = ?", (student_id,)).fetchone()
    if not student:
        flash(f"Student with ID {student_id} not found.", "danger")
        conn.close()
        return redirect(url_for('students'))

    # Current active mess plan
    current_plan = conn.execute("""
        SELECT *, (julianday(current_expiry_date) - julianday(?)) as remaining_days
        FROM mess_plans 
        WHERE student_id = ? AND is_current = 1
    """, (today_str, student_id)).fetchone()

    # Plan history
    plan_history = conn.execute("""
        SELECT * FROM mess_plans 
        WHERE student_id = ? 
        ORDER BY id DESC
    """, (student_id,)).fetchall()

    # Payment history
    payments = conn.execute("""
        SELECT * FROM payments 
        WHERE student_id = ? 
        ORDER BY payment_date DESC, id DESC
    """, (student_id,)).fetchall()

    total_fees = sum([p['total_fee'] for p in plan_history]) if plan_history else 0
    total_paid = sum([pay['amount'] for pay in payments]) if payments else 0
    balance = max(0.0, total_fees - total_paid)

    # Attendance stats
    att_stats = conn.execute("""
        SELECT 
            COUNT(*) as total_days,
            SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_days,
            SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent_days
        FROM attendance 
        WHERE student_id = ?
    """, (student_id,)).fetchone()

    recent_attendance = conn.execute("""
        SELECT * FROM attendance 
        WHERE student_id = ? 
        ORDER BY date DESC LIMIT 30
    """, (student_id,)).fetchall()

    # Adjustments
    adjustments = conn.execute("""
        SELECT * FROM absence_adjustments 
        WHERE student_id = ? 
        ORDER BY id DESC
    """, (student_id,)).fetchall()

    # Detect if any new eligible streaks exist
    eligible_streaks = database.detect_consecutive_absences_for_student(student_id)

    conn.close()

    return render_template('student_profile.html',
        student=student,
        current_plan=current_plan,
        plan_history=plan_history,
        payments=payments,
        total_fees=total_fees,
        total_paid=total_paid,
        balance=balance,
        att_stats=att_stats,
        recent_attendance=recent_attendance,
        adjustments=adjustments,
        eligible_streaks=eligible_streaks
    )

@app.route('/student/<student_id>/edit', methods=['POST'])
@login_required
def edit_student(student_id):
    full_name = request.form.get('full_name', '').strip()
    mobile = request.form.get('mobile', '').strip()
    college_name = request.form.get('college_name', '').strip()
    mess_type = request.form.get('mess_type', 'Veg')

    if not full_name or not mobile or not college_name:
        flash("All fields are required.", "danger")
        return redirect(url_for('student_profile', student_id=student_id))

    conn = database.get_db_connection()
    # Check duplicate mobile for other student
    dup = conn.execute("SELECT id FROM students WHERE mobile = ? AND student_id != ?", (mobile, student_id)).fetchone()
    if dup:
        flash(f"Mobile number {mobile} is already in use by another student.", "danger")
        conn.close()
        return redirect(url_for('student_profile', student_id=student_id))

    conn.execute("""
        UPDATE students 
        SET full_name = ?, mobile = ?, college_name = ?, mess_type = ?, updated_at = CURRENT_TIMESTAMP
        WHERE student_id = ?
    """, (full_name, mobile, college_name, mess_type, student_id))
    
    # Also update current plan mess_type if active
    conn.execute("""
        UPDATE mess_plans SET mess_type = ? WHERE student_id = ? AND is_current = 1
    """, (mess_type, student_id))

    conn.commit()
    conn.close()

    flash("Student details updated successfully.", "success")
    return redirect(url_for('student_profile', student_id=student_id))

@app.route('/student/<student_id>/toggle-status', methods=['POST'])
@login_required
def toggle_student_status(student_id):
    conn = database.get_db_connection()
    student = conn.execute("SELECT status FROM students WHERE student_id = ?", (student_id,)).fetchone()
    if not student:
        conn.close()
        flash("Student not found.", "danger")
        return redirect(url_for('students'))

    new_status = 'Active' if student['status'] == 'Deactivated' else 'Deactivated'
    conn.execute("UPDATE students SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE student_id = ?", (new_status, student_id))
    conn.commit()
    conn.close()

    flash(f"Student account {student_id} is now {new_status}.", "info")
    return redirect(url_for('student_profile', student_id=student_id))

@app.route('/student/<student_id>/renew', methods=['POST'])
@login_required
def renew_mess_plan(student_id):
    try:
        duration = int(request.form.get('duration_days', 30))
        fee = float(request.form.get('fee', 3200))
        amount_paid = float(request.form.get('amount_paid', 0))
    except ValueError:
        flash("Invalid duration or fee input.", "danger")
        return redirect(url_for('student_profile', student_id=student_id))

    mess_type = request.form.get('mess_type', 'Veg')
    start_date_str = request.form.get('start_date', '').strip() or date.today().isoformat()
    payment_method = request.form.get('payment_method', 'UPI')
    notes = request.form.get('notes', 'Mess plan renewal')

    if amount_paid < 0 or amount_paid > fee:
        flash("Payment amount must be between 0 and the renewal fee.", "danger")
        return redirect(url_for('student_profile', student_id=student_id))

    conn = database.get_db_connection()
    cursor = conn.cursor()

    # Archive previous current plan
    cursor.execute("""
        UPDATE mess_plans 
        SET is_current = 0, status = 'Renewed' 
        WHERE student_id = ? AND is_current = 1
    """, (student_id,))

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    expiry_date = start_date + timedelta(days=duration)
    expiry_date_str = expiry_date.isoformat()

    cursor.execute("""
        INSERT INTO mess_plans (
            student_id, plan_duration_days, start_date, original_expiry_date,
            current_expiry_date, total_extension_days, mess_type, total_fee, status, is_current
        ) VALUES (?, ?, ?, ?, ?, 0, ?, ?, 'Active', 1)
    """, (student_id, duration, start_date_str, expiry_date_str, expiry_date_str, mess_type, fee))

    new_plan_id = cursor.lastrowid

    # Record payment if any
    receipt_no = None
    if amount_paid > 0:
        receipt_no = database.generate_receipt_no()
        cursor.execute("""
            INSERT INTO payments (receipt_no, student_id, plan_id, amount, payment_date, payment_method, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (receipt_no, student_id, new_plan_id, amount_paid, start_date_str, payment_method, notes))

    # Set student to Active
    cursor.execute("""
        UPDATE students 
        SET status = 'Active', mess_type = ?, updated_at = CURRENT_TIMESTAMP 
        WHERE student_id = ?
    """, (mess_type, student_id))

    conn.commit()
    conn.close()

    flash(f"Mess plan renewed successfully for {duration} days! New expiry date: {expiry_date_str}", "success")
    if receipt_no:
        return redirect(url_for('view_receipt', receipt_no=receipt_no))
    return redirect(url_for('student_profile', student_id=student_id))

# ----------------- VEG & NON-VEG DEDICATED MANAGEMENT ----------------- #

@app.route('/mess/veg')
@login_required
def veg_mess():
    database.update_all_mess_expiries()
    conn = database.get_db_connection()
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', 'all')
    sort_by = request.args.get('sort_by', 'remaining_days_asc')

    query = """
        SELECT s.student_id, s.full_name, s.mobile, s.college_name, s.status,
               p.start_date, p.current_expiry_date, p.total_fee,
               COALESCE((SELECT SUM(amount) FROM payments WHERE student_id = s.student_id), 0) as total_paid,
               (p.total_fee - COALESCE((SELECT SUM(amount) FROM payments WHERE student_id = s.student_id), 0)) as balance,
               (julianday(p.current_expiry_date) - julianday(date('now'))) as remaining_days
        FROM students s
        JOIN mess_plans p ON s.student_id = p.student_id AND p.is_current = 1
        WHERE s.mess_type = 'Veg'
    """
    params = []

    if search:
        query += " AND (s.student_id LIKE ? OR s.full_name LIKE ? OR s.mobile LIKE ?)"
        like_term = f"%{search}%"
        params.extend([like_term, like_term, like_term])

    if status_filter in ('Active', 'Expired', 'Deactivated'):
        query += " AND s.status = ?"
        params.append(status_filter)

    if sort_by == 'name_asc':
        query += " ORDER BY s.full_name ASC"
    elif sort_by == 'expiry_date_asc':
        query += " ORDER BY p.current_expiry_date ASC"
    else:
        query += " ORDER BY remaining_days ASC"

    students_list = conn.execute(query, params).fetchall()

    # Stats for Veg
    total_veg = conn.execute("SELECT COUNT(*) as c FROM students WHERE mess_type = 'Veg'").fetchone()['c']
    active_veg = conn.execute("SELECT COUNT(*) as c FROM students WHERE mess_type = 'Veg' AND status = 'Active'").fetchone()['c']
    expired_veg = conn.execute("SELECT COUNT(*) as c FROM students WHERE mess_type = 'Veg' AND status = 'Expired'").fetchone()['c']
    veg_collected = conn.execute("""
        SELECT COALESCE(SUM(pay.amount), 0) as c 
        FROM payments pay 
        JOIN students s ON pay.student_id = s.student_id 
        WHERE s.mess_type = 'Veg'
    """).fetchone()['c']

    conn.close()

    return render_template('veg_mess.html',
        students=students_list,
        search=search,
        status_filter=status_filter,
        sort_by=sort_by,
        total_veg=total_veg,
        active_veg=active_veg,
        expired_veg=expired_veg,
        veg_collected=veg_collected
    )

@app.route('/mess/non-veg')
@login_required
def nonveg_mess():
    database.update_all_mess_expiries()
    conn = database.get_db_connection()
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', 'all')
    sort_by = request.args.get('sort_by', 'remaining_days_asc')

    query = """
        SELECT s.student_id, s.full_name, s.mobile, s.college_name, s.status,
               p.start_date, p.current_expiry_date, p.total_fee,
               COALESCE((SELECT SUM(amount) FROM payments WHERE student_id = s.student_id), 0) as total_paid,
               (p.total_fee - COALESCE((SELECT SUM(amount) FROM payments WHERE student_id = s.student_id), 0)) as balance,
               (julianday(p.current_expiry_date) - julianday(date('now'))) as remaining_days
        FROM students s
        JOIN mess_plans p ON s.student_id = p.student_id AND p.is_current = 1
        WHERE s.mess_type = 'Non-Veg'
    """
    params = []

    if search:
        query += " AND (s.student_id LIKE ? OR s.full_name LIKE ? OR s.mobile LIKE ?)"
        like_term = f"%{search}%"
        params.extend([like_term, like_term, like_term])

    if status_filter in ('Active', 'Expired', 'Deactivated'):
        query += " AND s.status = ?"
        params.append(status_filter)

    if sort_by == 'name_asc':
        query += " ORDER BY s.full_name ASC"
    elif sort_by == 'expiry_date_asc':
        query += " ORDER BY p.current_expiry_date ASC"
    else:
        query += " ORDER BY remaining_days ASC"

    students_list = conn.execute(query, params).fetchall()

    # Stats for Non-Veg
    total_nonveg = conn.execute("SELECT COUNT(*) as c FROM students WHERE mess_type = 'Non-Veg'").fetchone()['c']
    active_nonveg = conn.execute("SELECT COUNT(*) as c FROM students WHERE mess_type = 'Non-Veg' AND status = 'Active'").fetchone()['c']
    expired_nonveg = conn.execute("SELECT COUNT(*) as c FROM students WHERE mess_type = 'Non-Veg' AND status = 'Expired'").fetchone()['c']
    nonveg_collected = conn.execute("""
        SELECT COALESCE(SUM(pay.amount), 0) as c 
        FROM payments pay 
        JOIN students s ON pay.student_id = s.student_id 
        WHERE s.mess_type = 'Non-Veg'
    """).fetchone()['c']

    conn.close()

    return render_template('nonveg_mess.html',
        students=students_list,
        search=search,
        status_filter=status_filter,
        sort_by=sort_by,
        total_nonveg=total_nonveg,
        active_nonveg=active_nonveg,
        expired_nonveg=expired_nonveg,
        nonveg_collected=nonveg_collected
    )

# ----------------- ATTENDANCE SYSTEM ----------------- #

@app.route('/attendance', methods=['GET', 'POST'])
@login_required
def attendance():
    database.update_all_mess_expiries()
    conn = database.get_db_connection()
    selected_date = request.args.get('date', date.today().isoformat())
    mess_filter = request.args.get('mess_type', 'all')
    search = request.args.get('search', '').strip()

    if request.method == 'POST':
        date_to_save = request.form.get('attendance_date', date.today().isoformat())
        # Parse posted attendance values
        # Form inputs: att_status_{student_id} = 'Present' or 'Absent'
        cursor = conn.cursor()
        saved_count = 0
        for key, val in request.form.items():
            if key.startswith('att_status_'):
                student_id = key.replace('att_status_', '')
                att_status = 'Present' if val == 'Present' else 'Absent'
                cursor.execute("""
                    INSERT INTO attendance (student_id, date, status, marked_by)
                    VALUES (?, ?, ?, 'admin')
                    ON CONFLICT(student_id, date) DO UPDATE SET 
                        status = excluded.status,
                        created_at = CURRENT_TIMESTAMP
                """, (student_id, date_to_save, att_status))
                saved_count += 1

        conn.commit()
        conn.close()
        flash(f"Attendance for {date_to_save} saved successfully ({saved_count} records updated)!", "success")
        return redirect(url_for('attendance', date=date_to_save, mess_type=mess_filter))

    # Query active students and their attendance status on selected date
    query = """
        SELECT s.student_id, s.full_name, s.mobile, s.college_name, s.mess_type, s.status as student_status,
               COALESCE(a.status, 'Unmarked') as attendance_status
        FROM students s
        LEFT JOIN attendance a ON s.student_id = a.student_id AND a.date = ?
        WHERE s.status IN ('Active', 'Expired')
    """
    params = [selected_date]

    if mess_filter in ('Veg', 'Non-Veg'):
        query += " AND s.mess_type = ?"
        params.append(mess_filter)

    if search:
        query += " AND (s.student_id LIKE ? OR s.full_name LIKE ?)"
        like_term = f"%{search}%"
        params.extend([like_term, like_term])

    query += " ORDER BY s.student_id ASC"

    students_attendance = conn.execute(query, params).fetchall()

    # Day summary
    summary_row = conn.execute("""
        SELECT 
            COUNT(*) as total_records,
            SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_count,
            SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent_count
        FROM students s
        JOIN attendance a ON s.student_id = a.student_id AND a.date = ?
        WHERE s.status = 'Active'
    """, (selected_date,)).fetchone()

    total_active = conn.execute("SELECT COUNT(*) as c FROM students WHERE status = 'Active'").fetchone()['c']

    conn.close()

    return render_template('attendance.html',
        selected_date=selected_date,
        mess_filter=mess_filter,
        search=search,
        students=students_attendance,
        total_active=total_active,
        summary=summary_row
    )

# ----------------- ABSENT-DAY ADJUSTMENTS ----------------- #

@app.route('/absent-approvals')
@login_required
def absent_approvals():
    database.update_all_mess_expiries()
    threshold = int(database.get_setting('absent_threshold_days', '3'))
    conn = database.get_db_connection()

    # 1. Detected eligible streaks currently awaiting submission / approval
    eligible_streaks = database.detect_all_eligible_absences(threshold=threshold)

    # 2. Adjustments currently in Pending or Approved/Rejected state in DB
    adjustments_history = conn.execute("""
        SELECT a.*, s.full_name as student_name, s.mess_type, s.mobile
        FROM absence_adjustments a
        JOIN students s ON a.student_id = s.student_id
        ORDER BY a.id DESC
    """).fetchall()

    conn.close()

    return render_template('absent_approvals.html',
        threshold=threshold,
        eligible_streaks=eligible_streaks,
        adjustments_history=adjustments_history
    )

@app.route('/absent-approvals/approve-detected', methods=['POST'])
@login_required
def approve_detected():
    student_id = request.form.get('student_id')
    plan_id = int(request.form.get('plan_id'))
    consecutive_count = int(request.form.get('consecutive_count'))
    absent_dates_json = request.form.get('absent_dates_json')
    original_expiry = request.form.get('original_expiry_date')
    proposed_expiry = request.form.get('proposed_expiry_date')
    admin_notes = request.form.get('admin_notes', 'Approved by administrator')

    conn = database.get_db_connection()
    cursor = conn.cursor()

    # Insert adjustment record as Approved
    today_str = date.today().isoformat()
    cursor.execute("""
        INSERT INTO absence_adjustments (
            student_id, plan_id, consecutive_days_count, absent_dates_json,
            credited_days, original_expiry_date, updated_expiry_date,
            status, requested_date, approved_date, admin_notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Approved', ?, ?, ?)
    """, (
        student_id, plan_id, consecutive_count, absent_dates_json,
        consecutive_count, original_expiry, proposed_expiry,
        today_str, today_str, admin_notes
    ))

    # Extend plan expiry date
    cursor.execute("""
        UPDATE mess_plans 
        SET current_expiry_date = ?, total_extension_days = total_extension_days + ?, status = 'Active'
        WHERE id = ?
    """, (proposed_expiry, consecutive_count, plan_id))

    # Update student status to Active if it was expired
    cursor.execute("""
        UPDATE students 
        SET status = 'Active', updated_at = CURRENT_TIMESTAMP
        WHERE student_id = ?
    """, (student_id,))

    conn.commit()
    conn.close()

    flash(f"Approved {consecutive_count}-day extension for {student_id}! Plan extended to {proposed_expiry}.", "success")
    return redirect(url_for('absent_approvals'))

@app.route('/absent-approvals/reject-adjustment/<int:adj_id>', methods=['POST'])
@login_required
def reject_adjustment(adj_id):
    reason = request.form.get('reason', 'Rejected by administrator')
    success, msg = database.reject_absence_adjustment(adj_id, reason)
    if success:
        flash(msg, "info")
    else:
        flash(msg, "danger")
    return redirect(url_for('absent_approvals'))

# ----------------- PAYMENTS MANAGEMENT ----------------- #

@app.route('/payments', methods=['GET', 'POST'])
@login_required
def payments():
    conn = database.get_db_connection()
    search = request.args.get('search', '').strip()
    method_filter = request.args.get('method', 'all')
    date_filter = request.args.get('date', '')

    query = """
        SELECT p.*, s.full_name as student_name, s.mobile, s.mess_type,
               pl.total_fee,
               (SELECT SUM(amount) FROM payments WHERE student_id = p.student_id) as total_paid_student
        FROM payments p
        JOIN students s ON p.student_id = s.student_id
        LEFT JOIN mess_plans pl ON p.plan_id = pl.id
        WHERE 1=1
    """
    params = []

    if search:
        query += " AND (p.receipt_no LIKE ? OR p.student_id LIKE ? OR s.full_name LIKE ?)"
        like_term = f"%{search}%"
        params.extend([like_term, like_term, like_term])

    if method_filter in ('Cash', 'UPI', 'Credit/Debit Card', 'Net Banking'):
        query += " AND p.payment_method = ?"
        params.append(method_filter)

    if date_filter:
        query += " AND p.payment_date = ?"
        params.append(date_filter)

    query += " ORDER BY p.payment_date DESC, p.id DESC"

    payments_list = conn.execute(query, params).fetchall()

    # Overall financial summary
    total_fee_all = conn.execute("SELECT COALESCE(SUM(total_fee), 0) as s FROM mess_plans").fetchone()['s']
    total_collected_all = conn.execute("SELECT COALESCE(SUM(amount), 0) as s FROM payments").fetchone()['s']
    outstanding_balance = max(0.0, total_fee_all - total_collected_all)

    today_str = date.today().isoformat()
    today_collected = conn.execute("SELECT COALESCE(SUM(amount), 0) as s FROM payments WHERE payment_date = ?", (today_str,)).fetchone()['s']

    # Active students for Record Payment modal
    active_students = conn.execute("""
        SELECT s.student_id, s.full_name, s.mess_type,
               p.id as plan_id, p.total_fee,
               COALESCE((SELECT SUM(amount) FROM payments WHERE student_id = s.student_id), 0) as paid,
               (p.total_fee - COALESCE((SELECT SUM(amount) FROM payments WHERE student_id = s.student_id), 0)) as balance
        FROM students s
        JOIN mess_plans p ON s.student_id = p.student_id AND p.is_current = 1
        ORDER BY s.full_name ASC
    """).fetchall()

    conn.close()

    return render_template('payments.html',
        payments=payments_list,
        total_collected=total_collected_all,
        outstanding_balance=outstanding_balance,
        today_collected=today_collected,
        search=search,
        method_filter=method_filter,
        date_filter=date_filter,
        active_students=active_students
    )

@app.route('/payments/record', methods=['POST'])
@login_required
def record_payment():
    student_id = request.form.get('student_id', '').strip()
    payment_date_str = request.form.get('payment_date', '').strip() or date.today().isoformat()
    payment_method = request.form.get('payment_method', 'Cash')
    notes = request.form.get('notes', 'Mess fee installment')

    try:
        amount = float(request.form.get('amount', 0))
    except ValueError:
        flash("Invalid payment amount entered.", "danger")
        return redirect(url_for('payments'))

    if amount <= 0:
        flash("Payment amount must be greater than zero.", "danger")
        return redirect(url_for('payments'))

    conn = database.get_db_connection()
    # Check student
    student = conn.execute("SELECT * FROM students WHERE student_id = ?", (student_id,)).fetchone()
    if not student:
        flash(f"Student ID {student_id} not found.", "danger")
        conn.close()
        return redirect(url_for('payments'))

    current_plan = conn.execute("SELECT * FROM mess_plans WHERE student_id = ? AND is_current = 1", (student_id,)).fetchone()
    plan_id = current_plan['id'] if current_plan else None

    # Calculate current balance
    total_fee = current_plan['total_fee'] if current_plan else 0
    total_paid_prev = conn.execute("SELECT COALESCE(SUM(amount), 0) as s FROM payments WHERE student_id = ?", (student_id,)).fetchone()['s']
    remaining_balance = total_fee - total_paid_prev

    if amount > remaining_balance and remaining_balance > 0:
        flash(f"Amount {amount} exceeds current outstanding balance of ₹{remaining_balance:.2f}!", "danger")
        conn.close()
        return redirect(url_for('payments'))

    receipt_no = database.generate_receipt_no()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO payments (receipt_no, student_id, plan_id, amount, payment_date, payment_method, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (receipt_no, student_id, plan_id, amount, payment_date_str, payment_method, notes))

    conn.commit()
    conn.close()

    flash(f"Payment of ₹{amount:.2f} recorded successfully for {student['full_name']}! Receipt: {receipt_no}", "success")
    return redirect(url_for('view_receipt', receipt_no=receipt_no))

@app.route('/receipt/<receipt_no>')
@login_required
def view_receipt(receipt_no):
    conn = database.get_db_connection()
    payment = conn.execute("""
        SELECT p.*, s.full_name as student_name, s.mobile, s.college_name, s.mess_type,
               pl.plan_duration_days, pl.start_date, pl.current_expiry_date, pl.total_fee,
               (SELECT SUM(amount) FROM payments WHERE student_id = p.student_id AND payment_date <= p.payment_date) as cumulative_paid
        FROM payments p
        JOIN students s ON p.student_id = s.student_id
        LEFT JOIN mess_plans pl ON p.plan_id = pl.id
        WHERE p.receipt_no = ?
    """, (receipt_no,)).fetchone()

    conn.close()

    if not payment:
        flash(f"Receipt {receipt_no} not found.", "danger")
        return redirect(url_for('payments'))

    total_fee = payment['total_fee'] or 0
    cum_paid = payment['cumulative_paid'] or payment['amount']
    remaining = max(0.0, total_fee - cum_paid)

    return render_template('receipt_print.html',
        payment=payment,
        remaining_balance=remaining
    )

# ----------------- EXPIRED MESS STUDENTS ----------------- #

@app.route('/expired-students')
@login_required
def expired_students():
    database.update_all_mess_expiries()
    conn = database.get_db_connection()
    today_str = date.today().isoformat()

    expired_list = conn.execute("""
        SELECT s.student_id, s.full_name, s.mobile, s.college_name, s.mess_type, s.status,
               p.start_date, p.current_expiry_date, p.total_fee,
               (julianday(?) - julianday(p.current_expiry_date)) as days_since_expiry,
               COALESCE((SELECT SUM(amount) FROM payments WHERE student_id = s.student_id), 0) as total_paid,
               (p.total_fee - COALESCE((SELECT SUM(amount) FROM payments WHERE student_id = s.student_id), 0)) as balance
        FROM students s
        JOIN mess_plans p ON s.student_id = p.student_id AND p.is_current = 1
        WHERE p.current_expiry_date < ? OR s.status = 'Expired'
        ORDER BY p.current_expiry_date DESC
    """, (today_str, today_str)).fetchall()

    conn.close()

    default_veg_fee = float(database.get_setting('veg_monthly_fee', '3200'))
    default_nonveg_fee = float(database.get_setting('nonveg_monthly_fee', '4200'))

    return render_template('expired_students.html',
        expired_students=expired_list,
        default_veg_fee=default_veg_fee,
        default_nonveg_fee=default_nonveg_fee
    )

# ----------------- REPORTS MODULE ----------------- #

@app.route('/reports')
@login_required
def reports():
    database.update_all_mess_expiries()
    report_type = request.args.get('report_type', 'daily_attendance')
    selected_date = request.args.get('date', date.today().isoformat())
    selected_month = request.args.get('month', datetime.now().strftime("%Y-%m"))
    mess_filter = request.args.get('mess_type', 'all')

    conn = database.get_db_connection()
    report_data = []
    summary_data = {}

    if report_type == 'daily_attendance':
        query = """
            SELECT a.date, s.student_id, s.full_name, s.mess_type, s.college_name, a.status
            FROM attendance a
            JOIN students s ON a.student_id = s.student_id
            WHERE a.date = ?
        """
        params = [selected_date]
        if mess_filter in ('Veg', 'Non-Veg'):
            query += " AND s.mess_type = ?"
            params.append(mess_filter)
        query += " ORDER BY s.student_id ASC"
        report_data = conn.execute(query, params).fetchall()

        present_c = sum(1 for r in report_data if r['status'] == 'Present')
        absent_c = sum(1 for r in report_data if r['status'] == 'Absent')
        summary_data = {
            "date": selected_date,
            "total_marked": len(report_data),
            "present_count": present_c,
            "absent_count": absent_c,
            "attendance_rate": f"{(present_c / len(report_data) * 100):.1f}%" if report_data else "0%"
        }

    elif report_type == 'monthly_attendance':
        # Filter attendance by YYYY-MM
        month_pattern = f"{selected_month}%"
        query = """
            SELECT s.student_id, s.full_name, s.mess_type, s.college_name,
                   COUNT(a.id) as total_marked,
                   SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_days,
                   SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent_days
            FROM students s
            LEFT JOIN attendance a ON s.student_id = a.student_id AND a.date LIKE ?
            WHERE s.status IN ('Active', 'Expired')
        """
        params = [month_pattern]
        if mess_filter in ('Veg', 'Non-Veg'):
            query += " AND s.mess_type = ?"
            params.append(mess_filter)
        query += " GROUP BY s.student_id ORDER BY s.student_id ASC"
        report_data = conn.execute(query, params).fetchall()
        summary_data = {"month": selected_month, "total_students": len(report_data)}

    elif report_type == 'payments_collection':
        query = """
            SELECT p.receipt_no, p.payment_date, s.student_id, s.full_name, s.mess_type,
                   p.amount, p.payment_method, p.notes
            FROM payments p
            JOIN students s ON p.student_id = s.student_id
            WHERE 1=1
        """
        params = []
        if selected_month:
            query += " AND p.payment_date LIKE ?"
            params.append(f"{selected_month}%")
        query += " ORDER BY p.payment_date DESC, p.id DESC"
        report_data = conn.execute(query, params).fetchall()
        total_coll = sum([r['amount'] for r in report_data])
        summary_data = {"month": selected_month, "total_records": len(report_data), "total_amount": total_coll}

    elif report_type == 'pending_fees':
        query = """
            SELECT s.student_id, s.full_name, s.mobile, s.mess_type, s.status,
                   p.total_fee,
                   COALESCE((SELECT SUM(amount) FROM payments WHERE student_id = s.student_id), 0) as paid,
                   (p.total_fee - COALESCE((SELECT SUM(amount) FROM payments WHERE student_id = s.student_id), 0)) as pending_amount
            FROM students s
            JOIN mess_plans p ON s.student_id = p.student_id AND p.is_current = 1
            WHERE (p.total_fee - COALESCE((SELECT SUM(amount) FROM payments WHERE student_id = s.student_id), 0)) > 0
            ORDER BY pending_amount DESC
        """
        report_data = conn.execute(query).fetchall()
        total_pending = sum([r['pending_amount'] for r in report_data])
        summary_data = {"students_with_dues": len(report_data), "total_pending": total_pending}

    elif report_type == 'expired_students':
        today_str = date.today().isoformat()
        query = """
            SELECT s.student_id, s.full_name, s.mobile, s.mess_type,
                   p.start_date, p.current_expiry_date,
                   (julianday(?) - julianday(p.current_expiry_date)) as days_expired,
                   (p.total_fee - COALESCE((SELECT SUM(amount) FROM payments WHERE student_id = s.student_id), 0)) as balance
            FROM students s
            JOIN mess_plans p ON s.student_id = p.student_id AND p.is_current = 1
            WHERE p.current_expiry_date < ? OR s.status = 'Expired'
            ORDER BY p.current_expiry_date DESC
        """
        report_data = conn.execute(query, (today_str, today_str)).fetchall()
        summary_data = {"total_expired": len(report_data)}

    elif report_type == 'absent_adjustments':
        query = """
            SELECT a.*, s.full_name as student_name, s.mess_type
            FROM absence_adjustments a
            JOIN students s ON a.student_id = s.student_id
            WHERE a.status = 'Approved'
            ORDER BY a.approved_date DESC, a.id DESC
        """
        report_data = conn.execute(query).fetchall()
        total_days_ext = sum([r['credited_days'] for r in report_data])
        summary_data = {"total_approved": len(report_data), "total_extension_days": total_days_ext}

    conn.close()

    return render_template('reports.html',
        report_type=report_type,
        selected_date=selected_date,
        selected_month=selected_month,
        mess_filter=mess_filter,
        report_data=report_data,
        summary=summary_data
    )

@app.route('/reports/export-csv')
@login_required
def export_csv():
    report_type = request.args.get('report_type', 'daily_attendance')
    selected_date = request.args.get('date', date.today().isoformat())
    selected_month = request.args.get('month', datetime.now().strftime("%Y-%m"))
    mess_filter = request.args.get('mess_type', 'all')

    conn = database.get_db_connection()
    output = io.StringIO()
    writer = csv.writer(output)

    filename = f"mess_report_{report_type}_{date.today().isoformat()}.csv"

    if report_type == 'daily_attendance':
        writer.writerow(["Date", "Student ID", "Full Name", "Mess Type", "College", "Attendance Status"])
        records = conn.execute("""
            SELECT a.date, s.student_id, s.full_name, s.mess_type, s.college_name, a.status
            FROM attendance a
            JOIN students s ON a.student_id = s.student_id
            WHERE a.date = ?
            ORDER BY s.student_id ASC
        """, (selected_date,)).fetchall()
        for r in records:
            writer.writerow([r['date'], r['student_id'], r['full_name'], r['mess_type'], r['college_name'], r['status']])

    elif report_type == 'monthly_attendance':
        writer.writerow(["Month", "Student ID", "Full Name", "Mess Type", "College", "Total Marked", "Present Days", "Absent Days", "Attendance Rate"])
        records = conn.execute("""
            SELECT s.student_id, s.full_name, s.mess_type, s.college_name,
                   COUNT(a.id) as total_marked,
                   SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_days,
                   SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent_days
            FROM students s
            LEFT JOIN attendance a ON s.student_id = a.student_id AND a.date LIKE ?
            WHERE s.status IN ('Active', 'Expired')
            GROUP BY s.student_id ORDER BY s.student_id ASC
        """, (f"{selected_month}%",)).fetchall()
        for r in records:
            rate = f"{(r['present_days'] / r['total_marked'] * 100):.1f}%" if r['total_marked'] else "0%"
            writer.writerow([selected_month, r['student_id'], r['full_name'], r['mess_type'], r['college_name'], r['total_marked'], r['present_days'], r['absent_days'], rate])

    elif report_type == 'payments_collection':
        writer.writerow(["Receipt No", "Payment Date", "Student ID", "Full Name", "Mess Type", "Amount", "Method", "Notes"])
        records = conn.execute("""
            SELECT p.receipt_no, p.payment_date, s.student_id, s.full_name, s.mess_type, p.amount, p.payment_method, p.notes
            FROM payments p
            JOIN students s ON p.student_id = s.student_id
            ORDER BY p.payment_date DESC
        """).fetchall()
        for r in records:
            writer.writerow([r['receipt_no'], r['payment_date'], r['student_id'], r['full_name'], r['mess_type'], r['amount'], r['payment_method'], r['notes']])

    elif report_type == 'pending_fees':
        writer.writerow(["Student ID", "Full Name", "Mobile", "Mess Type", "Status", "Total Fee", "Paid Amount", "Pending Balance"])
        records = conn.execute("""
            SELECT s.student_id, s.full_name, s.mobile, s.mess_type, s.status, p.total_fee,
                   COALESCE((SELECT SUM(amount) FROM payments WHERE student_id = s.student_id), 0) as paid,
                   (p.total_fee - COALESCE((SELECT SUM(amount) FROM payments WHERE student_id = s.student_id), 0)) as pending_amount
            FROM students s
            JOIN mess_plans p ON s.student_id = p.student_id AND p.is_current = 1
            WHERE (p.total_fee - COALESCE((SELECT SUM(amount) FROM payments WHERE student_id = s.student_id), 0)) > 0
            ORDER BY pending_amount DESC
        """).fetchall()
        for r in records:
            writer.writerow([r['student_id'], r['full_name'], r['mobile'], r['mess_type'], r['status'], r['total_fee'], r['paid'], r['pending_amount']])

    elif report_type == 'expired_students':
        today_str = date.today().isoformat()
        writer.writerow(["Student ID", "Full Name", "Mobile", "Mess Type", "Start Date", "Expiry Date", "Days Expired", "Pending Balance"])
        records = conn.execute("""
            SELECT s.student_id, s.full_name, s.mobile, s.mess_type, p.start_date, p.current_expiry_date,
                   (julianday(?) - julianday(p.current_expiry_date)) as days_expired,
                   (p.total_fee - COALESCE((SELECT SUM(amount) FROM payments WHERE student_id = s.student_id), 0)) as balance
            FROM students s
            JOIN mess_plans p ON s.student_id = p.student_id AND p.is_current = 1
            WHERE p.current_expiry_date < ? OR s.status = 'Expired'
            ORDER BY p.current_expiry_date DESC
        """, (today_str, today_str)).fetchall()
        for r in records:
            writer.writerow([r['student_id'], r['full_name'], r['mobile'], r['mess_type'], r['start_date'], r['current_expiry_date'], int(r['days_expired'] or 0), r['balance']])

    conn.close()

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-type"] = "text/csv; charset=utf-8"
    return response

# ----------------- SETTINGS & CONFIGURATION ----------------- #

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'save_mess_settings':
            database.update_setting('mess_name', request.form.get('mess_name', '').strip())
            database.update_setting('college_name', request.form.get('college_name', '').strip())
            database.update_setting('absent_threshold_days', request.form.get('absent_threshold_days', '3').strip())
            database.update_setting('veg_monthly_fee', request.form.get('veg_monthly_fee', '3200').strip())
            database.update_setting('nonveg_monthly_fee', request.form.get('nonveg_monthly_fee', '4200').strip())
            database.update_setting('currency_symbol', request.form.get('currency_symbol', '₹').strip())
            database.update_setting('contact_phone', request.form.get('contact_phone', '').strip())
            database.update_setting('contact_email', request.form.get('contact_email', '').strip())
            flash("System settings saved successfully!", "success")

        elif action == 'change_password':
            current_pw = request.form.get('current_password', '')
            new_pw = request.form.get('new_password', '')
            confirm_pw = request.form.get('confirm_password', '')

            if not new_pw or new_pw != confirm_pw:
                flash("New passwords do not match or are empty.", "danger")
            else:
                conn = database.get_db_connection()
                user = conn.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
                if user and check_password_hash(user['password_hash'], current_pw):
                    hashed = generate_password_hash(new_pw)
                    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hashed, session['user_id']))
                    conn.commit()
                    flash("Administrator password updated successfully!", "success")
                else:
                    flash("Incorrect current password.", "danger")
                conn.close()

        elif action == 'reset_sample_data':
            # Reset database with sample records
            conn = database.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM attendance")
            cursor.execute("DELETE FROM absence_adjustments")
            cursor.execute("DELETE FROM payments")
            cursor.execute("DELETE FROM mess_plans")
            cursor.execute("DELETE FROM students")
            conn.commit()
            conn.close()
            database.init_db(seed_sample=True)
            database.update_all_mess_expiries()
            flash("Sample data reloaded successfully!", "success")

        return redirect(url_for('settings'))

    conn = database.get_db_connection()
    all_settings = {row['key']: row['value'] for row in conn.execute("SELECT key, value FROM settings").fetchall()}
    conn.close()

    return render_template('settings.html', settings=all_settings)

# ----------------- REST APIS (FOR AJAX / MODALS) ----------------- #

@app.route('/api/student/<student_id>')
@login_required
def api_get_student(student_id):
    conn = database.get_db_connection()
    student = conn.execute("""
        SELECT s.*, p.id as plan_id, p.total_fee, p.plan_duration_days, p.current_expiry_date,
               COALESCE((SELECT SUM(amount) FROM payments WHERE student_id = s.student_id), 0) as paid,
               (p.total_fee - COALESCE((SELECT SUM(amount) FROM payments WHERE student_id = s.student_id), 0)) as balance
        FROM students s
        LEFT JOIN mess_plans p ON s.student_id = p.student_id AND p.is_current = 1
        WHERE s.student_id = ?
    """, (student_id,)).fetchone()
    conn.close()

    if not student:
        return jsonify({"error": "Student not found"}), 404

    return jsonify(dict(student))

@app.route('/api/attendance/quick-mark', methods=['POST'])
@login_required
def api_quick_mark_attendance():
    data = request.get_json()
    student_id = data.get('student_id')
    att_date = data.get('date', date.today().isoformat())
    status = data.get('status', 'Present')

    conn = database.get_db_connection()
    conn.execute("""
        INSERT INTO attendance (student_id, date, status, marked_by)
        VALUES (?, ?, ?, 'admin')
        ON CONFLICT(student_id, date) DO UPDATE SET 
            status = excluded.status,
            created_at = CURRENT_TIMESTAMP
    """, (student_id, att_date, status))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "student_id": student_id, "date": att_date, "status": status})

if __name__ == '__main__':
    database.init_db(seed_sample=False)
    database.update_all_mess_expiries()
    print("[SERVER] College Mess Management System running on http://127.0.0.1:5000")
    app.run(host='127.0.0.1', port=5000, debug=True)
