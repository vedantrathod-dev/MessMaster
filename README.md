# College Mess Management System

A complete, functional, responsive, full-stack **College Mess Management System** designed for educational institutions and campus hostels to manage student admissions, dining plans (Pure Veg & Non-Veg), fee collections, daily attendance, configurable absent-day adjustment policies, and automated expiry workflows.

---

## 🌟 Key Features

### 1. Executive Admin Dashboard
- **10 Core Summary Metrics:**
  1. Total Admitted Students
  2. Active Dining Students
  3. Veg Mess Students
  4. Non-Veg Mess Students
  5. Total Fees Collected
  6. Pending Fee Balances
  7. Students Absent Today
  8. Students with 3+ Consecutive Absences
  9. Students Expiring Within 3 Days (Warning Alert)
  10. Total Expired Students
- **Interactive Visualizations (Chart.js):**
  - 7-Day Attendance Trend bar chart (Present vs Absent)
  - Veg vs Non-Veg Plan Distribution doughnut chart
- **Actionable Tables:** Quick Renew trigger for expiring plans, and one-click Approval for qualifying consecutive absence streaks.

### 2. Student Admission & Registration
- Auto-generates unique student IDs (e.g., `STU20260001`).
- Captures full name, 10-digit mobile number, college/institute name, admission date, mess start date, dining type (Veg / Non-Veg), and plan duration (30, 60, 90, 180 days).
- **Real-Time Client & Server Calculations:** Computes initial expiry date, total fee, and outstanding balance dynamically.
- Duplicate prevention for mobile numbers and student IDs.

### 3. Veg & Non-Veg Dedicated Management
- Dedicated views tailored for **Pure Veg** and **Non-Veg** dining halls.
- Real-time status cards showing total count, active diners, expired count, and collections for that specific mess type.
- Instant search, filtering by status (Active / Expired / Deactivated), and sorting by remaining days, name, or expiry date.

### 4. Fee & Payment Management
- Records full, partial, or multi-installment payments.
- Automatic remaining balance calculation.
- Safeguards preventing negative payments or amounts exceeding outstanding balance.
- Multiple payment modes: UPI / QR Code, Cash, Credit/Debit Card, Net Banking.
- Full transaction history per student and system-wide.
- **Official Printable Receipts:** Professional layout with mess & college branding, breakdown of charges, cumulative payments, remaining balance, and authorized signature line.

### 5. Daily Attendance Tracking
- Date picker interface defaulting to today, with ability to view/edit past dates.
- Bulk action buttons: **Mark All Present** and **Mark All Absent**.
- Filter by dining type (Pure Veg / Non-Veg) and search by student name/ID.
- Prevents duplicate attendance entries on the same date using database `UNIQUE(student_id, date)` constraints and atomic upserts.

### 6. Configurable Absent-Day Adjustment Engine
- **Automated Consecutive Absence Detection:** Scans attendance history within active plan validity to detect contiguous absent days &ge; configured threshold (3 or 4 days).
- **Protection Against Double Crediting:** Ensures absent dates credited once can never be approved or credited again.
- **Admin Review Queue:** Lists eligible students with exact date ranges, credited days, and preview of the extended expiry date.
- **One-Click Approval / Rejection:** Updates student plan with extension days, moves expiry date forward, records audit trail with original and updated expiry dates.

### 7. Automatic Mess Expiry & Renewal
- Calculates plan expiry based on: `start_date + duration_days + approved_extension_days`.
- Server-side logic evaluates dates automatically on every request.
- Automatically transitions overdue students to **Expired** status and removes them from active meal quotas.
- Visual warning badge for students with &le; 3 days remaining.
- **Seamless Renewal:** Archives expired plan (`is_current = 0`, status `Renewed`) and creates a new plan (`is_current = 1`) with recorded payment, preserving complete financial and attendance history.

### 8. Comprehensive Reports & Data Export
- Multi-dimensional reports:
  1. Daily Attendance Report
  2. Monthly Attendance Summary (Present days, Absent days, Attendance %)
  3. Payment Collection Report
  4. Pending Fees & Dues Report
  5. Expired Students Audit
  6. Approved Absent-Day Adjustments Log
- **1-Click CSV Export:** Generates clean CSV files for external analysis.
- **Print Optimization:** Print-friendly styling with clean formatting.

### 9. System Settings & Customization
- Configurable absent threshold (3 vs 4 days).
- Customizable default monthly fees for Veg and Non-Veg mess plans.
- Facility branding (Mess name, college name, contact phone, email, currency symbol).
- Secure password change for administrator account.
- One-click sample data reload for demonstrations and testing.

---

## 🛠️ Technology Stack

| Layer | Technologies Used |
|---|---|
| **Frontend** | HTML5, CSS3 (Custom Design System), Vanilla JavaScript (ES6+), Chart.js |
| **Backend** | Python 3.10+, Flask 3.1, Werkzeug (Password Hashing & Security) |
| **Database** | SQLite3 with Foreign Key constraints, Unique indexes, and Row factories |
| **Tooling** | npm / Node.js `package.json` for task scripts and frontend tooling |

---

## 📂 Project Structure

```
mess-management-system/
├── app.py                     # Main Flask web application & REST routes
├── database.py                # Database models, schema creation, seeder & business logic
├── requirements.txt           # Python backend dependencies
├── package.json               # Node.js project configuration and scripts
├── run.bat                    # Windows Batch launcher
├── run.ps1                    # Windows PowerShell launcher
├── README.md                  # Complete documentation and user manual
├── instance/
│   └── mess.db                # SQLite database file (auto-generated)
├── static/
│   ├── css/
│   │   └── style.css          # Responsive design system & print styles
│   └── js/
│       └── app.js             # Dynamic calculations, modals, & attendance UI helpers
└── templates/
    ├── base.html              # Layout master with sidebar & topbar
    ├── login.html             # Secure administrator login
    ├── dashboard.html         # Analytics dashboard with 10 KPIs & charts
    ├── admission.html         # Student admission form with live fee calculator
    ├── students.html          # All students directory with multi-filter & search
    ├── student_profile.html   # Detailed student profile & history tabs
    ├── veg_mess.html          # Pure Veg mess management page
    ├── nonveg_mess.html       # Non-Veg mess management page
    ├── attendance.html        # Daily attendance sheet with bulk buttons
    ├── payments.html          # Fee collection ledger & record payment modal
    ├── receipt_print.html     # Official printable fee receipt
    ├── absent_approvals.html  # Consecutive absent day detection & approval
    ├── expired_students.html  # Expired memberships queue & renewal
    ├── reports.html           # Multi-report generator with CSV export
    └── settings.html          # System rules & mess settings
```

---

## 🗄️ Database Schema Design

The SQLite database (`instance/mess.db`) implements relational integrity:

1. **`users`**: Administrator credentials with secure password hashes.
2. **`settings`**: Key-value system configurations (absent threshold, fees, branding).
3. **`students`**: Personal details, mobile number (UNIQUE), dining type, admission date, status (`Active`, `Expired`, `Deactivated`).
4. **`mess_plans`**: Mess contracts linked to `students(student_id)`: duration, start date, original expiry, current expiry, extension days, status (`Active`, `Expired`, `Renewed`), `is_current` flag.
5. **`payments`**: Financial ledger linked to student and plan: unique receipt number (`REC-YYYYMMDD-XXXX`), amount, date, method, notes.
6. **`attendance`**: Daily attendance records with `UNIQUE(student_id, date)` constraint to prevent duplicate logging.
7. **`absence_adjustments`**: Tracks consecutive absent sequences, approved days, original and updated expiry dates, approval status, and notes.

---

## 🚀 Installation & Quick Start

### Prerequisites
- Python 3.10 or higher.
- (Optional) Node.js & npm for package scripts.

### 1. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 2. Initialize the Database with Sample Data
```powershell
python database.py --init-sample
```
*This populates 12 realistic student records across Veg and Non-Veg plans, partial payments, expiring warnings, past 14-day attendance, and pending consecutive absent streaks.*

### 3. Run the Application
You can run via any of the following methods:

**Method A (Direct Python):**
```powershell
python app.py
```

**Method B (Windows Batch):**
```cmd
run.bat
```

**Method C (Windows PowerShell):**
```powershell
.\run.ps1
```

**Method D (npm script):**
```bash
npm start
```

### 4. Access the Portal
Open your web browser and navigate to:
```
http://127.0.0.1:5000
```

**Default Administrator Credentials:**
- **Username:** `admin`
- **Password:** `admin123`

---

## 🧪 Step-by-Step Testing Walkthrough

### 1. Dashboard Overview
1. Sign in with `admin` / `admin123`.
2. Inspect the **10 Summary KPI cards** (Total Admitted, Active, Veg, Non-Veg, Collected, Pending Dues, Absent Today, 3+ Consecutive Absences, Expiring in &le; 3 Days, Expired).
3. Review the interactive **7-Day Attendance Trend** and **Plan Distribution** charts.
4. Check the **Expiring in &le; 3 Days** alert table and click **Renew** on any candidate.

### 2. Testing Student Admission
1. Click **New Admission** from the topbar or sidebar.
2. Enter student details:
   - Name: `Siddharth Rao`
   - Mobile: `9876500111`
   - College: `National Institute of Tech`
   - Mess Type: Select `Non-Veg` (notice fee changes to ₹4200 automatically).
   - Duration: Select `60 Days` (notice fee updates to ₹8400 and expiry adjusts dynamically).
   - Amount Paid: Enter `5000` (notice balance shows ₹3400 in real-time).
   - Method: Select `UPI`.
3. Submit the form.
4. The system validates uniqueness, creates the student record, saves the plan, and automatically redirects to the generated **Payment Receipt**.

### 3. Testing Daily Attendance
1. Click **Attendance** from the sidebar.
2. Select any date or use today's date.
3. Click **Mark All Present** or **Mark All Absent** to verify bulk selection.
4. Toggle individual students between Present and Absent.
5. Click **Save Attendance**. Verify that existing records are updated seamlessly without creating duplicates.

### 4. Testing Absent-Day Adjustments
1. Navigate to **Absent Approvals**.
2. Notice the detected qualifying students with &ge; 3 consecutive absences.
3. Review the candidate details: student name, exact absent dates range, credited days, and proposed new expiry date.
4. Click **Approve Extension**.
5. Observe the success confirmation: the student's plan expiry date is moved forward by the exact credited days, and the event is logged in the permanent audit table.

### 5. Testing Payments & Receipt Generation
1. Click **Payments** from the sidebar.
2. Click **Record New Payment**.
3. Select a student with outstanding dues (e.g. `Rohan Patel`). Notice their current due amount is displayed.
4. Enter payment amount (e.g. `1000`), choose `UPI`, and click **Generate Receipt & Record**.
5. The official printable receipt appears with updated cumulative totals and reduced balance.
6. Click **Print Receipt / Save PDF** to verify printer styling.

### 6. Testing Expired Plans & Renewals
1. Click **Expired Students** from the sidebar.
2. View students whose validity dates have passed (e.g. `Kabir Verma`).
3. Click **Renew Mess**.
4. Choose renewal duration (30 days), enter payment details, and submit.
5. Notice that the old plan is marked `Renewed`, a fresh plan is activated, and the student transitions from Expired back to `Active`.

### 7. Testing Reports & CSV Exports
1. Click **Reports & Export** from the sidebar.
2. Switch between **Daily Attendance**, **Monthly Attendance**, **Payment Collection**, and **Pending Fees**.
3. Click **Export to CSV** &mdash; a spreadsheet file is downloaded instantly.
4. Click **Print Report** &mdash; view the print-formatted ledger.

---

## 🔒 Security & Reliability Highlights
- **Parameterized SQL Queries:** All database interactions utilize SQLite parameter substitution (`?`) to prevent SQL injection vulnerabilities.
- **Password Hashing:** Administrative passwords stored using PBKDF2/SHA-256 via `werkzeug.security`.
- **Session Authentication:** All management routes guarded by `@login_required` decorators.
- **Transaction Safety:** Payments and absence adjustments update balances and expiry dates within atomic SQLite transactions.
- **Data Preservation:** Student deactivation preserves all historical plans, payments, and attendance records.
