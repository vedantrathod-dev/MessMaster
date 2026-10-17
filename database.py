import sqlite3
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash

import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, 'instance', 'mess.db')

def get_db_path():
    # If running on Vercel or read-only filesystem
    if os.environ.get('VERCEL') or not os.access(BASE_DIR, os.W_OK):
        tmp_db = '/tmp/mess.db'
        if not os.path.exists(tmp_db):
            os.makedirs('/tmp', exist_ok=True)
            if os.path.exists(DEFAULT_DB_PATH):
                try:
                    shutil.copy2(DEFAULT_DB_PATH, tmp_db)
                except Exception as e:
                    print(f"Notice: copying DB to /tmp failed, will init fresh: {e}")
        return tmp_db
    return DEFAULT_DB_PATH

def get_db_connection():
    db_file = get_db_path()
    try:
        os.makedirs(os.path.dirname(db_file), exist_ok=True)
    except OSError:
        pass
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(seed_sample=False):
    db_file = get_db_path()
    try:
        os.makedirs(os.path.dirname(db_file), exist_ok=True)
    except OSError:
        pass
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Users table (for admin authentication)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT DEFAULT 'admin',
            student_id TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Dynamic migrations for existing databases
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN student_id TEXT;")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN email TEXT;")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE students ADD COLUMN meal_preference TEXT DEFAULT 'Both';")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE students ADD COLUMN email TEXT;")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE attendance ADD COLUMN meal_session TEXT DEFAULT 'All';")
    except Exception:
        pass

    # Migrate attendance table to UNIQUE(student_id, date, meal_session) if old UNIQUE(student_id, date) exists
    try:
        att_sql_row = cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='attendance'").fetchone()
        if att_sql_row and "UNIQUE(student_id, date)" in att_sql_row[0]:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS attendance_migrated (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    date DATE NOT NULL,
                    meal_session TEXT DEFAULT 'All',
                    status TEXT NOT NULL CHECK(status IN ('Present', 'Absent')),
                    marked_by TEXT DEFAULT 'admin',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(student_id, date, meal_session),
                    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
                );
            """)
            cursor.execute("""
                INSERT OR IGNORE INTO attendance_migrated (id, student_id, date, meal_session, status, marked_by, created_at)
                SELECT id, student_id, date, COALESCE(meal_session, 'All'), status, marked_by, created_at FROM attendance;
            """)
            cursor.execute("DROP TABLE attendance;")
            cursor.execute("ALTER TABLE attendance_migrated RENAME TO attendance;")
    except Exception as e:
        print(f"Attendance migration notice: {e}")

    # 2. Settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT NOT NULL,
            description TEXT
        );
    """)

    # 3. Students table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            mobile TEXT UNIQUE NOT NULL,
            email TEXT,
            college_name TEXT NOT NULL,
            mess_type TEXT NOT NULL CHECK(mess_type IN ('Veg', 'Non-Veg')),
            meal_preference TEXT NOT NULL DEFAULT 'Both' CHECK(meal_preference IN ('Both', 'Lunch', 'Dinner')),
            status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active', 'Expired', 'Deactivated')),
            admission_date DATE NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 4. Mess Plans table (tracks active and historical plans for renewals)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mess_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            plan_duration_days INTEGER NOT NULL,
            start_date DATE NOT NULL,
            original_expiry_date DATE NOT NULL,
            current_expiry_date DATE NOT NULL,
            total_extension_days INTEGER DEFAULT 0,
            mess_type TEXT NOT NULL CHECK(mess_type IN ('Veg', 'Non-Veg')),
            total_fee REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active', 'Expired', 'Renewed')),
            is_current INTEGER NOT NULL DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
        );
    """)

    # 5. Payments table (each transaction recorded separately)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_no TEXT UNIQUE NOT NULL,
            student_id TEXT NOT NULL,
            plan_id INTEGER,
            amount REAL NOT NULL,
            payment_date DATE NOT NULL,
            payment_method TEXT NOT NULL CHECK(payment_method IN ('Cash', 'UPI', 'Credit/Debit Card', 'Net Banking')),
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
            FOREIGN KEY (plan_id) REFERENCES mess_plans(id) ON DELETE SET NULL
        );
    """)

    # 6. Attendance table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            date DATE NOT NULL,
            meal_session TEXT DEFAULT 'All',
            status TEXT NOT NULL CHECK(status IN ('Present', 'Absent')),
            marked_by TEXT DEFAULT 'admin',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_id, date, meal_session),
            FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
        );
    """)

    # 7. Absence Adjustments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS absence_adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            plan_id INTEGER NOT NULL,
            consecutive_days_count INTEGER NOT NULL,
            absent_dates_json TEXT NOT NULL,
            credited_days INTEGER NOT NULL,
            original_expiry_date DATE NOT NULL,
            updated_expiry_date DATE NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'Approved', 'Rejected')),
            requested_date DATE NOT NULL,
            approved_date DATE,
            admin_notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
            FOREIGN KEY (plan_id) REFERENCES mess_plans(id) ON DELETE CASCADE
        );
    """)

    # Default admin user: admin / admin123
    admin_exists = cursor.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
    if not admin_exists:
        hashed = generate_password_hash("admin123")
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, role)
            VALUES (?, ?, ?, ?)
        """, ('admin', hashed, 'Mess Chief Administrator', 'admin'))

    # Default student demo user: student1 / password123 (linked to first student)
    first_stu = cursor.execute("SELECT student_id, full_name FROM students LIMIT 1").fetchone()
    if first_stu:
        stu_exists = cursor.execute("SELECT id FROM users WHERE username = 'student1'").fetchone()
        if not stu_exists:
            hashed_stu = generate_password_hash("password123")
            cursor.execute("""
                INSERT INTO users (username, password_hash, full_name, role, student_id)
                VALUES (?, ?, ?, 'student', ?)
            """, ('student1', hashed_stu, first_stu['full_name'], first_stu['student_id']))

    # Default system settings
    default_settings = [
        ('mess_name', 'Campus Royal Mess & Dining Hall', 'Name of the mess facility'),
        ('college_name', 'Engineering & Technology Campus', 'Affiliated college/institution'),
        ('absent_threshold_days', '3', 'Minimum consecutive absent days required for extension approval (e.g. 3 or 4)'),
        ('veg_monthly_fee', '3200', 'Standard 30-day fee for Pure Veg Mess (Both Meals)'),
        ('nonveg_monthly_fee', '4200', 'Standard 30-day fee for Non-Veg Mess (Both Meals)'),
        ('veg_1time_monthly_fee', '1920', 'Standard 30-day fee for 1-Time Pure Veg Mess (Morning or Night)'),
        ('nonveg_1time_monthly_fee', '2520', 'Standard 30-day fee for 1-Time Non-Veg Mess (Morning or Night)'),
        ('currency_symbol', '₹', 'Currency symbol for monetary displays'),
        ('contact_phone', '+91 98765 43210', 'Mess admin contact phone number'),
        ('contact_email', 'mess-admin@campus.edu', 'Mess admin official email')
    ]

    for key, val, desc in default_settings:
        exists = cursor.execute("SELECT id FROM settings WHERE key = ?", (key,)).fetchone()
        if not exists:
            cursor.execute("INSERT INTO settings (key, value, description) VALUES (?, ?, ?)", (key, val, desc))

    conn.commit()

    if seed_sample:
        seed_sample_data(conn)

    conn.close()

def get_setting(key, default_value=''):
    conn = get_db_connection()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row['value'] if row else default_value

def update_setting(key, value):
    conn = get_db_connection()
    conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, str(value)))
    conn.commit()
    conn.close()

def generate_student_id():
    conn = get_db_connection()
    current_year = datetime.now().year
    prefix = f"STU{current_year}"
    row = conn.execute("SELECT student_id FROM students WHERE student_id LIKE ? ORDER BY student_id DESC LIMIT 1", (f"{prefix}%",)).fetchone()
    conn.close()
    if row and row['student_id']:
        try:
            last_num = int(row['student_id'].replace(prefix, ''))
            return f"{prefix}{last_num + 1:04d}"
        except ValueError:
            pass
    return f"{prefix}0001"

def generate_receipt_no():
    today_str = datetime.now().strftime("%Y%m%d")
    prefix = f"REC-{today_str}-"
    conn = get_db_connection()
    row = conn.execute("SELECT receipt_no FROM payments WHERE receipt_no LIKE ? ORDER BY receipt_no DESC LIMIT 1", (f"{prefix}%",)).fetchone()
    conn.close()
    if row and row['receipt_no']:
        try:
            last_num = int(row['receipt_no'].split('-')[-1])
            return f"{prefix}{last_num + 1:04d}"
        except (ValueError, IndexError):
            pass
    return f"{prefix}0001"

def update_all_mess_expiries():
    """
    Evaluates all active mess plans against today's date.
    - If current_expiry_date < today: mark plan & student as Expired.
    - If current_expiry_date >= today: ensure status is Active if not deactivated.
    """
    today_str = date.today().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()

    # Expire overdue plans
    cursor.execute("""
        UPDATE mess_plans 
        SET status = 'Expired' 
        WHERE is_current = 1 AND current_expiry_date < ? AND status = 'Active'
    """, (today_str,))

    # Update student status to Expired if current plan is expired and student is not deactivated
    cursor.execute("""
        UPDATE students
        SET status = 'Expired', updated_at = CURRENT_TIMESTAMP
        WHERE status = 'Active' AND student_id IN (
            SELECT student_id FROM mess_plans 
            WHERE is_current = 1 AND current_expiry_date < ?
        )
    """, (today_str,))

    # Reactivate students whose plan was extended or renewed into valid range
    cursor.execute("""
        UPDATE students
        SET status = 'Active', updated_at = CURRENT_TIMESTAMP
        WHERE status = 'Expired' AND student_id IN (
            SELECT student_id FROM mess_plans 
            WHERE is_current = 1 AND current_expiry_date >= ?
        )
    """, (today_str,))

    cursor.execute("""
        UPDATE mess_plans 
        SET status = 'Active' 
        WHERE is_current = 1 AND current_expiry_date >= ? AND status = 'Expired'
    """, (today_str,))

    conn.commit()
    conn.close()

def detect_consecutive_absences_for_student(student_id, threshold=None):
    """
    Checks if a student has eligible consecutive absent days that qualify for adjustment.
    Threshold defaults to setting (3 or 4).
    """
    if threshold is None:
        threshold = int(get_setting('absent_threshold_days', '3'))

    conn = get_db_connection()
    student = conn.execute("SELECT * FROM students WHERE student_id = ?", (student_id,)).fetchone()
    if not student:
        conn.close()
        return []

    current_plan = conn.execute("""
        SELECT * FROM mess_plans 
        WHERE student_id = ? AND is_current = 1 
        ORDER BY id DESC LIMIT 1
    """, (student_id,)).fetchone()

    if not current_plan:
        conn.close()
        return []

    # Get all already processed (pending or approved) dates for this student
    existing_adjustments = conn.execute("""
        SELECT absent_dates_json FROM absence_adjustments 
        WHERE student_id = ? AND status IN ('Pending', 'Approved')
    """, (student_id,)).fetchall()

    processed_dates = set()
    for adj in existing_adjustments:
        try:
            d_list = json.loads(adj['absent_dates_json'])
            processed_dates.update(d_list)
        except Exception:
            pass

    # Fetch attendance records within active plan start and today (or expiry date, whichever is earlier)
    today_str = date.today().isoformat()
    plan_start = current_plan['start_date']
    end_bound = min(today_str, current_plan['current_expiry_date'])

    records = conn.execute("""
        SELECT date, status FROM attendance 
        WHERE student_id = ? AND date >= ? AND date <= ?
        ORDER BY date ASC
    """, (student_id, plan_start, end_bound)).fetchall()

    conn.close()

    eligible_streaks = []
    current_streak = []

    for r in records:
        r_date = r['date']
        if r['status'] == 'Absent' and r_date not in processed_dates:
            # Check if contiguous with previous
            if not current_streak:
                current_streak.append(r_date)
            else:
                prev_date = datetime.strptime(current_streak[-1], "%Y-%m-%d").date()
                curr_date = datetime.strptime(r_date, "%Y-%m-%d").date()
                if (curr_date - prev_date).days == 1:
                    current_streak.append(r_date)
                else:
                    if len(current_streak) >= threshold:
                        eligible_streaks.append(list(current_streak))
                    current_streak = [r_date]
        else:
            if len(current_streak) >= threshold:
                eligible_streaks.append(list(current_streak))
            current_streak = []

    if len(current_streak) >= threshold:
        eligible_streaks.append(list(current_streak))

    results = []
    for streak in eligible_streaks:
        credited_days = len(streak)
        curr_exp = datetime.strptime(current_plan['current_expiry_date'], "%Y-%m-%d").date()
        new_exp = (curr_exp + timedelta(days=credited_days)).isoformat()
        results.append({
            'student_id': student['student_id'],
            'student_name': student['full_name'],
            'mess_type': student['mess_type'],
            'plan_id': current_plan['id'],
            'consecutive_count': credited_days,
            'absent_dates': streak,
            'absent_dates_str': f"{streak[0]} to {streak[-1]} ({credited_days} days)",
            'original_expiry_date': current_plan['current_expiry_date'],
            'proposed_expiry_date': new_exp,
            'credited_days': credited_days
        })

    return results

def detect_all_eligible_absences(threshold=None):
    """
    Finds all active students who currently have qualifying consecutive absences
    that have not yet been submitted or approved.
    """
    if threshold is None:
        threshold = int(get_setting('absent_threshold_days', '3'))

    conn = get_db_connection()
    students = conn.execute("SELECT student_id FROM students WHERE status IN ('Active', 'Expired')").fetchall()
    conn.close()

    all_eligible = []
    for s in students:
        streaks = detect_consecutive_absences_for_student(s['student_id'], threshold)
        all_eligible.extend(streaks)

    return all_eligible

def approve_absence_adjustment(adjustment_id, admin_notes="Approved by Administrator"):
    conn = get_db_connection()
    cursor = conn.cursor()

    adj = cursor.execute("SELECT * FROM absence_adjustments WHERE id = ?", (adjustment_id,)).fetchone()
    if not adj:
        conn.close()
        return False, "Adjustment record not found."

    if adj['status'] == 'Approved':
        conn.close()
        return False, "This adjustment is already approved."

    student_id = adj['student_id']
    plan_id = adj['plan_id']
    credited_days = adj['credited_days']

    plan = cursor.execute("SELECT * FROM mess_plans WHERE id = ?", (plan_id,)).fetchone()
    if not plan:
        conn.close()
        return False, "Associated mess plan not found."

    # Calculate new expiry
    curr_expiry = datetime.strptime(plan['current_expiry_date'], "%Y-%m-%d").date()
    new_expiry = curr_expiry + timedelta(days=credited_days)
    new_expiry_str = new_expiry.isoformat()

    # Update plan
    cursor.execute("""
        UPDATE mess_plans 
        SET current_expiry_date = ?, total_extension_days = total_extension_days + ?, status = 'Active'
        WHERE id = ?
    """, (new_expiry_str, credited_days, plan_id))

    # Update adjustment record
    today_str = date.today().isoformat()
    cursor.execute("""
        UPDATE absence_adjustments
        SET status = 'Approved', approved_date = ?, updated_expiry_date = ?, admin_notes = ?
        WHERE id = ?
    """, (today_str, new_expiry_str, admin_notes, adjustment_id))

    # If student was Expired, re-evaluate status
    cursor.execute("""
        UPDATE students
        SET status = 'Active', updated_at = CURRENT_TIMESTAMP
        WHERE student_id = ?
    """, (student_id,))

    conn.commit()
    conn.close()
    return True, f"Successfully approved {credited_days}-day extension! New expiry date: {new_expiry_str}"

def reject_absence_adjustment(adjustment_id, reason="Rejected by Administrator"):
    conn = get_db_connection()
    cursor = conn.cursor()
    adj = cursor.execute("SELECT * FROM absence_adjustments WHERE id = ?", (adjustment_id,)).fetchone()
    if not adj:
        conn.close()
        return False, "Adjustment record not found."

    cursor.execute("""
        UPDATE absence_adjustments
        SET status = 'Rejected', admin_notes = ?
        WHERE id = ?
    """, (reason, adjustment_id))
    conn.commit()
    conn.close()
    return True, "Adjustment request rejected."

def seed_sample_data(conn):
    cursor = conn.cursor()
    # Check if students already exist
    existing = cursor.execute("SELECT COUNT(*) as count FROM students").fetchone()['count']
    if existing > 0:
        return

    today = date.today()
    students_data = [
        # 1. Active Veg student, paid in full
        {
            "id": "STU20260001", "name": "Aarav Sharma", "mobile": "9812345671", "college": "Govt Engineering College",
            "mess_type": "Veg", "duration": 30, "offset_start": -12, "fee": 3200, "paid": 3200, "method": "UPI"
        },
        # 2. Active Non-Veg student, partial payment
        {
            "id": "STU20260002", "name": "Rohan Patel", "mobile": "9812345672", "college": "Institute of Technology",
            "mess_type": "Non-Veg", "duration": 30, "offset_start": -10, "fee": 4200, "paid": 2500, "method": "Cash"
        },
        # 3. Active Veg student, pending payment (paid 0)
        {
            "id": "STU20260003", "name": "Priya Nair", "mobile": "9812345673", "college": "City Polytechnic",
            "mess_type": "Veg", "duration": 30, "offset_start": -5, "fee": 3200, "paid": 0, "method": "Cash"
        },
        # 4. Expiring in 2 days (Warning state!) Veg
        {
            "id": "STU20260004", "name": "Vikram Singh", "mobile": "9812345674", "college": "Govt Engineering College",
            "mess_type": "Veg", "duration": 30, "offset_start": -28, "fee": 3200, "paid": 3200, "method": "UPI"
        },
        # 5. Expiring in 1 day (Warning state!) Non-Veg
        {
            "id": "STU20260005", "name": "Ananya Joshi", "mobile": "9812345675", "college": "National Institute of Science",
            "mess_type": "Non-Veg", "duration": 30, "offset_start": -29, "fee": 4200, "paid": 4200, "method": "Net Banking"
        },
        # 6. Already Expired student (expired 3 days ago)
        {
            "id": "STU20260006", "name": "Kabir Verma", "mobile": "9812345676", "college": "Institute of Technology",
            "mess_type": "Veg", "duration": 30, "offset_start": -35, "fee": 3200, "paid": 2000, "method": "Cash"
        },
        # 7. Already Expired student (expired 5 days ago)
        {
            "id": "STU20260007", "name": "Sneha Roy", "mobile": "9812345677", "college": "City Polytechnic",
            "mess_type": "Non-Veg", "duration": 30, "offset_start": -40, "fee": 4200, "paid": 4200, "method": "UPI"
        },
        # 8. Active student with 4 consecutive absent days (qualifies for absent adjustment)
        {
            "id": "STU20260008", "name": "Aditya Rao", "mobile": "9812345678", "college": "Govt Engineering College",
            "mess_type": "Non-Veg", "duration": 30, "offset_start": -14, "fee": 4200, "paid": 4200, "method": "UPI"
        },
        # 9. Active Veg student with 3 consecutive absent days
        {
            "id": "STU20260009", "name": "Divya Krishnan", "mobile": "9812345679", "college": "Apex Institute",
            "mess_type": "Veg", "duration": 60, "offset_start": -20, "fee": 6400, "paid": 5000, "method": "Credit/Debit Card"
        },
        # 10. Active Non-Veg student with 90 days plan
        {
            "id": "STU20260010", "name": "Manish Gupta", "mobile": "9812345680", "college": "Govt Engineering College",
            "mess_type": "Non-Veg", "duration": 90, "offset_start": -15, "fee": 12000, "paid": 12000, "method": "Net Banking"
        },
        # 11. Active Veg student, paid full
        {
            "id": "STU20260011", "name": "Tanvi Deshmukh", "mobile": "9812345681", "college": "National Institute of Science",
            "mess_type": "Veg", "duration": 30, "offset_start": -8, "fee": 3200, "paid": 3200, "method": "UPI"
        },
        # 12. Active Non-Veg student, partial
        {
            "id": "STU20260012", "name": "Karan Malhotra", "mobile": "9812345682", "college": "Institute of Technology",
            "mess_type": "Non-Veg", "duration": 30, "offset_start": -6, "fee": 4200, "paid": 2000, "method": "Cash"
        }
    ]

    receipt_counter = 1

    for s in students_data:
        adm_date = today + timedelta(days=s['offset_start'])
        start_date = adm_date
        orig_expiry = start_date + timedelta(days=s['duration'])
        curr_expiry = orig_expiry
        
        is_expired = curr_expiry < today
        status = 'Expired' if is_expired else 'Active'
        plan_status = 'Expired' if is_expired else 'Active'

        cursor.execute("""
            INSERT INTO students (student_id, full_name, mobile, college_name, mess_type, status, admission_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (s['id'], s['name'], s['mobile'], s['college'], s['mess_type'], status, adm_date.isoformat()))

        cursor.execute("""
            INSERT INTO mess_plans (student_id, plan_duration_days, start_date, original_expiry_date, current_expiry_date, total_extension_days, mess_type, total_fee, status, is_current)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, 1)
        """, (s['id'], s['duration'], start_date.isoformat(), orig_expiry.isoformat(), curr_expiry.isoformat(), s['mess_type'], s['fee'], plan_status))

        plan_id = cursor.lastrowid

        if s['paid'] > 0:
            rec_no = f"REC-{adm_date.strftime('%Y%m%d')}-{receipt_counter:04d}"
            receipt_counter += 1
            cursor.execute("""
                INSERT INTO payments (receipt_no, student_id, plan_id, amount, payment_date, payment_method, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (rec_no, s['id'], plan_id, s['paid'], adm_date.isoformat(), s['method'], 'Admission fee payment'))

    conn.commit()

    # Now generate realistic attendance for the past 14 days up to today
    all_students = cursor.execute("SELECT student_id, admission_date, status FROM students").fetchall()
    
    for day_offset in range(14, -1, -1):
        att_date = today - timedelta(days=day_offset)
        att_date_str = att_date.isoformat()

        for st in all_students:
            s_id = st['student_id']
            adm_dt = datetime.strptime(st['admission_date'], "%Y-%m-%d").date()
            if att_date < adm_dt:
                continue

            # Special cases for consecutive absences
            if s_id == 'STU20260008':
                # Absent for 4 days: 4, 3, 2, 1 days ago
                if day_offset in (1, 2, 3, 4):
                    att_status = 'Absent'
                else:
                    att_status = 'Present'
            elif s_id == 'STU20260009':
                # Absent for 3 days: 3, 2, 1 days ago
                if day_offset in (1, 2, 3):
                    att_status = 'Absent'
                else:
                    att_status = 'Present'
            elif s_id == 'STU20260003' and day_offset in (0, 1):
                att_status = 'Absent'
            elif s_id == 'STU20260006':
                att_status = 'Absent' if day_offset < 8 else 'Present'
            else:
                # Mostly present
                att_status = 'Present' if (hash(s_id + att_date_str) % 7 != 0) else 'Absent'

            cursor.execute("""
                INSERT OR IGNORE INTO attendance (student_id, date, status, marked_by)
                VALUES (?, ?, ?, 'admin')
            """, (s_id, att_date_str, att_status))

    # Add one sample already-approved absence adjustment for STU20260001 from earlier
    orig_exp_stu1 = today + timedelta(days=-12 + 30)
    cursor.execute("""
        INSERT INTO absence_adjustments (
            student_id, plan_id, consecutive_days_count, absent_dates_json, credited_days,
            original_expiry_date, updated_expiry_date, status, requested_date, approved_date, admin_notes
        ) VALUES (
            'STU20260001', 1, 3, ?, 3, ?, ?, 'Approved', ?, ?, 'Approved medical leave extension'
        )
    """, (
        json.dumps([(today - timedelta(days=10)).isoformat(), (today - timedelta(days=9)).isoformat(), (today - timedelta(days=8)).isoformat()]),
        orig_exp_stu1.isoformat(),
        (orig_exp_stu1 + timedelta(days=3)).isoformat(),
        (today - timedelta(days=7)).isoformat(),
        (today - timedelta(days=7)).isoformat()
    ))

    # Update STU20260001 plan with the 3 days extension
    cursor.execute("""
        UPDATE mess_plans 
        SET total_extension_days = 3, current_expiry_date = ? 
        WHERE id = 1
    """, ((orig_exp_stu1 + timedelta(days=3)).isoformat(),))

    conn.commit()
    print("Database initialized and sample data seeded successfully!")

def get_student_dashboard_data(student_id):
    update_all_mess_expiries()
    conn = get_db_connection()
    today_str = date.today().isoformat()

    student = conn.execute("SELECT * FROM students WHERE student_id = ?", (student_id,)).fetchone()
    if not student:
        conn.close()
        return None

    # Current active mess plan
    current_plan = conn.execute("""
        SELECT *, (julianday(current_expiry_date) - julianday(?)) as remaining_days
        FROM mess_plans 
        WHERE student_id = ? AND is_current = 1
    """, (today_str, student_id)).fetchone()

    # Plan history
    plan_history = conn.execute("""
        SELECT * FROM mess_plans WHERE student_id = ? ORDER BY id DESC
    """, (student_id,)).fetchall()

    # Total fees & payments
    total_fees = conn.execute("SELECT COALESCE(SUM(total_fee), 0) as s FROM mess_plans WHERE student_id = ?", (student_id,)).fetchone()['s'] or 0.0
    total_paid = conn.execute("SELECT COALESCE(SUM(amount), 0) as s FROM payments WHERE student_id = ?", (student_id,)).fetchone()['s'] or 0.0
    balance = max(0.0, total_fees - total_paid)

    # Payments list
    payments = conn.execute("""
        SELECT * FROM payments WHERE student_id = ? ORDER BY payment_date DESC, id DESC
    """, (student_id,)).fetchall()

    # Attendance stats
    att_stats = conn.execute("""
        SELECT 
            COUNT(*) as total_days,
            SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_days,
            SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent_days
        FROM attendance
        WHERE student_id = ?
    """, (student_id,)).fetchone()

    # Recent attendance
    recent_attendance = conn.execute("""
        SELECT * FROM attendance WHERE student_id = ? ORDER BY date DESC, id DESC LIMIT 30
    """, (student_id,)).fetchall()

    # Today check-in status
    today_att_lunch = conn.execute("""
        SELECT status FROM attendance WHERE student_id = ? AND date = ? AND (meal_session = 'Lunch' OR meal_session = 'All')
    """, (student_id, today_str)).fetchone()

    today_att_dinner = conn.execute("""
        SELECT status FROM attendance WHERE student_id = ? AND date = ? AND (meal_session = 'Dinner' OR meal_session = 'All')
    """, (student_id, today_str)).fetchone()

    # Absence adjustments
    adjustments = conn.execute("""
        SELECT * FROM absence_adjustments WHERE student_id = ? ORDER BY id DESC
    """, (student_id,)).fetchall()

    conn.close()

    return {
        "student": dict(student),
        "current_plan": dict(current_plan) if current_plan else None,
        "plan_history": [dict(p) for p in plan_history],
        "total_fees": float(total_fees),
        "total_paid": float(total_paid),
        "balance": float(balance),
        "payments": [dict(p) for p in payments],
        "att_stats": dict(att_stats) if att_stats else {"total_days": 0, "present_days": 0, "absent_days": 0},
        "recent_attendance": [dict(a) for a in recent_attendance],
        "today_lunch": dict(today_att_lunch) if today_att_lunch else None,
        "today_dinner": dict(today_att_dinner) if today_att_dinner else None,
        "adjustments": [dict(a) for a in adjustments],
        "today_date": today_str,
        "student_qr_pass": f"MESS-PASS|{student_id}|{student['full_name']}|{student['mess_type']}",
        "current_meal_session": 'Lunch' if datetime.now().hour < 16 else 'Dinner',
        "mess_counter_qr_lunch": f"MESS-ATTENDANCE|CAMPUS-MESS|{today_str}|LUNCH",
        "mess_counter_qr_dinner": f"MESS-ATTENDANCE|CAMPUS-MESS|{today_str}|DINNER",
        "mess_counter_qr_current": f"MESS-ATTENDANCE|CAMPUS-MESS|{today_str}|{'LUNCH' if datetime.now().hour < 16 else 'DINNER'}"
    }

if __name__ == '__main__':
    import sys
    seed = '--init-sample' in sys.argv or True
    init_db(seed_sample=seed)
    update_all_mess_expiries()
