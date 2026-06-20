from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import database as db
import re

app = Flask(__name__)
app.secret_key = "super_secret_key"

db.create_tables()
db.initialize_slots(25)
db.initialize_rates() 

# ---------------- HOME ----------------
@app.route('/')
def home():
    return redirect(url_for('login'))

# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':

        username = request.form['username'].strip()
        email = request.form['email'].strip()
        vehicle_number = request.form['vehicle_number'].strip().upper()  # convert to uppercase
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        # Username validation
        if not username.isalpha():
            flash("Username must contain only letters.", "danger")
            return redirect(url_for('register'))

        # Email validation
        if not re.match(r'^[a-zA-Z0-9._%+-]+@gmail\.com$', email):
            flash("Email must be valid and end with @gmail.com", "danger")
            return redirect(url_for('register'))

        # Vehicle validation
        if not re.match(r'^[A-Z]{2}[0-9]{2}[A-Z]{2}[0-9]{4}$', vehicle_number):
            flash("Invalid vehicle number format (Example: KA01AB1234)", "danger")
            return redirect(url_for('register'))

        if db.get_vehicle_for_registration(vehicle_number):
            flash("Vehicle number already registered by another user.", "danger")
            return redirect(url_for('register'))
        
        # Password validation
        if len(password) != 6:
            flash("Password must be exactly 6 characters.", "danger")
            return redirect(url_for('register'))

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for('register'))

        # Check if email already exists
        if db.get_user(email):
            flash("Email already registered.", "danger")
            return redirect(url_for('register'))

        # Save user
        hashed_password = generate_password_hash(password)
        db.add_user(username, email, vehicle_number, hashed_password)

        flash("Registration successful. Please login.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')

# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':

        email = request.form['email'].strip()
        password = request.form['password']
        # -------- ADMIN LOGIN --------
        if email == "admin123@gmail.com" and password == "admin1":
            session['admin'] = "admin"
            flash("Admin login successful!", "success")
            return redirect(url_for('admin_dashboard'))

        user = db.get_user(email)

        if not user:
            flash("Invalid email.", "danger")
            return redirect(url_for('login'))

        if not check_password_hash(user['password'], password):
            flash("Incorrect password.", "danger")
            return redirect(url_for('login'))
        
        session['user_id'] = user['id']   # ✅ IMPORTANT
        session['user'] = user['username']
        flash("Login successful!", "success")
        return redirect(url_for('dashboard'))

    return render_template('login.html')

# ---------------- DASHBOARD ----------------
@app.route('/dashboard')
def dashboard():

    username = session.get('user')   # ✅ USE HERE

    if not username:
        return redirect(url_for('login'))

    total, available, occupied = db.get_slot_counts()

    revenue = db.get_last_exit_fee()

    return render_template(
        'dashboard.html',
        username=username,   # ✅ use variable
        total=total,
        available=available,
        occupied=occupied,
        revenue=revenue
    )

@app.route('/admin_dashboard')
def admin_dashboard():

    admin = session.get('admin')

    if not admin:
        return redirect(url_for('login'))

    total, available, occupied = db.get_slot_counts()

    # ✅ admin sees total revenue
    revenue = db.get_total_revenue()

    return render_template(
        'admin_dashboard.html',
        admin=admin,
        total=total,
        available=available,
        occupied=occupied,
        revenue=revenue
    )

@app.route('/admin_users')
def admin_users():

    if 'admin' not in session:
        return redirect(url_for('login'))

    users = db.get_all_users()

    return render_template("admin_users.html", users=users)
@app.route('/available_slots')
def available_slots():
    slots = db.get_slots_by_status("Available")
    return render_template("view_slots.html", slots=slots)

@app.route('/occupied_slots')
def occupied_slots():
    print(session)   # 🔥 DEBUG
    if 'user' not in session and 'admin' not in session:
        return redirect(url_for('login'))

    data = db.get_occupied_slot_details()
    print(data)

    return render_template(
        "occupied_details.html",
        data=data,
        is_admin='admin' in session
    )
    

# ---------------- VIEW SLOTS ----------------
@app.route('/view_slots')
def view_slots():

    if 'user' not in session and 'admin' not in session:
        return redirect(url_for('login'))

    filter_type = request.args.get('filter', 'all')

    if filter_type == 'available':
        slots = db.get_slots_by_status('Available')
    elif filter_type == 'occupied':
        slots = db.get_slots_by_status('Occupied')
    else:
        slots = db.get_all_slots()

    # Detect admin
    is_admin = 'admin' in session

    return render_template('view_slots.html', slots=slots, is_admin=is_admin)

@app.route('/slot_details/<int:slot_number>')
def slot_details(slot_number):

    vehicle = db.get_slot_details(slot_number)

    return render_template("slot_details.html", vehicle=vehicle)

# ---------------- ADD VEHICLE ----------------

@app.route('/add_vehicle', methods=['GET', 'POST'])
def add_vehicle():
    if 'user' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':

        vehicle_number = request.form['vehicle_number'].strip().upper()
        vehicle_type = request.form['vehicle_type']
        user_id = session['user_id']

        # 🔴 VALIDATION: EMPTY
        if not vehicle_number:
            flash("⚠️ Enter vehicle number", "danger")
            return redirect(url_for('add_vehicle'))

        if not vehicle_type:
            flash("⚠️ Select vehicle type", "danger")
            return redirect(url_for('add_vehicle'))

        # 🔴 VALIDATION: FORMAT
        import re
        if not re.match(r'^[A-Z]{2}[0-9]{2}[A-Z]{2}[0-9]{4}$', vehicle_number):
            flash("❌ Invalid format (Example: KA01AB1234)", "danger")
            return redirect(url_for('add_vehicle'))

        # ✅ 🔥 THIS IS THE LINE YOU ASKED ABOUT
        existing_vehicle = db.get_active_vehicle(vehicle_number)

        # 🔴 CHECK IF ALREADY PARKED
        if existing_vehicle:
            flash("❌ Vehicle already parked!", "danger")
            return redirect(url_for('add_vehicle'))

        # ✅ PARK VEHICLE
        slot = db.park_vehicle(vehicle_number, vehicle_type, user_id)

        if not slot:
            flash("No slots available!", "danger")
        else:
            flash(f"✅ Vehicle parked in Slot {slot}", "success")

        return redirect(url_for('dashboard'))

    # GET request
    rates = db.get_all_rates()
    rate_dict = {r["vehicle_type"]: r["rate_per_hour"] for r in rates}

    return render_template('add_vehicle.html', rates=rate_dict)

# ---------------- EXIT VEHICLE ----------------
@app.route('/exit_vehicle', methods=['GET', 'POST'])
def exit_vehicle():
    if request.method == 'POST':
        vehicle_number = request.form['vehicle_number'].strip().upper()

        bill = db.exit_vehicle(vehicle_number)

        if not bill:
            flash("Vehicle not found!", "danger")
            return redirect(url_for('exit_vehicle'))

        return render_template("bill.html", bill=bill)

    return render_template('exit_vehicle.html')

@app.route('/manage_rates', methods=['GET', 'POST'])
def manage_rates():

    if 'admin' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        vehicle_type = request.form['vehicle_type']
        rate = request.form['rate']

        db.update_rate(vehicle_type, rate)
        flash("Rate updated successfully!", "success")

        return redirect(url_for('manage_rates'))

    rates = db.get_all_rates()
    return render_template("manage_rates.html", rates=rates)   

  

   

# ---------------- FEEDBACK ----------------
@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if 'user' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form.get('name')   # optional
        email = request.form['email']
        rating = request.form['rating']
        message = request.form['message']

        db.add_feedback(name, email, rating, message)

        flash("Thank you for your feedback!", "success")
        return redirect(url_for('dashboard'))

    return render_template('feedback.html')
# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for('login'))

@app.route('/parking_history')
def parking_history():
    if 'admin' not in session:
        return redirect(url_for('login'))

    history = db.get_parking_history()
    return render_template('parking_history.html', history=history)

@app.route('/admin_feedback')
def admin_feedback():
    if 'admin' not in session:
        return redirect(url_for('login'))

    feedbacks = db.get_all_feedback()
    return render_template('admin_feedback.html', feedbacks=feedbacks)

@app.route('/daily_revenue')
def daily_revenue():
    if 'admin' not in session:
        return redirect(url_for('login'))

    dates, totals = db.get_daily_revenue()

    return render_template(
        'daily_revenue.html',
        dates=dates,
        totals=totals
    )

@app.route('/add_slot')
def add_slot():
    if 'admin' not in session:
        return redirect(url_for('login'))

    db.add_slot()
    flash("New slot added successfully!", "success")
    return redirect(url_for('view_slots'))

@app.route('/delete_slot/<int:slot_id>')
def delete_slot(slot_id):
    if 'admin' not in session:
        return redirect(url_for('login'))

    success = db.delete_slot(slot_id)

    if not success:
        flash("Cannot delete occupied slot!", "danger")
    else:
        flash("Slot deleted successfully!", "success")

    return redirect(url_for('view_slots'))

from datetime import datetime

@app.route('/report')
def report():

    if 'admin' not in session:
        return redirect(url_for('login'))

    filter_type = request.args.get('filter')

    if filter_type == "daily":
        today = datetime.now().strftime("%Y-%m-%d")
        data = db.get_filtered_vehicles(today)
    elif filter_type == "monthly":
        month = datetime.now().strftime("%Y-%m")
        data = db.get_monthly_vehicles(month)
    else:
        data = db.get_all_vehicles()

    return render_template('report.html', data=data)



@app.route('/invoice/<vehicle_number>')
def invoice(vehicle_number):

    db.mark_invoice_printed(vehicle_number)   # 🔥 ADD THIS

    vehicle = db.get_vehicle(vehicle_number)
    return render_template('invoice.html', vehicle=vehicle)

if __name__ == '__main__':
    app.run(debug=True)
