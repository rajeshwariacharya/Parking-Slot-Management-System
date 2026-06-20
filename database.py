import sqlite3
from datetime import datetime
import math

DATABASE = "parking.db"

# ---------------- DATABASE CONNECTION ----------------

def connect_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- CREATE TABLES ----------------

def create_tables():
    conn = connect_db()
    cursor = conn.cursor()

    # USERS TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            vehicle_number TEXT NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user'
        )
    """)

    # PARKING SLOTS TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parking_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_number INTEGER UNIQUE NOT NULL,
            status TEXT DEFAULT 'Available'
        )
    """)

    #vehicles table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vehicles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_number TEXT NOT NULL,
    vehicle_type TEXT NOT NULL,
    entry_time TEXT NOT NULL,
    exit_time TEXT,
    slot_id INTEGER,
    fee REAL,
    status TEXT DEFAULT 'Parked',
    user_id INTEGER,
    printed INTEGER DEFAULT 0,
    FOREIGN KEY (slot_id) REFERENCES parking_slots(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
)  
""")

    # FEEDBACK TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            rating TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parking_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_type TEXT UNIQUE,
            rate_per_hour REAL
        )
    """)

    conn.commit()
    conn.close()

# ---------------- INITIALIZE SLOTS ----------------

def initialize_slots(total_slots=25):
    conn = connect_db()
    count = conn.execute("SELECT COUNT(*) FROM parking_slots").fetchone()[0]

    if count == 0:
        for i in range(1, total_slots + 1):
            conn.execute(
                "INSERT INTO parking_slots (slot_number) VALUES (?)",
                (i,)
            )
        conn.commit()

    conn.close()

# ---------------- USER FUNCTIONS ----------------

def add_user(username, email, vehicle_number, password, role="user"):
    conn = connect_db()
    conn.execute("""
        INSERT INTO users (username, email, vehicle_number, password, role)
        VALUES (?, ?, ?, ?, ?)
    """, (username, email, vehicle_number, password, role))
    conn.commit()
    conn.close()

def get_user(email):
    conn = connect_db()
    user = conn.execute(
        "SELECT * FROM users WHERE email=?",
        (email,)
    ).fetchone()
    conn.close()
    return user

def get_user_by_username(username):
    conn = connect_db()
    user = conn.execute(
        "SELECT * FROM users WHERE username=?",
        (username,)
    ).fetchone()
    conn.close()
    return user

# ---------------- SLOT FUNCTIONS ----------------

def get_slot_counts():
    conn = connect_db()

    total = conn.execute(
        "SELECT COUNT(*) FROM parking_slots"
    ).fetchone()[0]

    available = conn.execute(
        "SELECT COUNT(*) FROM parking_slots WHERE status='Available'"
    ).fetchone()[0]

    conn.close()

    return total, available, total - available

def get_all_slots():
    conn = connect_db()
    slots = conn.execute(
        "SELECT * FROM parking_slots"
    ).fetchall()
    conn.close()
    return slots

def get_slots_by_status(status):
    conn = connect_db()
    slots = conn.execute(
        "SELECT * FROM parking_slots WHERE status=?",
        (status,)
    ).fetchall()
    conn.close()
    return slots

def get_available_slot():
    conn = connect_db()
    slot = conn.execute(
        "SELECT * FROM parking_slots WHERE status='Available' LIMIT 1"
    ).fetchone()
    conn.close()
    return slot

def get_slot_details(slot_number):
    conn = connect_db()
    conn.row_factory = sqlite3.Row

    vehicle = conn.execute("""
        SELECT v.*, p.slot_number
        FROM vehicles v
        JOIN parking_slots p ON v.slot_id = p.id
        WHERE p.slot_number = ?
        ORDER BY v.entry_time DESC
        LIMIT 1
    """, (slot_number,)).fetchone()

    conn.close()
    return vehicle

# ---------------- PARK VEHICLE ----------------

def park_vehicle(vehicle_number, vehicle_type, user_id):

    slot = get_available_slot()
    if not slot:
        return None

    entry_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = connect_db()

    conn.execute("""
        INSERT INTO vehicles (vehicle_number, vehicle_type, entry_time, slot_id, user_id)
        VALUES (?, ?, ?, ?, ?)
    """, (vehicle_number, vehicle_type, entry_time, slot["id"], user_id))

    conn.execute(
        "UPDATE parking_slots SET status='Occupied' WHERE id=?",
        (slot["id"],)
    )

    conn.commit()
    conn.close()

    return slot["slot_number"]


# ---------------- PARKING RATE FUNCTIONS ----------------

def get_all_rates():
    conn = connect_db()
    rates = conn.execute("SELECT * FROM parking_rates").fetchall()
    conn.close()
    return rates

def update_rate(vehicle_type, new_rate):
    conn = connect_db()
    conn.execute(
        "UPDATE parking_rates SET rate_per_hour=? WHERE vehicle_type=?",
        (new_rate, vehicle_type)
    )
    conn.commit()
    conn.close()

# ---------------- INITIALIZE RATES ----------------

def initialize_rates():
    conn = connect_db()

    existing = conn.execute("SELECT COUNT(*) FROM parking_rates").fetchone()[0]

    if existing == 0:
        rates = [
            ("Bike", 10),
            ("Car", 20),
            ("Truck", 30)
        ]

        conn.executemany(
            "INSERT INTO parking_rates (vehicle_type, rate_per_hour) VALUES (?, ?)",
            rates
        )

        conn.commit()

    conn.close()

# ---------------- EXIT VEHICLE ----------------

def exit_vehicle(vehicle_number):
    conn = connect_db()

    vehicle = conn.execute("""
        SELECT v.*, p.slot_number
        FROM vehicles v
        JOIN parking_slots p ON v.slot_id = p.id
        WHERE v.vehicle_number=? AND v.status='Parked'
    """, (vehicle_number,)).fetchone()

    if not vehicle:
        conn.close()
        return None

    exit_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    fee = calculate_fee(
        vehicle["entry_time"],
        exit_time,
        vehicle["vehicle_type"]
    )

    conn.execute("""
        UPDATE vehicles
        SET exit_time=?, fee=?, status='Exited'
        WHERE id=?
    """, (exit_time, fee, vehicle["id"]))

    conn.execute(
        "UPDATE parking_slots SET status='Available' WHERE id=?",
        (vehicle["slot_id"],)
    )

    conn.commit()
    conn.close()

    # Return bill details
    return {
        "vehicle_number": vehicle["vehicle_number"],
        "vehicle_type": vehicle["vehicle_type"],
        "slot_number": vehicle["slot_number"],
        "entry_time": vehicle["entry_time"],
        "exit_time": exit_time,
        "fee": fee
    }

def get_vehicle(vehicle_number):
    conn = connect_db()

    vehicle = conn.execute("""
        SELECT v.*, u.username
        FROM vehicles v
        LEFT JOIN users u ON v.user_id = u.id
        WHERE v.vehicle_number = ?
        ORDER BY v.exit_time DESC
        LIMIT 1
    """, (vehicle_number,)).fetchone()

    conn.close()
    return vehicle

def get_vehicle_for_registration(vehicle_number):
    conn = connect_db()
    vehicle = conn.execute(
        "SELECT * FROM users WHERE vehicle_number = ?", (vehicle_number,)
    ).fetchone()
    conn.close()
    return vehicle

# ---------------- FEE CALCULATION ----------------

def calculate_fee(entry_time, exit_time, vehicle_type):
    entry = datetime.strptime(entry_time, "%Y-%m-%d %H:%M:%S")
    exit = datetime.strptime(exit_time, "%Y-%m-%d %H:%M:%S")

    duration = (exit - entry).total_seconds() / 3600
    hours = max(1, math.ceil(duration))

    conn = connect_db()
    rate = conn.execute(
        "SELECT rate_per_hour FROM parking_rates WHERE vehicle_type=?",
        (vehicle_type,)
    ).fetchone()

    conn.close()

    rate_value = rate["rate_per_hour"] if rate else 20

    return hours * rate_value

# ---------------- LAST EXIT FEE ----------------

def get_last_exit_fee():
    conn = connect_db()

    fee = conn.execute("""
        SELECT fee 
        FROM vehicles 
        WHERE status='Exited'
        ORDER BY exit_time DESC
        LIMIT 1
    """).fetchone()

    conn.close()

    return fee["fee"] if fee else 0

def get_total_revenue():
    conn = connect_db()
    revenue = conn.execute(
        "SELECT SUM(fee) FROM vehicles WHERE status='Exited'"
    ).fetchone()[0]
    conn.close()

    return revenue if revenue else 0

def add_feedback(name, email, rating, message):
    conn = connect_db()
    conn.execute("""
        INSERT INTO feedback (name, email, rating, message)
        VALUES (?, ?, ?, ?)
    """, (name, email, rating, message))
    conn.commit()
    conn.close()

def get_slot_details(slot_number):
    conn = connect_db()

    vehicle = conn.execute("""
        SELECT v.*, p.slot_number, u.username
        FROM vehicles v
        JOIN parking_slots p ON v.slot_id = p.id
        LEFT JOIN users u ON v.user_id = u.id
        WHERE p.slot_number = ?
        AND v.status = 'Parked'
        ORDER BY v.entry_time DESC
        LIMIT 1
    """, (slot_number,)).fetchone()

    conn.close()
    return vehicle

def get_all_users():
    conn = connect_db()

    users = conn.execute("""
        SELECT id, username, email, vehicle_number
        FROM users
    """).fetchall()

    conn.close()
    return users

def get_parking_history():
    conn = connect_db()

    history = conn.execute("""
        SELECT 
            v.vehicle_number,
            v.vehicle_type,
            v.entry_time,
            v.exit_time,
            v.fee,
            u.username
        FROM vehicles v
        LEFT JOIN users u ON v.user_id = u.id
        ORDER BY v.entry_time DESC
    """).fetchall()

    conn.close()
    return history

def get_all_feedback():
    conn = connect_db()

    feedbacks = conn.execute("""
        SELECT name, email, rating, message, created_at
        FROM feedback
        ORDER BY created_at DESC
    """).fetchall()

    conn.close()
    return feedbacks

def get_daily_revenue():
    conn = connect_db()

    data = conn.execute("""
        SELECT DATE(exit_time) as date, SUM(fee) as total
        FROM vehicles
        WHERE status='Exited'
        GROUP BY DATE(exit_time)
        ORDER BY DATE(exit_time)
    """).fetchall()

    conn.close()

    dates = [row["date"] for row in data]
    totals = [row["total"] for row in data]

    return dates, totals

def add_slot():
    conn = connect_db()

    # Get max slot number
    max_slot = conn.execute(
        "SELECT MAX(slot_number) FROM parking_slots"
    ).fetchone()[0]

    next_slot = 1 if max_slot is None else max_slot + 1

    conn.execute(
        "INSERT INTO parking_slots (slot_number) VALUES (?)",
        (next_slot,)
    )

    conn.commit()
    conn.close()

def delete_slot(slot_id):
    conn = connect_db()

    # Check if slot is occupied
    slot = conn.execute(
        "SELECT status FROM parking_slots WHERE id=?",
        (slot_id,)
    ).fetchone()

    if slot and slot["status"] == "Occupied":
        conn.close()
        return False   # Cannot delete

    conn.execute(
        "DELETE FROM parking_slots WHERE id=?",
        (slot_id,)
    )

    conn.commit()
    conn.close()
    return True

def get_occupied_slot_details():
    conn = connect_db()

    data = conn.execute("""
        SELECT 
            p.slot_number,
            v.vehicle_number,
            v.vehicle_type,
            v.entry_time
        FROM vehicles v
        JOIN parking_slots p ON v.slot_id = p.id
        WHERE v.status = 'Parked'
        ORDER BY p.slot_number
    """).fetchall()

    conn.close()
    return data

def get_all_vehicles():
    conn = connect_db()

    data = conn.execute("""
        SELECT v.*, u.username
        FROM vehicles v
        LEFT JOIN users u ON v.user_id = u.id
    """).fetchall()

    conn.close()
    return data

def get_vehicle_by_number(vehicle_number):
    conn = connect_db()
    vehicle = conn.execute(
        "SELECT * FROM vehicles WHERE vehicle_number=?",
        (vehicle_number,)
    ).fetchone()
    conn.close()
    return vehicle

def get_active_vehicle(vehicle_number):
    conn = connect_db()

    vehicle = conn.execute("""
        SELECT * FROM vehicles
        WHERE vehicle_number = ?
        AND status = 'Parked'
    """, (vehicle_number,)).fetchone()

    conn.close()
    return vehicle



def get_filtered_vehicles(date):
    conn = connect_db()

    data = conn.execute("""
        SELECT v.*, u.username
        FROM vehicles v
        LEFT JOIN users u ON v.user_id = u.id
        WHERE DATE(v.entry_time) = ?
    """, (date,)).fetchall()

    conn.close()
    return data

def get_monthly_vehicles(month):
    conn = connect_db()

    data = conn.execute("""
        SELECT v.*, u.username
        FROM vehicles v
        LEFT JOIN users u ON v.user_id = u.id
        WHERE strftime('%Y-%m', v.entry_time) = ?
    """, (month,)).fetchall()

    conn.close()
    return data

def mark_invoice_printed(vehicle_number):
    conn = connect_db()
    conn.execute("""
        UPDATE vehicles
        SET printed = 1
        WHERE vehicle_number = ?
    """, (vehicle_number,))
    conn.commit()
    conn.close()

def mark_invoice_printed(vehicle_number):
    conn = connect_db()
    conn.execute("""
        UPDATE vehicles
        SET printed = 1
        WHERE vehicle_number = ?
    """, (vehicle_number,))
    conn.commit()
    conn.close()
