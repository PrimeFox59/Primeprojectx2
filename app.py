import streamlit as st
import pandas as pd
import sqlite3
import os
import time
from datetime import datetime, date, time as dt_time, timedelta
import altair as alt
import pytz
import json
import urllib.parse
import secrets
import hashlib

# Timezone GMT+7 (WIB)
WIB = pytz.timezone('Asia/Jakarta')

# Helper functions untuk format tanggal
def parse_date(date_str):
    """Parse tanggal dari berbagai format ke datetime object"""
    if pd.isna(date_str) or date_str == '' or date_str is None:
        return None
    
    date_str = str(date_str).strip()
    
    # Try dd-mm-yyyy first (format baru kita)
    for fmt in ['%d-%m-%Y', '%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d']:
        try:
            return datetime.strptime(date_str, fmt)
        except:
            continue
    
    # Try pandas parsing as fallback
    try:
        return pd.to_datetime(date_str)
    except:
        return None

def format_date(date_obj):
    """Format datetime object ke string dd-mm-yyyy"""
    if pd.isna(date_obj) or date_obj is None:
        return ''
    if hasattr(date_obj, 'strftime'):
        return date_obj.strftime('%d-%m-%Y')
    return str(date_obj)

def format_datetime(dt_obj):
    """Format datetime object ke string dd-mm-yyyy HH:MM:SS"""
    if pd.isna(dt_obj) or dt_obj is None:
        return ''
    if hasattr(dt_obj, 'strftime'):
        return dt_obj.strftime('%d-%m-%Y %H:%M:%S')
    return str(dt_obj)

DB_NAME = "car_wash.db"

# Paket Cucian (akan diload dari database)
PAKET_CUCIAN = {
    "Cuci Reguler": 50000,
    "Cuci Premium": 75000,
    "Cuci + Wax": 100000,
    "Full Detailing": 200000,
    "Interior Only": 60000,
    "Exterior Only": 40000
}

# --- Kasir - Menu Coffee & Snack ---
DEFAULT_COFFEE_MENU = {
    "Espresso": 15000,
    "Americano": 18000,
    "Latte": 22000,
    "Cappuccino": 22000,
    "Mocha": 25000,
    "Iced Coffee": 20000,
    "Biskuit": 8000,
    "Roti Manis": 12000,
    "Sandwich": 20000
}

# Default checklist items (akan diload dari database)
DEFAULT_CHECKLIST_DATANG = [
    "Ban lengkap dan baik",
    "Wiper berfungsi", 
    "Kaca tidak retak",
    "Body tidak penyok",
    "Lampu lengkap",
    "Spion lengkap"
]

DEFAULT_CHECKLIST_SELESAI = [
    "Interior bersih",
    "Exterior bersih",
    "Kaca bersih",
    "Ban hitam mengkilap",
    "Dashboard bersih",
    "Tidak ada noda"
]

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Tabel customers - database pelanggan
    c.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nopol TEXT UNIQUE NOT NULL,
            nama_customer TEXT NOT NULL,
            no_telp TEXT,
            jenis_kendaraan TEXT,
            merk_kendaraan TEXT,
            ukuran_mobil TEXT,
            created_at TEXT NOT NULL
        )
    ''')
    
    # Tabel wash_transactions - transaksi cuci mobil
    c.execute('''
        CREATE TABLE IF NOT EXISTS wash_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nopol TEXT NOT NULL,
            nama_customer TEXT NOT NULL,
            tanggal TEXT NOT NULL,
            waktu_masuk TEXT NOT NULL,
            waktu_selesai TEXT,
            paket_cuci TEXT NOT NULL,
            harga INTEGER NOT NULL,
            jenis_kendaraan TEXT,
            merk_kendaraan TEXT,
            ukuran_mobil TEXT,
            checklist_datang TEXT,
            checklist_selesai TEXT,
            qc_barang TEXT,
            catatan TEXT,
            status TEXT DEFAULT 'Dalam Proses',
            created_by TEXT,
            FOREIGN KEY (nopol) REFERENCES customers(nopol)
        )
    ''')
    
    # Tabel audit trail
    c.execute('''
        CREATE TABLE IF NOT EXISTS audit_trail (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            user TEXT NOT NULL,
            action TEXT NOT NULL,
            detail TEXT
        )
    ''')
    
    # Tabel settings - untuk konfigurasi toko
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_key TEXT UNIQUE NOT NULL,
            setting_value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    
    # Insert default settings jika belum ada
    c.execute("SELECT COUNT(*) FROM settings")
    if c.fetchone()[0] == 0:
        now = datetime.now(WIB).strftime("%d-%m-%Y %H:%M:%S")
        
        # Default paket cucian
        c.execute("INSERT INTO settings (setting_key, setting_value, updated_at) VALUES (?, ?, ?)",
                 ("paket_cucian", json.dumps(PAKET_CUCIAN), now))
        
        # Default checklist
        c.execute("INSERT INTO settings (setting_key, setting_value, updated_at) VALUES (?, ?, ?)",
                 ("checklist_datang", json.dumps(DEFAULT_CHECKLIST_DATANG), now))
        c.execute("INSERT INTO settings (setting_key, setting_value, updated_at) VALUES (?, ?, ?)",
                 ("checklist_selesai", json.dumps(DEFAULT_CHECKLIST_SELESAI), now))
        
        # Info toko
        toko_info = {
            "nama": "TIME AUTOCARE",
            "tagline": "Detailing & Ceramic Coating",
            "alamat": "Jl. Contoh No. 123",
            "telp": "08123456789",
            "email": "info@timeautocare.com"
        }
        c.execute("INSERT INTO settings (setting_key, setting_value, updated_at) VALUES (?, ?, ?)",
                 ("toko_info", json.dumps(toko_info), now))
        # Default coffee shop menu
        c.execute("INSERT INTO settings (setting_key, setting_value, updated_at) VALUES (?, ?, ?)",
                 ("coffee_menu", json.dumps(DEFAULT_COFFEE_MENU), now))
        # Default multiplier ukuran mobil
        default_multiplier = {
            "Kecil": 1.0,
            "Sedang": 1.2,
            "Besar": 1.5,
            "Extra Besar": 2.0
        }
        c.execute("INSERT INTO settings (setting_key, setting_value, updated_at) VALUES (?, ?, ?)",
                 ("ukuran_multiplier", json.dumps(default_multiplier), now))

    # Tabel untuk menyimpan transaksi penjualan kopi/snack
    c.execute('''
        CREATE TABLE IF NOT EXISTS coffee_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            items TEXT NOT NULL,
            total INTEGER NOT NULL,
            tanggal TEXT NOT NULL,
            waktu TEXT NOT NULL,
            nama_customer TEXT,
            no_telp TEXT,
            created_by TEXT
        )
    ''')
    
    # Migration: Add nama_customer and no_telp columns if they don't exist
    try:
        c.execute("SELECT nama_customer FROM coffee_sales LIMIT 1")
    except sqlite3.OperationalError:
        # Column doesn't exist, add it
        c.execute("ALTER TABLE coffee_sales ADD COLUMN nama_customer TEXT")
        c.execute("ALTER TABLE coffee_sales ADD COLUMN no_telp TEXT")
    
    # Tabel untuk transaksi Kasir (gabungan cuci mobil + coffee/snack)
    c.execute('''
        CREATE TABLE IF NOT EXISTS kasir_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nopol TEXT NOT NULL,
            nama_customer TEXT NOT NULL,
            no_telp TEXT,
            tanggal TEXT NOT NULL,
            waktu TEXT NOT NULL,
            wash_trans_id INTEGER,
            paket_cuci TEXT,
            harga_cuci INTEGER DEFAULT 0,
            coffee_items TEXT,
            harga_coffee INTEGER DEFAULT 0,
            total_bayar INTEGER NOT NULL,
            status_bayar TEXT DEFAULT 'Lunas',
            metode_bayar TEXT,
            created_by TEXT,
            catatan TEXT,
            FOREIGN KEY (nopol) REFERENCES customers(nopol),
            FOREIGN KEY (wash_trans_id) REFERENCES wash_transactions(id)
        )
    ''')
    
    # Migration: Add secret_code column to existing kasir_transactions table if it doesn't exist
    try:
        c.execute("SELECT secret_code FROM kasir_transactions LIMIT 1")
    except sqlite3.OperationalError:
        # Column doesn't exist, add it
        c.execute("ALTER TABLE kasir_transactions ADD COLUMN secret_code TEXT")
        conn.commit()
    
    # Migration: Add vehicle info columns to customers table if they don't exist
    try:
        c.execute("SELECT jenis_kendaraan FROM customers LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE customers ADD COLUMN jenis_kendaraan TEXT")
        conn.commit()
    
    try:
        c.execute("SELECT merk_kendaraan FROM customers LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE customers ADD COLUMN merk_kendaraan TEXT")
        conn.commit()
    
    try:
        c.execute("SELECT ukuran_mobil FROM customers LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE customers ADD COLUMN ukuran_mobil TEXT")
        conn.commit()
    
    # Migration: Add vehicle info columns to wash_transactions table if they don't exist
    try:
        c.execute("SELECT jenis_kendaraan FROM wash_transactions LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE wash_transactions ADD COLUMN jenis_kendaraan TEXT")
        conn.commit()
    
    try:
        c.execute("SELECT merk_kendaraan FROM wash_transactions LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE wash_transactions ADD COLUMN merk_kendaraan TEXT")
        conn.commit()
    
    try:
        c.execute("SELECT ukuran_mobil FROM wash_transactions LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE wash_transactions ADD COLUMN ukuran_mobil TEXT")
        conn.commit()
    
    # Tabel customer_reviews - untuk menyimpan review dari customer
    # Check if table exists and has wrong structure, recreate if needed
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='customer_reviews'")
    if c.fetchone():
        # Table exists, check if it has created_at column (old structure)
        c.execute("PRAGMA table_info(customer_reviews)")
        columns = [col[1] for col in c.fetchall()]
        if 'created_at' in columns:
            # Old structure detected, need to recreate table
            # First, backup existing data
            c.execute("ALTER TABLE customer_reviews RENAME TO customer_reviews_old")
            conn.commit()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS customer_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            secret_code TEXT NOT NULL,
            trans_id INTEGER,
            trans_type TEXT NOT NULL,
            nopol TEXT,
            no_telp TEXT,
            nama_customer TEXT NOT NULL,
            rating INTEGER NOT NULL,
            review_text TEXT,
            review_date TEXT NOT NULL,
            review_time TEXT NOT NULL,
            FOREIGN KEY (trans_id) REFERENCES kasir_transactions(id)
        )
    ''')
    
    # Migrate data from old table if it exists
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='customer_reviews_old'")
    if c.fetchone():
        try:
            c.execute("""
                INSERT INTO customer_reviews 
                (id, secret_code, trans_id, trans_type, nopol, no_telp, nama_customer, rating, review_text, review_date, review_time)
                SELECT id, secret_code, trans_id, trans_type, nopol, no_telp, nama_customer, rating, review_text, review_date, review_time
                FROM customer_reviews_old
            """)
            c.execute("DROP TABLE customer_reviews_old")
            conn.commit()
        except:
            pass
    
    # Migration: Add reward_points column to existing customer_reviews table if it doesn't exist
    try:
        c.execute("SELECT reward_points FROM customer_reviews LIMIT 1")
    except sqlite3.OperationalError:
        # Column doesn't exist, add it
        c.execute("ALTER TABLE customer_reviews ADD COLUMN reward_points INTEGER DEFAULT 10")
        conn.commit()
    
    # Tabel customer_points - untuk menyimpan akumulasi poin customer
    c.execute('''
        CREATE TABLE IF NOT EXISTS customer_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nopol TEXT,
            no_telp TEXT,
            nama_customer TEXT NOT NULL,
            total_points INTEGER DEFAULT 0,
            last_updated TEXT NOT NULL,
            UNIQUE(nopol, no_telp)
        )
    ''')
    
    # Tabel users - untuk menyimpan user accounts
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by TEXT,
            last_login TEXT
        )
    ''')
    
    # Insert default users jika belum ada
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        now = datetime.now(WIB).strftime("%d-%m-%Y %H:%M:%S")
        default_users = [
            ("admin", "admin123", "Admin", now, "system", None),
            ("kasir", "kasir123", "Kasir", now, "system", None),
            ("supervisor", "super123", "Supervisor", now, "system", None)
        ]
        c.executemany("""
            INSERT INTO users (username, password, role, created_at, created_by, last_login)
            VALUES (?, ?, ?, ?, ?, ?)
        """, default_users)
    
    # Tabel employees - data karyawan
    c.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL,
            role_karyawan TEXT NOT NULL,
            gaji_tetap INTEGER DEFAULT 0,
            shift TEXT,
            jam_masuk_default TEXT,
            jam_pulang_default TEXT,
            status TEXT DEFAULT 'Aktif',
            no_telp TEXT,
            created_at TEXT NOT NULL,
            created_by TEXT
        )
    ''')
    
    # Tabel attendance - presensi karyawan
    c.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            tanggal TEXT NOT NULL,
            jam_masuk TEXT NOT NULL,
            jam_pulang TEXT,
            shift TEXT,
            status TEXT DEFAULT 'Hadir',
            catatan TEXT,
            created_by TEXT,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    ''')
    
    # Tabel payroll - pembayaran gaji
    c.execute('''
        CREATE TABLE IF NOT EXISTS payroll (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            periode_awal TEXT NOT NULL,
            periode_akhir TEXT NOT NULL,
            total_hari_kerja INTEGER DEFAULT 0,
            total_gaji INTEGER NOT NULL,
            bonus INTEGER DEFAULT 0,
            potongan INTEGER DEFAULT 0,
            gaji_bersih INTEGER NOT NULL,
            status TEXT DEFAULT 'Pending',
            tanggal_bayar TEXT,
            catatan TEXT,
            created_at TEXT NOT NULL,
            created_by TEXT,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    ''')
    
    # Tabel shift_settings - setting shift dan persentase
    c.execute('''
        CREATE TABLE IF NOT EXISTS shift_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shift_name TEXT UNIQUE NOT NULL,
            jam_mulai TEXT NOT NULL,
            jam_selesai TEXT NOT NULL,
            persentase_gaji REAL NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    
    # Insert default shift settings
    c.execute("SELECT COUNT(*) FROM shift_settings")
    if c.fetchone()[0] == 0:
        now = datetime.now(WIB).strftime("%d-%m-%Y %H:%M:%S")
        default_shifts = [
            ("Pagi", "08:00", "17:00", 35.0, now),
            ("Malam", "17:00", "08:00", 45.0, now)
        ]
        c.executemany("""
            INSERT INTO shift_settings (shift_name, jam_mulai, jam_selesai, persentase_gaji, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, default_shifts)
    
    # Tabel kas_bon - untuk mencatat hutang/pinjaman karyawan
    c.execute('''
        CREATE TABLE IF NOT EXISTS kas_bon (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            tanggal TEXT NOT NULL,
            jumlah INTEGER NOT NULL,
            keterangan TEXT,
            status TEXT DEFAULT 'Belum Lunas',
            sisa_hutang INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            created_by TEXT,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    ''')
    
    # Tabel pembayaran_kas_bon - untuk mencatat cicilan pembayaran kas bon
    c.execute('''
        CREATE TABLE IF NOT EXISTS pembayaran_kas_bon (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kas_bon_id INTEGER NOT NULL,
            payroll_id INTEGER,
            tanggal_bayar TEXT NOT NULL,
            jumlah_bayar INTEGER NOT NULL,
            metode TEXT DEFAULT 'Potong Gaji',
            keterangan TEXT,
            created_at TEXT NOT NULL,
            created_by TEXT,
            FOREIGN KEY (kas_bon_id) REFERENCES kas_bon(id),
            FOREIGN KEY (payroll_id) REFERENCES payroll(id)
        )
    ''')
    
    conn.commit()
    conn.close()


def generate_secret_code():
    """Generate unique 8-character secret code"""
    return secrets.token_urlsafe(6).upper().replace('-', 'X').replace('_', 'Y')[:8]


# --- Data Dummy Functions ---
def check_database_empty():
    """Check apakah database kosong (perlu di-populate)"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Check apakah ada customers
    c.execute("SELECT COUNT(*) FROM customers")
    customer_count = c.fetchone()[0]
    
    conn.close()
    return customer_count == 0


def reset_database():
    """Reset seluruh database (hapus semua data transaksi)"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    try:
        # Hapus semua data dari tabel-tabel transaksi
        tables = [
            'pembayaran_kas_bon',
            'kas_bon',
            'customer_reviews',
            'customer_points',
            'kasir_transactions',
            'coffee_sales',
            'wash_transactions',
            'payroll',
            'attendance',
            'employees',
            'customers',
            'audit_trail'
        ]
        
        for table in tables:
            c.execute(f"DELETE FROM {table}")
        
        conn.commit()
        return True, "Database berhasil di-reset!"
    except Exception as e:
        conn.rollback()
        return False, f"Error reset database: {str(e)}"
    finally:
        conn.close()


def populate_dummy_data():
    """Populate database dengan data dummy yang lengkap"""
    import random
    
    # Data untuk generate
    NAMA_DEPAN = [
        "Budi", "Siti", "Ahmad", "Dewi", "Rudi", "Ani", "Agus", "Sri", "Bambang", "Lina",
        "Hendra", "Maya", "Andi", "Rina", "Doni", "Sari", "Eko", "Wati", "Fajar", "Indah",
        "Joko", "Nur", "Teguh", "Putri", "Wahyu", "Ayu", "Yudi", "Lestari", "Rahmat", "Kartika"
    ]
    
    NAMA_BELAKANG = [
        "Santoso", "Wijaya", "Pratama", "Kusuma", "Putra", "Putri", "Setiawan", "Wibowo",
        "Hidayat", "Nugroho", "Permana", "Saputra", "Kurniawan", "Suryanto", "Gunawan"
    ]
    
    JENIS_KENDARAAN = ["Mobil", "Motor"]
    MERK_MOBIL = ["Toyota", "Honda", "Suzuki", "Daihatsu", "Mitsubishi", "Nissan", "Mazda", "BMW"]
    MERK_MOTOR = ["Honda", "Yamaha", "Suzuki", "Kawasaki", "Vespa"]
    UKURAN_MOBIL = ["Kecil", "Sedang", "Besar", "Extra Besar"]
    
    METODE_BAYAR = ["Tunai", "Transfer", "QRIS", "Debit"]
    
    REVIEW_TEXTS = [
        "Sangat puas dengan pelayanan, mobil bersih dan wangi!",
        "Pelayanan cepat dan hasil memuaskan.",
        "Harga terjangkau, hasil maksimal. Recommended!",
        "Staff ramah dan profesional.",
        "Tempat bersih, hasil cucian bagus.",
        "Kualitas cucian sangat baik, akan kembali lagi."
    ]
    
    def generate_nopol():
        huruf = ['B', 'D', 'L', 'F', 'N', 'T', 'S', 'H', 'K', 'R']
        angka = random.randint(1000, 9999)
        huruf_akhir = random.choice('ABCDEFGHIJKLMNOPQRST')
        huruf_akhir2 = random.choice('ABCDEFGHIJKLMNOPQRST')
        return f"{random.choice(huruf)}{angka}{huruf_akhir}{huruf_akhir2}"
    
    def generate_phone():
        return f"08{random.randint(1, 9)}{random.randint(10000000, 99999999)}"
    
    def generate_nama():
        return f"{random.choice(NAMA_DEPAN)} {random.choice(NAMA_BELAKANG)}"
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    try:
        now = datetime.now(WIB)
        
        # 1. Populate Customers (30 pelanggan)
        customers = []
        for i in range(30):
            nopol = generate_nopol()
            nama = generate_nama()
            no_telp = generate_phone()
            jenis_kendaraan = random.choice(JENIS_KENDARAAN)
            
            if jenis_kendaraan == "Mobil":
                merk = random.choice(MERK_MOBIL)
                ukuran = random.choice(UKURAN_MOBIL)
            else:
                merk = random.choice(MERK_MOTOR)
                ukuran = "Kecil"
            
            days_ago = random.randint(1, 180)
            created_at = now - timedelta(days=days_ago)
            
            try:
                c.execute("""
                    INSERT INTO customers (nopol, nama_customer, no_telp, jenis_kendaraan, merk_kendaraan, ukuran_mobil, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (nopol, nama, no_telp, jenis_kendaraan, merk, ukuran, format_datetime(created_at)))
                
                customers.append({
                    'nopol': nopol, 'nama': nama, 'no_telp': no_telp,
                    'jenis_kendaraan': jenis_kendaraan, 'merk': merk, 'ukuran': ukuran
                })
            except:
                pass
        
        # 2. Populate Employees (6 karyawan)
        roles = ["Washer", "QC Inspector", "Kasir", "Supervisor"]
        gaji_ranges = {
            "Washer": (3000000, 4000000),
            "QC Inspector": (3500000, 4500000),
            "Kasir": (3500000, 4500000),
            "Supervisor": (5000000, 6000000)
        }
        shifts = ["Pagi", "Malam"]
        shift_times = {"Pagi": ("08:00", "17:00"), "Malam": ("17:00", "08:00")}
        
        employees = []
        for i in range(6):
            nama = generate_nama()
            role = random.choice(roles)
            gaji_min, gaji_max = gaji_ranges[role]
            gaji = random.randint(gaji_min // 100000, gaji_max // 100000) * 100000
            shift = random.choice(shifts)
            jam_masuk, jam_pulang = shift_times[shift]
            
            c.execute("""
                INSERT INTO employees (nama, role_karyawan, gaji_tetap, shift, jam_masuk_default, 
                                       jam_pulang_default, status, no_telp, created_at, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (nama, role, gaji, shift, jam_masuk, jam_pulang, "Aktif", generate_phone(), 
                  format_datetime(now - timedelta(days=random.randint(30, 365))), "admin"))
            
            employees.append({'id': c.lastrowid, 'nama': nama, 'role': role, 'gaji': gaji, 'shift': shift})
        
        # 3. Populate Attendance (30 hari terakhir)
        for employee in employees:
            for day in range(30):
                tanggal = now - timedelta(days=day)
                rand = random.random()
                
                if rand < 0.90:  # 90% hadir
                    jam_masuk = f"{random.randint(7, 9):02d}:{random.randint(0, 59):02d}"
                    jam_pulang = f"{random.randint(16, 18):02d}:{random.randint(0, 59):02d}"
                    status = "Hadir"
                elif rand < 0.95:  # 5% izin
                    jam_masuk = jam_pulang = ""
                    status = "Izin"
                else:  # 5% alpha
                    jam_masuk = jam_pulang = ""
                    status = "Alpha"
                
                c.execute("""
                    INSERT INTO attendance (employee_id, tanggal, jam_masuk, jam_pulang, shift, status, catatan, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (employee['id'], format_date(tanggal), jam_masuk, jam_pulang, employee['shift'], status, "", "system"))
        
        # 4. Populate Wash Transactions (100 transaksi)
        c.execute("SELECT setting_value FROM settings WHERE setting_key = 'ukuran_multiplier'")
        result = c.fetchone()
        ukuran_multiplier = json.loads(result[0]) if result else {"Kecil": 1.0, "Sedang": 1.2, "Besar": 1.5, "Extra Besar": 2.0}
        
        transactions = []
        for i in range(100):
            customer = random.choice(customers)
            days_ago = random.randint(0, 60)
            tanggal = now - timedelta(days=days_ago)
            
            jam_masuk = f"{random.randint(8, 20):02d}:{random.randint(0, 59):02d}"
            waktu_selesai = f"{random.randint(10, 21):02d}:{random.randint(0, 59):02d}"
            
            paket = random.choice(list(PAKET_CUCIAN.keys()))
            harga_base = PAKET_CUCIAN[paket]
            multiplier = ukuran_multiplier.get(customer['ukuran'], 1.0)
            harga = int(harga_base * multiplier)
            
            status = "Selesai" if days_ago > 0 or random.random() > 0.05 else "Dalam Proses"
            
            c.execute("""
                INSERT INTO wash_transactions (nopol, nama_customer, tanggal, waktu_masuk, waktu_selesai,
                                              paket_cuci, harga, jenis_kendaraan, merk_kendaraan, ukuran_mobil,
                                              checklist_datang, checklist_selesai, qc_barang, catatan, status, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (customer['nopol'], customer['nama'], format_date(tanggal), jam_masuk, waktu_selesai,
                  paket, harga, customer['jenis_kendaraan'], customer['merk'], customer['ukuran'],
                  json.dumps(DEFAULT_CHECKLIST_DATANG), json.dumps(DEFAULT_CHECKLIST_SELESAI),
                  "OK", "", status, "admin"))
            
            if status == "Selesai":
                transactions.append({
                    'id': c.lastrowid, 'nopol': customer['nopol'], 'nama': customer['nama'],
                    'no_telp': customer['no_telp'], 'tanggal': tanggal, 'paket': paket, 'harga': harga
                })
        
        # 5. Populate Kasir Transactions & Reviews
        for trans in transactions:
            # Generate coffee items (30% chance)
            has_coffee = random.random() < 0.3
            coffee_items = []
            harga_coffee = 0
            
            if has_coffee:
                for _ in range(random.randint(1, 2)):
                    item_name = random.choice(list(DEFAULT_COFFEE_MENU.keys()))
                    price = DEFAULT_COFFEE_MENU[item_name]
                    qty = random.randint(1, 2)
                    coffee_items.append({'nama': item_name, 'harga': price, 'qty': qty, 'subtotal': price * qty})
                    harga_coffee += price * qty
            
            total_bayar = trans['harga'] + harga_coffee
            secret_code = generate_secret_code()
            
            c.execute("""
                INSERT INTO kasir_transactions (nopol, nama_customer, no_telp, tanggal, waktu,
                                               wash_trans_id, paket_cuci, harga_cuci, coffee_items, harga_coffee, 
                                               total_bayar, status_bayar, metode_bayar, secret_code, created_by, catatan)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (trans['nopol'], trans['nama'], trans['no_telp'], format_date(trans['tanggal']), "12:00",
                  trans['id'], trans['paket'], trans['harga'], json.dumps(coffee_items) if coffee_items else None,
                  harga_coffee, total_bayar, "Lunas", random.choice(METODE_BAYAR), secret_code, "kasir", ""))
            
            kasir_id = c.lastrowid
            
            # Add review (50% chance)
            if random.random() < 0.5:
                rating = random.choices([3, 4, 5], weights=[10, 40, 50])[0]
                reward_points = rating * 10
                review_date = trans['tanggal'] + timedelta(days=random.randint(0, 2))
                
                c.execute("""
                    INSERT INTO customer_reviews (secret_code, trans_id, trans_type, nopol, no_telp,
                                                 nama_customer, rating, review_text, review_date, review_time, reward_points)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (secret_code, kasir_id, "kasir", trans['nopol'], trans['no_telp'], trans['nama'],
                      rating, random.choice(REVIEW_TEXTS), format_date(review_date), "14:00", reward_points))
                
                # Update customer points
                c.execute("""
                    INSERT INTO customer_points (nopol, no_telp, nama_customer, total_points, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(nopol, no_telp) DO UPDATE SET 
                        total_points = total_points + ?,
                        last_updated = ?
                """, (trans['nopol'], trans['no_telp'], trans['nama'], reward_points, format_datetime(now),
                      reward_points, format_datetime(now)))
        
        # 6. Populate Coffee Sales (50 transaksi standalone)
        for i in range(50):
            days_ago = random.randint(0, 60)
            tanggal = now - timedelta(days=days_ago)
            waktu = f"{random.randint(8, 20):02d}:{random.randint(0, 59):02d}"
            
            items = []
            total = 0
            for _ in range(random.randint(1, 3)):
                item_name = random.choice(list(DEFAULT_COFFEE_MENU.keys()))
                price = DEFAULT_COFFEE_MENU[item_name]
                qty = random.randint(1, 2)
                items.append({'nama': item_name, 'harga': price, 'qty': qty, 'subtotal': price * qty})
                total += price * qty
            
            c.execute("""
                INSERT INTO coffee_sales (items, total, tanggal, waktu, nama_customer, no_telp, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (json.dumps(items), total, format_date(tanggal), waktu, None, None, "kasir"))
        
        # 7. Populate Payroll (3 bulan terakhir dengan data lengkap)
        # Load shift settings untuk persentase
        c.execute("SELECT shift_name, persentase_gaji FROM shift_settings")
        shift_percentages = dict(c.fetchall())
        
        payroll_records = []
        for month_offset in range(3):
            # Tentukan periode (mingguan, 4 minggu per bulan = 12 payroll per karyawan)
            for week in range(4):
                # Periode 7 hari
                week_start = now - timedelta(days=(month_offset * 30 + week * 7))
                week_end = week_start + timedelta(days=6)
                
                for employee in employees:
                    # Hitung hari kerja dari attendance dalam periode ini
                    # Simulasi: 5-6 hari kerja per minggu (weekend kadang masuk)
                    hari_kerja = random.randint(5, 6)
                    
                    # Hitung gaji berdasarkan role
                    if employee['role'] in ['Kasir', 'Supervisor']:
                        # Gaji tetap per minggu
                        total_gaji = employee['gaji']
                    else:
                        # Worker - simulasi berdasarkan pendapatan
                        # Asumsi pendapatan per hari: 500k - 1.5jt
                        daily_revenue = random.randint(500000, 1500000)
                        shift_pct = shift_percentages.get(employee['shift'], 35.0) / 100
                        total_gaji = int(daily_revenue * shift_pct * hari_kerja)
                    
                    # Bonus random (0-200k)
                    bonus = random.randint(0, 4) * 50000
                    
                    # Potongan random (0-100k)
                    potongan = random.randint(0, 2) * 50000
                    
                    gaji_bersih = total_gaji + bonus - potongan
                    
                    # Status: Lunas untuk minggu lalu, Pending untuk minggu ini
                    if month_offset == 0 and week == 0:
                        status = "Pending"
                        tanggal_bayar = None
                    else:
                        status = "Lunas"
                        # Tanggal bayar: 2 hari setelah periode berakhir
                        tanggal_bayar = week_end + timedelta(days=2)
                    
                    c.execute("""
                        INSERT INTO payroll (employee_id, periode_awal, periode_akhir, total_hari_kerja,
                                            total_gaji, bonus, potongan, gaji_bersih, status, 
                                            tanggal_bayar, catatan, created_at, created_by)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (employee['id'], format_date(week_start), format_date(week_end), 
                          hari_kerja, total_gaji, bonus, potongan, gaji_bersih, status,
                          format_date(tanggal_bayar) if tanggal_bayar else None,
                          f"Periode {format_date(week_start)} - {format_date(week_end)}",
                          format_datetime(now), "admin"))
                    
                    payroll_records.append({
                        'employee_id': employee['id'],
                        'payroll_id': c.lastrowid,
                        'tanggal_bayar': tanggal_bayar
                    })
        
        # 8. Populate Kas Bon (detail dengan multiple pembayaran)
        kas_bon_records = []
        keterangan_kasbon = [
            "Keperluan mendesak keluarga",
            "Biaya pengobatan",
            "Keperluan sekolah anak",
            "Renovasi rumah",
            "Bayar hutang lain",
            "Modal usaha sampingan",
            "Keperluan hajatan"
        ]
        
        for employee in employees:
            # 50% chance karyawan punya kas bon
            num_kasbon = random.choices([0, 1, 2], weights=[50, 40, 10])[0]
            
            for kb_idx in range(num_kasbon):
                # Tanggal pinjam: 30-90 hari yang lalu
                days_ago_kasbon = random.randint(30, 90)
                tanggal_kasbon = now - timedelta(days=days_ago_kasbon)
                
                # Jumlah pinjaman: 200k - 1jt
                jumlah_kasbon = random.randint(4, 20) * 50000
                
                keterangan = random.choice(keterangan_kasbon)
                
                c.execute("""
                    INSERT INTO kas_bon (employee_id, tanggal, jumlah, keterangan, status, sisa_hutang, created_at, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (employee['id'], format_date(tanggal_kasbon), jumlah_kasbon, 
                      keterangan, "Belum Lunas", jumlah_kasbon, format_datetime(tanggal_kasbon), "admin"))
                
                kas_bon_id = c.lastrowid
                kas_bon_records.append({
                    'id': kas_bon_id,
                    'employee_id': employee['id'],
                    'jumlah': jumlah_kasbon,
                    'tanggal_kasbon': tanggal_kasbon,
                    'sisa_hutang': jumlah_kasbon
                })
                
                # Simulate pembayaran cicilan (2-5 cicilan)
                num_cicilan = random.randint(2, 5)
                sisa_hutang_current = jumlah_kasbon
                
                for cicilan_idx in range(num_cicilan):
                    if sisa_hutang_current <= 0:
                        break
                    
                    # Jumlah bayar: 20-50% dari sisa hutang
                    if cicilan_idx == num_cicilan - 1:
                        # Cicilan terakhir: bayar sisa
                        jumlah_bayar = sisa_hutang_current
                    else:
                        max_bayar = int(sisa_hutang_current * 0.5)
                        min_bayar = min(50000, sisa_hutang_current)
                        jumlah_bayar = random.randint(min_bayar, max(min_bayar, max_bayar))
                        jumlah_bayar = (jumlah_bayar // 10000) * 10000  # Round to 10k
                    
                    # Tanggal bayar: 1-2 minggu setelah kas bon / cicilan sebelumnya
                    days_after = random.randint(7, 14) * (cicilan_idx + 1)
                    tanggal_bayar_kasbon = tanggal_kasbon + timedelta(days=days_after)
                    
                    # Hanya tambahkan pembayaran jika belum melewati hari ini
                    if tanggal_bayar_kasbon <= now.date():
                        metode_bayar = random.choices(
                            ["Potong Gaji", "Tunai", "Transfer"],
                            weights=[70, 20, 10]
                        )[0]
                        
                        # Link ke payroll jika metode potong gaji
                        payroll_id_link = None
                        if metode_bayar == "Potong Gaji":
                            # Cari payroll yang tanggal bayarnya dekat dengan tanggal bayar kas bon
                            matching_payroll = [
                                pr for pr in payroll_records 
                                if pr['employee_id'] == employee['id'] 
                                and pr['tanggal_bayar'] 
                                and abs((pr['tanggal_bayar'].date() if hasattr(pr['tanggal_bayar'], 'date') else pr['tanggal_bayar']) - tanggal_bayar_kasbon).days <= 3
                            ]
                            if matching_payroll:
                                payroll_id_link = matching_payroll[0]['payroll_id']
                        
                        c.execute("""
                            INSERT INTO pembayaran_kas_bon (kas_bon_id, payroll_id, tanggal_bayar, jumlah_bayar, metode, keterangan, created_at, created_by)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (kas_bon_id, payroll_id_link, format_date(tanggal_bayar_kasbon), jumlah_bayar, 
                              metode_bayar, f"Cicilan ke-{cicilan_idx + 1}", format_datetime(tanggal_bayar_kasbon), "admin"))
                        
                        sisa_hutang_current -= jumlah_bayar
                        
                        # Update sisa hutang di kas_bon
                        c.execute("""
                            UPDATE kas_bon SET sisa_hutang = ? WHERE id = ?
                        """, (sisa_hutang_current, kas_bon_id))
                        
                        # Update status jika lunas
                        if sisa_hutang_current <= 0:
                            c.execute("""
                                UPDATE kas_bon SET status = 'Lunas' WHERE id = ?
                            """, (kas_bon_id,))
                            break
        
        # 9. Add Audit Trail
        c.execute("""
            INSERT INTO audit_trail (timestamp, user, action, detail)
            VALUES (?, ?, ?, ?)
        """, (format_datetime(now), "admin", "Populate Data", "Data dummy berhasil di-generate"))
        
        conn.commit()
        
        # Count all records
        c.execute("SELECT COUNT(*) FROM kas_bon")
        kasbon_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM kas_bon WHERE status = 'Lunas'")
        kasbon_lunas = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM payroll")
        payroll_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM pembayaran_kas_bon")
        pembayaran_count = c.fetchone()[0]
        
        return True, f"""✅ Data dummy berhasil dibuat!
📊 Summary:
- {len(customers)} pelanggan
- {len(employees)} karyawan
- {len(transactions)} transaksi cuci
- {payroll_count} slip gaji ({len(employees)} karyawan x 12 periode)
- {kasbon_count} kas bon ({kasbon_lunas} lunas, {kasbon_count - kasbon_lunas} belum lunas)
- {pembayaran_count} pembayaran kas bon"""
        
    except Exception as e:
        conn.rollback()
        return False, f"Error populate data: {str(e)}"
    finally:
        conn.close()


# --- Simpan & Load Customer ---
def save_customer(nopol, nama, telp, jenis_kendaraan='', merk_kendaraan='', ukuran_mobil=''):
    """Simpan data customer baru"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    now_wib = datetime.now(WIB)
    try:
        c.execute("""
            INSERT INTO customers (nopol, nama_customer, no_telp, jenis_kendaraan, merk_kendaraan, ukuran_mobil, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (nopol.upper(), nama, telp, jenis_kendaraan, merk_kendaraan, ukuran_mobil, now_wib.strftime("%d-%m-%Y %H:%M:%S")))
        conn.commit()
        return True, "Customer berhasil ditambahkan"
    except sqlite3.IntegrityError:
        return False, "Nopol sudah terdaftar"
    except Exception as e:
        return False, f"Error: {str(e)}"
    finally:
        conn.close()

def get_customer_by_nopol(nopol):
    """Ambil data customer berdasarkan nopol"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM customers WHERE nopol = ?", (nopol.upper(),))
    result = c.fetchone()
    conn.close()
    if result:
        return {
            'id': result[0],
            'nopol': result[1],
            'nama_customer': result[2],
            'no_telp': result[3],
            'jenis_kendaraan': result[4] if len(result) > 4 else '',
            'merk_kendaraan': result[5] if len(result) > 5 else '',
            'ukuran_mobil': result[6] if len(result) > 6 else '',
            'created_at': result[7] if len(result) > 7 else result[4]
        }
    return None

def get_all_customers():
    """Ambil semua data customer"""
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql("SELECT * FROM customers ORDER BY created_at DESC", conn)
    conn.close()
    return df

# --- Simpan & Load Transaksi ---
def save_transaction(data):
    """Simpan transaksi cuci mobil"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO wash_transactions 
            (nopol, nama_customer, tanggal, waktu_masuk, waktu_selesai, paket_cuci, harga, 
             jenis_kendaraan, merk_kendaraan, ukuran_mobil,
             checklist_datang, checklist_selesai, qc_barang, catatan, status, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['nopol'].upper(),
            data['nama_customer'],
            data['tanggal'],
            data['waktu_masuk'],
            data.get('waktu_selesai', ''),
            data['paket_cuci'],
            data['harga'],
            data.get('jenis_kendaraan', ''),
            data.get('merk_kendaraan', ''),
            data.get('ukuran_mobil', ''),
            data.get('checklist_datang', ''),
            data.get('checklist_selesai', ''),
            data.get('qc_barang', ''),
            data.get('catatan', ''),
            data.get('status', 'Dalam Proses'),
            data.get('created_by', '')
        ))
        conn.commit()
        return True, "Transaksi berhasil disimpan"
    except Exception as e:
        return False, f"Error: {str(e)}"
    finally:
        conn.close()

def update_transaction_finish(trans_id, waktu_selesai, checklist_selesai, qc_barang, catatan):
    """Update transaksi saat selesai cuci"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        # Pastikan trans_id adalah integer
        trans_id = int(trans_id)
        
        # Cek status dulu dengan logging
        c.execute("SELECT id, status, nopol FROM wash_transactions WHERE id = ?", (trans_id,))
        result = c.fetchone()
        
        if not result:
            # Debug: cek semua ID yang ada
            c.execute("SELECT id, nopol, status FROM wash_transactions")
            all_trans = c.fetchall()
            print(f"DEBUG: Mencari ID {trans_id} (tipe: {type(trans_id)})")
            print(f"DEBUG: IDs yang ada di database: {[row[0] for row in all_trans]}")
            return False, f"Transaksi ID {trans_id} tidak ditemukan di database"
        
        current_status = result[1].strip()
        print(f"DEBUG: Transaksi ditemukan - ID: {result[0]}, Status: '{current_status}', Nopol: {result[2]}")
        
        if current_status != 'Dalam Proses':
            return False, f"Transaksi berstatus '{current_status}', tidak bisa diselesaikan"
        
        # Update status menjadi 'Selesai'
        c.execute("""
            UPDATE wash_transactions 
            SET waktu_selesai = ?, checklist_selesai = ?, qc_barang = ?, 
                catatan = ?, status = 'Selesai'
            WHERE id = ?
        """, (waktu_selesai, checklist_selesai, qc_barang, catatan, trans_id))
        
        conn.commit()
        print(f"DEBUG: Update berhasil untuk ID {trans_id}")
        return True, "Transaksi berhasil diselesaikan"
        
    except Exception as e:
        print(f"DEBUG ERROR: {str(e)}")
        return False, f"Error: {str(e)}"
    finally:
        conn.close()

def get_all_transactions():
    """Ambil semua transaksi"""
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql("SELECT * FROM wash_transactions ORDER BY tanggal DESC, waktu_masuk DESC", conn)
    conn.close()
    return df

def get_transactions_by_date_range(start_date, end_date):
    """Ambil transaksi dalam rentang tanggal"""
    conn = sqlite3.connect(DB_NAME)
    query = """
        SELECT * FROM wash_transactions 
        WHERE tanggal BETWEEN ? AND ?
        ORDER BY tanggal DESC, waktu_masuk DESC
    """
    df = pd.read_sql(query, conn, params=(start_date, end_date))
    conn.close()
    return df

# --- Settings Functions ---
def get_setting(key):
    """Ambil setting berdasarkan key"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT setting_value FROM settings WHERE setting_key = ?", (key,))
    result = c.fetchone()
    conn.close()
    if result:
        try:
            return json.loads(result[0])
        except:
            return result[0]
    return None

def update_setting(key, value):
    """Update setting"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    now = datetime.now(WIB).strftime("%d-%m-%Y %H:%M:%S")
    try:
        value_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        c.execute("""
            INSERT OR REPLACE INTO settings (setting_key, setting_value, updated_at)
            VALUES (?, ?, ?)
        """, (key, value_str, now))
        conn.commit()
        return True, "Setting berhasil diupdate"
    except Exception as e:
        return False, f"Error: {str(e)}"
    finally:
        conn.close()

def get_paket_cucian():
    """Ambil daftar paket cucian dari database"""
    paket = get_setting("paket_cucian")
    return paket if paket else PAKET_CUCIAN

def get_checklist_datang():
    """Ambil checklist datang dari database"""
    checklist = get_setting("checklist_datang")
    return checklist if checklist else DEFAULT_CHECKLIST_DATANG

def get_checklist_selesai():
    """Ambil checklist selesai dari database"""
    checklist = get_setting("checklist_selesai")
    return checklist if checklist else DEFAULT_CHECKLIST_SELESAI

def get_toko_info():
    """Ambil informasi toko dari database"""
    toko = get_setting("toko_info")
    if toko:
        return toko
    # Default fallback
    return {
        "nama": "TIME AUTOCARE",
        "tagline": "Detailing & Ceramic Coating",
        "alamat": "Jl. Contoh No. 123",
        "telp": "08123456789",
        "email": "info@timeautocare.com"
    }

def get_ukuran_multiplier():
    """Ambil multiplier harga berdasarkan ukuran mobil"""
    multiplier = get_setting("ukuran_multiplier")
    if multiplier:
        return multiplier
    # Default multiplier
    return {
        "Kecil": 1.0,
        "Sedang": 1.2,
        "Besar": 1.5,
        "Extra Besar": 2.0
    }


# ========== PAYROLL FUNCTIONS ==========

def get_all_employees():
    """Get all employees"""
    conn = sqlite3.connect('car_wash.db')
    c = conn.cursor()
    c.execute("SELECT * FROM employees ORDER BY id DESC")
    employees = [dict(zip([column[0] for column in c.description], row)) for row in c.fetchall()]
    conn.close()
    return employees

def add_employee(nama, role_karyawan, gaji_tetap, shift, jam_masuk_default, jam_pulang_default, no_telp, created_by):
    """Add new employee"""
    conn = sqlite3.connect('car_wash.db')
    c = conn.cursor()
    now = datetime.now(WIB).strftime("%d-%m-%Y %H:%M:%S")
    c.execute("""
        INSERT INTO employees (nama, role_karyawan, gaji_tetap, shift, jam_masuk_default, jam_pulang_default, status, no_telp, created_at, created_by)
        VALUES (?, ?, ?, ?, ?, ?, 'Aktif', ?, ?, ?)
    """, (nama, role_karyawan, gaji_tetap, shift, jam_masuk_default, jam_pulang_default, no_telp, now, created_by))
    conn.commit()
    conn.close()

def update_employee(emp_id, nama, role_karyawan, gaji_tetap, shift, jam_masuk_default, jam_pulang_default, no_telp, status):
    """Update employee data"""
    conn = sqlite3.connect('car_wash.db')
    c = conn.cursor()
    c.execute("""
        UPDATE employees 
        SET nama=?, role_karyawan=?, gaji_tetap=?, shift=?, jam_masuk_default=?, jam_pulang_default=?, no_telp=?, status=?
        WHERE id=?
    """, (nama, role_karyawan, gaji_tetap, shift, jam_masuk_default, jam_pulang_default, no_telp, status, emp_id))
    conn.commit()
    conn.close()

def delete_employee(emp_id):
    """Delete employee"""
    conn = sqlite3.connect('car_wash.db')
    c = conn.cursor()
    c.execute("DELETE FROM employees WHERE id=?", (emp_id,))
    conn.commit()
    conn.close()

def update_customer(nopol, nama, telp, jenis_kendaraan='', merk_kendaraan='', ukuran_mobil=''):
    """Update customer data"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("""
            UPDATE customers 
            SET nama_customer=?, no_telp=?, jenis_kendaraan=?, merk_kendaraan=?, ukuran_mobil=?
            WHERE nopol=?
        """, (nama, telp, jenis_kendaraan, merk_kendaraan, ukuran_mobil, nopol.upper()))
        conn.commit()
        return True, "Customer berhasil diupdate"
    except Exception as e:
        return False, f"Error: {str(e)}"
    finally:
        conn.close()

def delete_customer(nopol):
    """Delete customer"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        # Check if customer has transactions
        c.execute("SELECT COUNT(*) FROM wash_transactions WHERE nopol=?", (nopol.upper(),))
        trans_count = c.fetchone()[0]
        
        if trans_count > 0:
            return False, f"Tidak dapat menghapus customer. Ada {trans_count} transaksi terkait."
        
        c.execute("DELETE FROM customers WHERE nopol=?", (nopol.upper(),))
        conn.commit()
        return True, "Customer berhasil dihapus"
    except Exception as e:
        return False, f"Error: {str(e)}"
    finally:
        conn.close()

def delete_wash_transaction(trans_id):
    """Delete wash transaction"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        # Check if already in kasir
        c.execute("SELECT COUNT(*) FROM kasir_transactions WHERE wash_trans_id=?", (trans_id,))
        kasir_count = c.fetchone()[0]
        
        if kasir_count > 0:
            return False, "Tidak dapat menghapus transaksi yang sudah masuk kasir."
        
        c.execute("DELETE FROM wash_transactions WHERE id=?", (trans_id,))
        conn.commit()
        return True, "Transaksi berhasil dihapus"
    except Exception as e:
        return False, f"Error: {str(e)}"
    finally:
        conn.close()

def update_wash_transaction(trans_id, paket_cuci, harga, catatan):
    """Update wash transaction"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("""
            UPDATE wash_transactions 
            SET paket_cuci=?, harga=?, catatan=?
            WHERE id=?
        """, (paket_cuci, harga, catatan, trans_id))
        conn.commit()
        return True, "Transaksi berhasil diupdate"
    except Exception as e:
        return False, f"Error: {str(e)}"
    finally:
        conn.close()

def delete_kasir_transaction(trans_id):
    """Delete kasir transaction"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("DELETE FROM kasir_transactions WHERE id=?", (trans_id,))
        conn.commit()
        return True, "Transaksi kasir berhasil dihapus"
    except Exception as e:
        return False, f"Error: {str(e)}"
    finally:
        conn.close()

def delete_attendance(attendance_id):
    """Delete attendance record"""
    conn = sqlite3.connect('car_wash.db')
    c = conn.cursor()
    try:
        c.execute("DELETE FROM attendance WHERE id=?", (attendance_id,))
        conn.commit()
        return True, "Presensi berhasil dihapus"
    except Exception as e:
        return False, f"Error: {str(e)}"
    finally:
        conn.close()

def get_shift_settings():
    """Get shift settings"""
    conn = sqlite3.connect('car_wash.db')
    c = conn.cursor()
    c.execute("SELECT * FROM shift_settings")
    shifts = [dict(zip([column[0] for column in c.description], row)) for row in c.fetchall()]
    conn.close()
    return shifts

def update_shift_settings(shift_name, jam_mulai, jam_selesai, persentase):
    """Update shift settings"""
    conn = sqlite3.connect('car_wash.db')
    c = conn.cursor()
    now = datetime.now(WIB).strftime("%d-%m-%Y %H:%M:%S")
    c.execute("""
        UPDATE shift_settings 
        SET jam_mulai=?, jam_selesai=?, persentase_gaji=?, updated_at=?
        WHERE shift_name=?
    """, (jam_mulai, jam_selesai, persentase, now, shift_name))
    conn.commit()
    conn.close()

def add_attendance(employee_id, tanggal, jam_masuk, jam_pulang, shift, status, catatan, created_by):
    """Add attendance record"""
    conn = sqlite3.connect('car_wash.db')
    c = conn.cursor()
    c.execute("""
        INSERT INTO attendance (employee_id, tanggal, jam_masuk, jam_pulang, shift, status, catatan, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (employee_id, tanggal, jam_masuk, jam_pulang, shift, status, catatan, created_by))
    conn.commit()
    conn.close()

def get_attendance_by_date_range(start_date, end_date):
    """Get attendance records by date range"""
    conn = sqlite3.connect('car_wash.db')
    c = conn.cursor()
    c.execute("""
        SELECT a.*, e.nama, e.role_karyawan
        FROM attendance a
        JOIN employees e ON a.employee_id = e.id
        WHERE a.tanggal BETWEEN ? AND ?
        ORDER BY a.tanggal DESC, a.jam_masuk DESC
    """, (start_date, end_date))
    attendance = [dict(zip([column[0] for column in c.description], row)) for row in c.fetchall()]
    conn.close()
    return attendance

def get_wash_revenue_by_time_range(start_datetime, end_datetime):
    """Get total WASH revenue between datetime range (excludes coffee shop)"""
    conn = sqlite3.connect('car_wash.db')
    c = conn.cursor()
    
    # Query untuk mendapatkan total pendapatan CUCI MOBIL saja (tanpa coffee)
    # Hanya dari wash_transactions, bukan dari kasir_transactions coffee
    c.execute("""
        SELECT COALESCE(SUM(harga), 0) as total
        FROM wash_transactions
        WHERE datetime(substr(tanggal, 7, 4) || '-' || substr(tanggal, 4, 2) || '-' || substr(tanggal, 1, 2) || ' ' || waktu_masuk) 
        BETWEEN ? AND ?
    """, (start_datetime, end_datetime))
    
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def calculate_worker_salary(employee_id, tanggal, jam_masuk, jam_pulang, shift):
    """Calculate salary for worker based on actual working hours"""
    # Get shift settings
    shifts = get_shift_settings()
    shift_data = next((s for s in shifts if s['shift_name'] == shift), None)
    
    if not shift_data:
        return 0
    
    persentase = shift_data['persentase_gaji'] / 100
    
    # Convert strings to datetime for calculation
    try:
        tanggal_obj = datetime.strptime(tanggal, "%d-%m-%Y")
        jam_masuk_obj = datetime.strptime(jam_masuk, "%H:%M")
        
        if jam_pulang:
            jam_pulang_obj = datetime.strptime(jam_pulang, "%H:%M")
        else:
            # Jika belum pulang, gunakan waktu sekarang
            jam_pulang_obj = datetime.now(WIB)
        
        # Gabungkan tanggal dan jam
        datetime_masuk = datetime.combine(tanggal_obj.date(), jam_masuk_obj.time())
        datetime_pulang = datetime.combine(tanggal_obj.date(), jam_pulang_obj.time())
        
        # Jika shift malam dan jam pulang lebih kecil, tambah 1 hari
        if shift == "Malam" and jam_pulang_obj.time() < jam_masuk_obj.time():
            datetime_pulang = datetime_pulang + timedelta(days=1)
        
        # Format untuk query
        start_str = datetime_masuk.strftime("%Y-%m-%d %H:%M:%S")
        end_str = datetime_pulang.strftime("%Y-%m-%d %H:%M:%S")
        
        # Get revenue dalam periode kerja
        revenue = get_wash_revenue_by_time_range(start_str, end_str)
        
        # Calculate salary
        salary = int(revenue * persentase)
        return salary
        
    except Exception as e:
        st.error(f"Error calculating salary: {e}")
        return 0

def add_payroll(employee_id, periode_awal, periode_akhir, total_hari_kerja, total_gaji, bonus, potongan, gaji_bersih, status, tanggal_bayar, catatan, created_by):
    """Add payroll record"""
    conn = sqlite3.connect('car_wash.db')
    c = conn.cursor()
    now = datetime.now(WIB).strftime("%d-%m-%Y %H:%M:%S")
    c.execute("""
        INSERT INTO payroll (employee_id, periode_awal, periode_akhir, total_hari_kerja, total_gaji, bonus, potongan, gaji_bersih, status, tanggal_bayar, catatan, created_at, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (employee_id, periode_awal, periode_akhir, total_hari_kerja, total_gaji, bonus, potongan, gaji_bersih, status, tanggal_bayar, catatan, now, created_by))
    conn.commit()
    conn.close()

def get_payroll_history(employee_id=None):
    """Get payroll history"""
    conn = sqlite3.connect('car_wash.db')
    c = conn.cursor()
    
    if employee_id:
        c.execute("""
            SELECT p.*, e.nama, e.role_karyawan
            FROM payroll p
            JOIN employees e ON p.employee_id = e.id
            WHERE p.employee_id = ?
            ORDER BY p.created_at DESC
        """, (employee_id,))
    else:
        c.execute("""
            SELECT p.*, e.nama, e.role_karyawan
            FROM payroll p
            JOIN employees e ON p.employee_id = e.id
            ORDER BY p.created_at DESC
        """)
    
    payroll = [dict(zip([column[0] for column in c.description], row)) for row in c.fetchall()]
    conn.close()
    return payroll

def update_payroll_status(payroll_id, status, tanggal_bayar):
    """Update payroll status"""
    conn = sqlite3.connect('car_wash.db')
    c = conn.cursor()
    c.execute("""
        UPDATE payroll 
        SET status=?, tanggal_bayar=?
        WHERE id=?
    """, (status, tanggal_bayar, payroll_id))
    conn.commit()
    conn.close()


# ========== KAS BON FUNCTIONS ==========

def add_kas_bon(employee_id, tanggal, jumlah, keterangan, created_by):
    """Add new kas bon record"""
    conn = sqlite3.connect('car_wash.db')
    c = conn.cursor()
    now = datetime.now(WIB).strftime("%d-%m-%Y %H:%M:%S")
    c.execute("""
        INSERT INTO kas_bon (employee_id, tanggal, jumlah, keterangan, status, sisa_hutang, created_at, created_by)
        VALUES (?, ?, ?, ?, 'Belum Lunas', ?, ?, ?)
    """, (employee_id, tanggal, jumlah, keterangan, jumlah, now, created_by))
    conn.commit()
    conn.close()

def get_kas_bon_by_employee(employee_id, status_filter=None):
    """Get kas bon records by employee"""
    conn = sqlite3.connect('car_wash.db')
    c = conn.cursor()
    
    if status_filter:
        c.execute("""
            SELECT kb.*, e.nama, e.role_karyawan
            FROM kas_bon kb
            JOIN employees e ON kb.employee_id = e.id
            WHERE kb.employee_id = ? AND kb.status = ?
            ORDER BY kb.tanggal DESC
        """, (employee_id, status_filter))
    else:
        c.execute("""
            SELECT kb.*, e.nama, e.role_karyawan
            FROM kas_bon kb
            JOIN employees e ON kb.employee_id = e.id
            WHERE kb.employee_id = ?
            ORDER BY kb.tanggal DESC
        """, (employee_id,))
    
    kas_bon = [dict(zip([column[0] for column in c.description], row)) for row in c.fetchall()]
    conn.close()
    return kas_bon

def get_all_kas_bon(status_filter=None):
    """Get all kas bon records"""
    conn = sqlite3.connect('car_wash.db')
    c = conn.cursor()
    
    if status_filter:
        c.execute("""
            SELECT kb.*, e.nama, e.role_karyawan
            FROM kas_bon kb
            JOIN employees e ON kb.employee_id = e.id
            WHERE kb.status = ?
            ORDER BY kb.tanggal DESC
        """, (status_filter,))
    else:
        c.execute("""
            SELECT kb.*, e.nama, e.role_karyawan
            FROM kas_bon kb
            JOIN employees e ON kb.employee_id = e.id
            ORDER BY kb.tanggal DESC
        """)
    
    kas_bon = [dict(zip([column[0] for column in c.description], row)) for row in c.fetchall()]
    conn.close()
    return kas_bon

def get_total_hutang_by_employee(employee_id):
    """Get total hutang belum lunas by employee"""
    conn = sqlite3.connect('car_wash.db')
    c = conn.cursor()
    c.execute("""
        SELECT COALESCE(SUM(sisa_hutang), 0)
        FROM kas_bon
        WHERE employee_id = ? AND status = 'Belum Lunas'
    """, (employee_id,))
    total = c.fetchone()[0]
    conn.close()
    return total

def add_pembayaran_kas_bon(kas_bon_id, payroll_id, tanggal_bayar, jumlah_bayar, metode, keterangan, created_by):
    """Add pembayaran kas bon and update sisa hutang"""
    conn = sqlite3.connect('car_wash.db')
    c = conn.cursor()
    now = datetime.now(WIB).strftime("%d-%m-%Y %H:%M:%S")
    
    try:
        # Insert pembayaran
        c.execute("""
            INSERT INTO pembayaran_kas_bon (kas_bon_id, payroll_id, tanggal_bayar, jumlah_bayar, metode, keterangan, created_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (kas_bon_id, payroll_id, tanggal_bayar, jumlah_bayar, metode, keterangan, now, created_by))
        
        # Update sisa hutang di kas_bon
        c.execute("""
            UPDATE kas_bon
            SET sisa_hutang = sisa_hutang - ?
            WHERE id = ?
        """, (jumlah_bayar, kas_bon_id))
        
        # Update status jika sudah lunas
        c.execute("""
            UPDATE kas_bon
            SET status = CASE 
                WHEN sisa_hutang <= 0 THEN 'Lunas'
                ELSE 'Belum Lunas'
            END
            WHERE id = ?
        """, (kas_bon_id,))
        
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        return False
    finally:
        conn.close()

def get_pembayaran_kas_bon(kas_bon_id):
    """Get pembayaran history for specific kas bon"""
    conn = sqlite3.connect('car_wash.db')
    c = conn.cursor()
    c.execute("""
        SELECT * FROM pembayaran_kas_bon
        WHERE kas_bon_id = ?
        ORDER BY tanggal_bayar DESC
    """, (kas_bon_id,))
    pembayaran = [dict(zip([column[0] for column in c.description], row)) for row in c.fetchall()]
    conn.close()
    return pembayaran

def delete_kas_bon(kas_bon_id):
    """Delete kas bon and related pembayaran"""
    conn = sqlite3.connect('car_wash.db')
    c = conn.cursor()
    try:
        # Delete pembayaran first (foreign key constraint)
        c.execute("DELETE FROM pembayaran_kas_bon WHERE kas_bon_id = ?", (kas_bon_id,))
        # Delete kas bon
        c.execute("DELETE FROM kas_bon WHERE id = ?", (kas_bon_id,))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        return False
    finally:
        conn.close()


# --- Coffee Shop Helpers ---
def get_coffee_menu():
    """Ambil daftar menu coffee/snack dari settings"""
    menu = get_setting("coffee_menu")
    return menu if menu else DEFAULT_COFFEE_MENU


def save_coffee_sale(data):
    """Simpan transaksi penjualan coffee/snack ke DB"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO coffee_sales (items, total, tanggal, waktu, nama_customer, no_telp, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            json.dumps(data.get('items', []), ensure_ascii=False),
            int(data.get('total', 0)),
            data.get('tanggal', ''),
            data.get('waktu', ''),
            data.get('nama_customer', ''),
            data.get('no_telp', ''),
            data.get('created_by', '')
        ))
        conn.commit()
        return True, "Penjualan Coffee berhasil disimpan"
    except Exception as e:
        return False, f"Error: {str(e)}"
    finally:
        conn.close()


def get_all_coffee_sales():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql("SELECT * FROM coffee_sales ORDER BY tanggal DESC, waktu DESC", conn)
    conn.close()
    return df

# --- Kasir Functions ---
def get_pending_wash_transactions():
    """Ambil transaksi cuci mobil yang belum dibayar (status 'Dalam Proses' atau 'Selesai')"""
    conn = sqlite3.connect(DB_NAME)
    # Cek transaksi yang belum ada di kasir_transactions
    query = """
        SELECT wt.* FROM wash_transactions wt
        LEFT JOIN kasir_transactions kt ON wt.id = kt.wash_trans_id
        WHERE kt.id IS NULL
        ORDER BY wt.tanggal DESC, wt.waktu_masuk DESC
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def save_kasir_transaction(data):
    """Simpan transaksi kasir (bisa gabungan cuci mobil + coffee atau hanya salah satu)"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        # Generate unique secret code
        secret_code = generate_secret_code()
        while True:
            # Check if code already exists
            c.execute("SELECT COUNT(*) FROM kasir_transactions WHERE secret_code = ?", (secret_code,))
            if c.fetchone()[0] == 0:
                break
            secret_code = generate_secret_code()
        
        c.execute("""
            INSERT INTO kasir_transactions 
            (nopol, nama_customer, no_telp, tanggal, waktu, wash_trans_id, paket_cuci, harga_cuci,
             coffee_items, harga_coffee, total_bayar, status_bayar, metode_bayar, created_by, catatan, secret_code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('nopol', '').upper(),
            data.get('nama_customer', ''),
            data.get('no_telp', ''),
            data.get('tanggal', ''),
            data.get('waktu', ''),
            data.get('wash_trans_id'),
            data.get('paket_cuci', ''),
            int(data.get('harga_cuci', 0)),
            data.get('coffee_items', ''),
            int(data.get('harga_coffee', 0)),
            int(data.get('total_bayar', 0)),
            data.get('status_bayar', 'Lunas'),
            data.get('metode_bayar', ''),
            data.get('created_by', ''),
            data.get('catatan', ''),
            secret_code
        ))
        
        # Jika ada transaksi coffee, simpan juga ke tabel coffee_sales untuk laporan terpisah
        if data.get('coffee_items') and data.get('harga_coffee', 0) > 0:
            c.execute("""
                INSERT INTO coffee_sales 
                (items, total, tanggal, waktu, nama_customer, no_telp, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get('coffee_items', ''),
                int(data.get('harga_coffee', 0)),
                data.get('tanggal', ''),
                data.get('waktu', ''),
                data.get('nama_customer', ''),
                data.get('no_telp', ''),
                data.get('created_by', '')
            ))
        
        conn.commit()
        return True, "Transaksi kasir berhasil disimpan", secret_code
    except Exception as e:
        return False, f"Error: {str(e)}", None
    finally:
        conn.close()

def get_all_kasir_transactions():
    """Ambil semua transaksi kasir"""
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql("SELECT * FROM kasir_transactions ORDER BY tanggal DESC, waktu DESC", conn)
    conn.close()
    return df

def generate_kasir_invoice(trans_data, toko_info):
    """Generate invoice kasir untuk WhatsApp (cuci mobil + coffee)"""
    # Parse coffee items jika ada
    coffee_detail = ""
    if trans_data.get('coffee_items'):
        try:
            items_list = json.loads(trans_data['coffee_items']) if isinstance(trans_data['coffee_items'], str) else trans_data['coffee_items']
            coffee_detail = '\n'.join([f"  {i['qty']}x {i['name']} @ Rp {i['price']:,.0f}" for i in items_list])
        except:
            coffee_detail = "N/A"
    
    # Build message
    message = f"""*{'='*35}*
   *INVOICE KASIR*
*{'='*35}*

*{toko_info.get('nama', 'TIME AUTOCARE')}*
_{toko_info.get('tagline', 'Detailing & Ceramic Coating')}_
Alamat: {toko_info.get('alamat', '')}
Telp: {toko_info.get('telp', '')}

*{'='*35}*
   *DETAIL TRANSAKSI*
*{'='*35}*

Customer: *{trans_data.get('nama_customer', '-')}*
No. Polisi: *{trans_data.get('nopol', '-')}*
Tanggal: {trans_data['tanggal']}
Waktu: {trans_data['waktu']}
Kasir: {trans_data.get('created_by', '-')}

*{'='*35}*"""

    # Tambahkan detail cuci mobil jika ada
    if trans_data.get('paket_cuci') and trans_data.get('harga_cuci', 0) > 0:
        message += f"""
   *CUCI MOBIL*
*{'='*35}*

Paket: {trans_data.get('paket_cuci', '-')}
Harga: Rp {trans_data.get('harga_cuci', 0):,.0f}

*{'='*35}*"""

    # Tambahkan detail coffee jika ada
    if coffee_detail:
        message += f"""
   *COFFEE SHOP*
*{'='*35}*

{coffee_detail}

Subtotal Coffee: Rp {trans_data.get('harga_coffee', 0):,.0f}

*{'='*35}*"""

    # Total pembayaran
    message += f"""

*TOTAL PEMBAYARAN:*
*Rp {trans_data.get('total_bayar', 0):,.0f}*

Metode: {trans_data.get('metode_bayar', 'Tunai')}
Status: {trans_data.get('status_bayar', 'Lunas')}

*{'='*35}*

_Terima kasih atas kunjungan Anda!_
_Kepuasan Anda adalah prioritas kami_

*🌟 BERIKAN REVIEW & DAPATKAN POIN! 🌟*

Kode Review Anda: *{trans_data.get('secret_code', 'N/A')}*

Akses: https://pp2trial.streamlit.app/
Masukkan kode di atas untuk memberikan review
dan dapatkan *10 poin reward*! 🎁

*Sampai jumpa lagi!* 

_Drive clean, stay fresh..._
"""
    
    return message

def generate_coffee_invoice(sale_data, toko_info):
    """Generate invoice coffee shop untuk WhatsApp"""
    # Parse items
    try:
        items_list = json.loads(sale_data['items']) if isinstance(sale_data['items'], str) else sale_data['items']
        items_str = '\n'.join([f"  {i['qty']}x {i['name']} @ Rp {i['price']:,.0f}" for i in items_list])
    except:
        items_str = "N/A"
    
    # Format pesan yang menarik dan impressive
    message = f"""*{'='*35}*
   *INVOICE COFFEE SHOP*
*{'='*35}*

*{toko_info.get('nama', 'TIME AUTOCARE')}*
_{toko_info.get('tagline', 'Detailing & Ceramic Coating')}_
Alamat: {toko_info.get('alamat', '')}
Telp: {toko_info.get('telp', '')}

*{'='*35}*
   *DETAIL PESANAN*
*{'='*35}*

Customer: *{sale_data.get('nama_customer', 'Walk-in Customer')}*
Tanggal: {sale_data['tanggal']}
Waktu: {sale_data['waktu']}
Kasir: {sale_data.get('created_by', '-')}

*{'='*35}*
   *PESANAN ANDA*
*{'='*35}*

{items_str}

*{'='*35}*

*TOTAL PEMBAYARAN:*
*Rp {sale_data['total']:,.0f}*

*{'='*35}*

_Terima kasih atas kunjungan Anda!_
_Kepuasan Anda adalah prioritas kami_

*Sampai jumpa lagi!* 

_Nikmati setiap tegukan..._
"""
    
    return message

def generate_invoice_message(trans_data, toko_info):
    """Generate pesan invoice untuk WhatsApp"""
    # Parse checklist
    try:
        checklist_datang = json.loads(trans_data['checklist_datang'])
        checklist_str_datang = '\n'.join([f"✓ {item}" for item in checklist_datang])
    except:
        checklist_str_datang = "N/A"
    
    try:
        checklist_selesai = json.loads(trans_data['checklist_selesai'])
        checklist_str_selesai = '\n'.join([f"✓ {item}" for item in checklist_selesai])
    except:
        checklist_str_selesai = "N/A"
    
    # Format pesan
    message = f"""🚗 *INVOICE TIME AUTOCARE*
━━━━━━━━━━━━━━━━━━━━

*{toko_info.get('nama', 'TIME AUTOCARE')}*
_{toko_info.get('tagline', 'Detailing & Ceramic Coating')}_
📍 {toko_info.get('alamat', '')}
📞 {toko_info.get('telp', '')}

━━━━━━━━━━━━━━━━━━━━
*DETAIL TRANSAKSI*

🔖 Nopol: *{trans_data['nopol']}*
👤 Customer: {trans_data['nama_customer']}
📅 Tanggal: {trans_data['tanggal']}
⏰ Masuk: {trans_data['waktu_masuk']}
⏰ Selesai: {trans_data['waktu_selesai']}

📦 Paket: *{trans_data['paket_cuci']}*
💰 Harga: *Rp {trans_data['harga']:,.0f}*

━━━━━━━━━━━━━━━━━━━━
*CHECKLIST SAAT DATANG:*
{checklist_str_datang}

*CHECKLIST SELESAI:*
{checklist_str_selesai}

━━━━━━━━━━━━━━━━━━━━
"""
    
    if trans_data.get('qc_barang'):
        message += f"📋 *Barang Customer:*\n{trans_data['qc_barang']}\n\n"
    
    if trans_data.get('catatan'):
        message += f"💬 *Catatan:*\n{trans_data['catatan']}\n\n"
    
    message += """━━━━━━━━━━━━━━━━━━━━
✨ Terima kasih telah menggunakan layanan kami!
Ditunggu kunjungan berikutnya 🙏"""
    
    return message

def create_whatsapp_link(phone_number, message):
    """Create WhatsApp link dengan nomor dan pesan"""
    # Clean phone number - remove spaces, dashes, etc
    phone = phone_number.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    
    # Convert 08xxx to 628xxx for WhatsApp
    if phone.startswith('08'):
        phone = '62' + phone[1:]
    elif phone.startswith('8'):
        phone = '62' + phone
    elif phone.startswith('+62'):
        phone = phone[1:]
    
    # URL encode the message
    encoded_message = urllib.parse.quote(message)
    
    # Create WhatsApp link
    wa_link = f"https://wa.me/{phone}?text={encoded_message}"
    
    return wa_link


# --- Review Customer Functions ---
def get_transaction_by_secret_code(secret_code):
    """Ambil transaksi berdasarkan secret code"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM kasir_transactions WHERE secret_code = ?", (secret_code.upper(),))
    result = c.fetchone()
    conn.close()
    if result:
        columns = ['id', 'nopol', 'nama_customer', 'no_telp', 'tanggal', 'waktu', 'wash_trans_id', 
                   'paket_cuci', 'harga_cuci', 'coffee_items', 'harga_coffee', 'total_bayar', 
                   'status_bayar', 'metode_bayar', 'created_by', 'catatan', 'secret_code']
        return dict(zip(columns, result))
    return None

def check_review_exists(secret_code):
    """Cek apakah secret code sudah pernah digunakan untuk review"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM customer_reviews WHERE secret_code = ?", (secret_code.upper(),))
    count = c.fetchone()[0]
    conn.close()
    return count > 0

def save_customer_review(review_data):
    """Simpan review customer dan berikan reward points"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        now_wib = datetime.now(WIB)
        
        # Simpan review
        c.execute("""
            INSERT INTO customer_reviews 
            (secret_code, trans_id, trans_type, nopol, no_telp, nama_customer, rating, review_text, 
             review_date, review_time, reward_points)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            review_data.get('secret_code', '').upper(),
            review_data.get('trans_id'),
            review_data.get('trans_type', 'kasir'),
            review_data.get('nopol', ''),
            review_data.get('no_telp', ''),
            review_data.get('nama_customer', ''),
            int(review_data.get('rating', 5)),
            review_data.get('review_text', ''),
            now_wib.strftime('%d-%m-%Y'),
            now_wib.strftime('%H:%M:%S'),
            10  # Default 10 points per review
        ))
        
        # Update atau tambah customer points
        identifier_nopol = review_data.get('nopol', '')
        identifier_telp = review_data.get('no_telp', '')
        
        # Cek apakah customer sudah ada
        c.execute("""
            SELECT id, total_points FROM customer_points 
            WHERE (nopol = ? AND nopol != '') OR (no_telp = ? AND no_telp != '')
        """, (identifier_nopol, identifier_telp))
        
        existing = c.fetchone()
        
        if existing:
            # Update points yang ada
            new_total = existing[1] + 10
            c.execute("""
                UPDATE customer_points 
                SET total_points = ?, last_updated = ?
                WHERE id = ?
            """, (new_total, now_wib.strftime('%d-%m-%Y %H:%M:%S'), existing[0]))
        else:
            # Insert customer baru
            c.execute("""
                INSERT INTO customer_points (nopol, no_telp, nama_customer, total_points, last_updated)
                VALUES (?, ?, ?, ?, ?)
            """, (
                identifier_nopol,
                identifier_telp,
                review_data.get('nama_customer', ''),
                10,
                now_wib.strftime('%d-%m-%Y %H:%M:%S')
            ))
        
        conn.commit()
        return True, "Review berhasil disimpan! Anda mendapat 10 poin reward 🎉"
    except Exception as e:
        return False, f"Error: {str(e)}"
    finally:
        conn.close()

def get_all_reviews():
    """Ambil semua review customer"""
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql("SELECT * FROM customer_reviews ORDER BY review_date DESC, review_time DESC", conn)
    conn.close()
    return df

def get_customer_points_by_identifier(nopol=None, no_telp=None):
    """Ambil poin customer berdasarkan nopol atau no_telp"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    if nopol:
        c.execute("SELECT * FROM customer_points WHERE nopol = ?", (nopol,))
    elif no_telp:
        c.execute("SELECT * FROM customer_points WHERE no_telp = ?", (no_telp,))
    else:
        conn.close()
        return None
    
    result = c.fetchone()
    conn.close()
    if result:
        columns = ['id', 'nopol', 'no_telp', 'nama_customer', 'total_points', 'last_updated']
        return dict(zip(columns, result))
    return None

def get_all_customer_points():
    """Ambil semua data poin customer"""
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql("SELECT * FROM customer_points ORDER BY total_points DESC", conn)
    conn.close()
    return df



USERS = {
    "admin": {"password": "admin123", "role": "Admin"},
    "kasir": {"password": "kasir123", "role": "Kasir"},
    "supervisor": {"password": "super123", "role": "Supervisor"},
}

# --- User Management Functions ---
def get_user_from_db(username):
    """Ambil user dari database"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ?", (username.lower(),))
    result = c.fetchone()
    conn.close()
    if result:
        return {
            'id': result[0],
            'username': result[1],
            'password': result[2],
            'role': result[3],
            'created_at': result[4],
            'created_by': result[5],
            'last_login': result[6]
        }
    return None

def get_all_users():
    """Ambil semua users"""
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql("SELECT id, username, role, created_at, created_by, last_login FROM users ORDER BY created_at DESC", conn)
    conn.close()
    return df

def add_user(username, password, role, created_by):
    """Tambah user baru"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    now_wib = datetime.now(WIB)
    try:
        c.execute("""
            INSERT INTO users (username, password, role, created_at, created_by, last_login)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (username.lower(), password, role, now_wib.strftime("%d-%m-%Y %H:%M:%S"), created_by, None))
        conn.commit()
        return True, "User berhasil ditambahkan"
    except sqlite3.IntegrityError:
        return False, "Username sudah terdaftar"
    except Exception as e:
        return False, f"Error: {str(e)}"
    finally:
        conn.close()

def update_user(username, password=None, role=None):
    """Update user"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        if password and role:
            c.execute("UPDATE users SET password = ?, role = ? WHERE username = ?",
                     (password, role, username.lower()))
        elif password:
            c.execute("UPDATE users SET password = ? WHERE username = ?",
                     (password, username.lower()))
        elif role:
            c.execute("UPDATE users SET role = ? WHERE username = ?",
                     (role, username.lower()))
        conn.commit()
        return True, "User berhasil diupdate"
    except Exception as e:
        return False, f"Error: {str(e)}"
    finally:
        conn.close()

def delete_user(username):
    """Hapus user"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("DELETE FROM users WHERE username = ?", (username.lower(),))
        conn.commit()
        return True, "User berhasil dihapus"
    except Exception as e:
        return False, f"Error: {str(e)}"
    finally:
        conn.close()

def update_last_login(username):
    """Update last login timestamp"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    now_wib = datetime.now(WIB)
    c.execute("UPDATE users SET last_login = ? WHERE username = ?",
             (now_wib.strftime("%d-%m-%Y %H:%M:%S"), username.lower()))
    conn.commit()
    conn.close()

# --- Audit Trail Helper ---
def add_audit(action, detail=None):
    """Simpan audit trail ke database SQLite agar persisten dan bisa dilihat semua user"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Gunakan timezone WIB (GMT+7)
    now_wib = datetime.now(WIB)
    c.execute("""
        INSERT INTO audit_trail (timestamp, user, action, detail)
        VALUES (?, ?, ?, ?)
    """, (
        now_wib.strftime("%d-%m-%Y %H:%M:%S"),
        st.session_state.get("login_user", "-"),
        action,
        detail or ""
    ))
    conn.commit()
    conn.close()

def load_audit_trail(user=None):
    """Load audit trail dari database. Jika user specified, filter by user."""
    conn = sqlite3.connect(DB_NAME)
    if user:
        query = "SELECT * FROM audit_trail WHERE user = ? ORDER BY timestamp DESC"
        df = pd.read_sql(query, conn, params=(user,))
    else:
        query = "SELECT * FROM audit_trail ORDER BY timestamp DESC"
        df = pd.read_sql(query, conn)
    conn.close()
    return df

def login_page():
    st.set_page_config(page_title="TIME AUTOCARE - Review & Login", layout="centered")
    
    st.markdown("""
    <style>
    .review-container {
        max-width: 600px;
        margin: 0 auto;
        padding: 2rem;
        background: white;
        border-radius: 15px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    }
    .review-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .star-rating {
        font-size: 2rem;
        text-align: center;
        margin: 1rem 0;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Sidebar untuk login admin/staff
    with st.sidebar:
        st.markdown("### 🔐 Staff Login")
        st.markdown("---")
        username = st.text_input("👤 Username", key="login_username")
        password = st.text_input("🔒 Password", type="password", key="login_password")
        
        login_btn = st.button("🔐 Login", key="login_btn", use_container_width=True, type="primary")
        
        if login_btn:
            uname = username.strip().lower()
            # Try database first, fallback to hardcoded USERS
            user_data = get_user_from_db(uname)
            if not user_data and uname in USERS:
                # Fallback to hardcoded users
                user_data = {"username": uname, "password": USERS[uname]["password"], "role": USERS[uname]["role"]}
            
            if user_data and password == user_data["password"]:
                st.session_state["is_logged_in"] = True
                st.session_state["login_user"] = uname
                st.session_state["login_role"] = user_data["role"]
                update_last_login(uname)
                add_audit("login", f"Login sebagai {user_data['role']}")
                st.success(f"✅ Login berhasil!")
                st.rerun()
            else:
                st.error("❌ Username/password salah")
        
        st.markdown("---")
        st.caption("💡 **Demo Account:**\n- admin / admin123\n- kasir / kasir123\n- supervisor / super123")
    
    # Main page - Customer Review
    st.markdown("""
    <div class="review-header">
        <h1 style="margin: 0;">🚗 TIME AUTOCARE</h1>
        <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">Detailing & Ceramic Coating</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("## ⭐ Berikan Review Anda")
    st.info("💡 **Dapatkan 10 poin reward** untuk setiap review yang Anda berikan!")
    
    # Input secret code
    st.markdown("### 🔑 Masukkan Kode Review")
    st.caption("Kode review dikirimkan bersama invoice WhatsApp setelah transaksi")
    
    secret_code_input = st.text_input(
        "Kode Review (8 karakter)",
        max_chars=8,
        placeholder="Contoh: ABC12XYZ",
        key="secret_code_input"
    ).upper()
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        verify_btn = st.button("🔍 Verifikasi Kode", use_container_width=True, type="primary")
    
    if verify_btn and secret_code_input:
        if len(secret_code_input) != 8:
            st.error("❌ Kode review harus 8 karakter!")
        else:
            # Cek apakah sudah pernah review
            if check_review_exists(secret_code_input):
                # Ambil data review yang sudah ada
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                c.execute("SELECT * FROM customer_reviews WHERE secret_code = ?", (secret_code_input,))
                review = c.fetchone()
                conn.close()
                
                if review:
                    st.session_state['existing_review'] = {
                        'nama_customer': review[6],
                        'nopol': review[4] if review[4] else 'Coffee Only',
                        'rating': review[7],
                        'review_text': review[8],
                        'review_date': review[9],
                        'review_time': review[10],
                        'reward_points': review[11]
                    }
                    st.session_state['review_already_submitted'] = True
                    st.rerun()
            else:
                # Kode belum pernah digunakan, cek apakah valid
                trans = get_transaction_by_secret_code(secret_code_input)
                if trans:
                    st.session_state['verified_transaction'] = trans
                    st.session_state['secret_code_verified'] = secret_code_input
                    st.session_state['review_already_submitted'] = False
                    st.success(f"✅ Kode valid! Transaksi ditemukan untuk **{trans['nama_customer']}**")
                    st.rerun()
                else:
                    st.error("❌ Kode review tidak valid atau tidak ditemukan.")
    
    # Tampilkan review yang sudah ada (read-only)
    if st.session_state.get('review_already_submitted') and st.session_state.get('existing_review'):
        review = st.session_state['existing_review']
        
        st.markdown("---")
        st.success("✅ Anda sudah memberikan review untuk transaksi ini!")
        
        st.markdown("### 📋 Review Anda")
        
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Nama:** {review['nama_customer']}")
            st.write(f"**Nopol:** {review['nopol']}")
        with col2:
            st.write(f"**Tanggal Review:** {review['review_date']}")
            st.write(f"**Waktu:** {review['review_time']}")
        
        st.markdown("---")
        st.markdown("### ⭐ Rating Anda")
        st.markdown(f'<div class="star-rating">{"⭐" * review["rating"]} ({review["rating"]}/5)</div>', unsafe_allow_html=True)
        
        st.markdown("### 💬 Review Anda")
        st.info(review['review_text'])
        
        st.markdown("---")
        st.success(f"🎁 Poin reward yang didapat: **+{review['reward_points']} poin**")
        
        st.markdown("---")
        st.warning("⚠️ Setiap kode review hanya dapat digunakan sekali. Anda tidak dapat mengubah review yang sudah dikirim.")
        
        if st.button("🔙 Kembali ke Halaman Awal"):
            # Clear session
            if 'existing_review' in st.session_state:
                del st.session_state['existing_review']
            if 'review_already_submitted' in st.session_state:
                del st.session_state['review_already_submitted']
            st.rerun()
    
    # Form review jika kode sudah diverifikasi dan belum pernah submit
    elif st.session_state.get('verified_transaction') and not st.session_state.get('review_already_submitted'):
        trans = st.session_state['verified_transaction']
        
        st.markdown("---")
        st.markdown("### 📋 Detail Transaksi")
        
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Nama:** {trans['nama_customer']}")
            st.write(f"**Nopol:** {trans['nopol']}")
            st.write(f"**Tanggal:** {trans['tanggal']}")
        with col2:
            st.write(f"**Paket:** {trans['paket_cuci'] or 'Coffee Only'}")
            st.write(f"**Total:** Rp {trans['total_bayar']:,.0f}")
            st.write(f"**Status:** {trans['status_bayar']}")
        
        st.markdown("---")
        st.markdown("### ⭐ Berikan Rating Anda")
        
        # Rating dengan bintang
        rating = st.select_slider(
            "Pilih rating",
            options=[1, 2, 3, 4, 5],
            value=5,
            format_func=lambda x: "⭐" * x,
            key="rating_slider"
        )
        
        st.markdown(f'<div class="star-rating">{"⭐" * rating}</div>', unsafe_allow_html=True)
        
        # Review text
        st.markdown("### 💬 Tulis Review Anda")
        review_text = st.text_area(
            "Bagaimana pengalaman Anda?",
            placeholder="Ceritakan pengalaman Anda menggunakan layanan kami...",
            height=150,
            key="review_text_input"
        )
        
        # Submit review
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            submit_review_btn = st.button("📤 Kirim Review", use_container_width=True, type="primary", key="submit_review")
        
        if submit_review_btn:
            if not review_text or len(review_text.strip()) < 10:
                st.error("❌ Mohon tulis review minimal 10 karakter")
            else:
                review_data = {
                    'secret_code': st.session_state['secret_code_verified'],
                    'trans_id': trans['id'],
                    'trans_type': 'kasir',
                    'nopol': trans['nopol'],
                    'no_telp': trans['no_telp'],
                    'nama_customer': trans['nama_customer'],
                    'rating': rating,
                    'review_text': review_text.strip()
                }
                
                success, msg = save_customer_review(review_data)
                
                if success:
                    st.success(msg)
                    st.balloons()
                    
                    # Show points info
                    points_info = get_customer_points_by_identifier(
                        nopol=trans['nopol'] if trans['nopol'] else None,
                        no_telp=trans['no_telp'] if not trans['nopol'] else None
                    )
                    
                    if points_info:
                        st.info(f"🎁 Total poin Anda sekarang: **{points_info['total_points']} poin**")
                    
                    st.markdown("---")
                    st.success("✅ Terima kasih atas review Anda! Poin reward sudah ditambahkan ke akun Anda.")
                    st.info("💡 Review Anda telah tersimpan dan tidak dapat diubah lagi.")
                    
                    # Set flag bahwa review sudah disubmit
                    st.session_state['existing_review'] = {
                        'nama_customer': trans['nama_customer'],
                        'nopol': trans['nopol'] if trans['nopol'] else 'Coffee Only',
                        'rating': rating,
                        'review_text': review_text.strip(),
                        'review_date': datetime.now(WIB).strftime("%d-%m-%Y"),
                        'review_time': datetime.now(WIB).strftime("%H:%M:%S"),
                        'reward_points': 10
                    }
                    st.session_state['review_already_submitted'] = True
                    
                    # Clear transaction session
                    if 'verified_transaction' in st.session_state:
                        del st.session_state['verified_transaction']
                    if 'secret_code_verified' in st.session_state:
                        del st.session_state['secret_code_verified']
                    
                    if st.button("🔙 Kembali ke Halaman Awal"):
                        if 'existing_review' in st.session_state:
                            del st.session_state['existing_review']
                        if 'review_already_submitted' in st.session_state:
                            del st.session_state['review_already_submitted']
                        st.rerun()
                else:
                    st.error(msg)
    
    # Info tambahan - hanya tampil jika tidak ada review yang aktif
    if not st.session_state.get('verified_transaction') and not st.session_state.get('review_already_submitted'):
        st.markdown("---")
        st.markdown("### ℹ️ Tentang Program Reward")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            **Keuntungan:**
            - 🎁 10 poin per review
            - 🎉 Tukar poin dengan promo
            - ⭐ Poin tidak ada masa kadaluarsa
            """)
        with col2:
            st.markdown("""
            **Cara Mendapat Kode:**
            - 💳 Lakukan transaksi
            - 📱 Terima invoice via WhatsApp
            - 🔑 Gunakan kode review di invoice
            """)


def dashboard_page(role):
    st.markdown("""
    <style>
    .dashboard-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 20px rgba(102, 126, 234, 0.4);
    }
    .dashboard-header h1 {
        margin: 0;
        font-size: 2.2rem;
        font-weight: 800;
    }
    .dashboard-header p {
        margin: 0.5rem 0 0 0;
        opacity: 0.9;
    }
    .card-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1.2rem;
        margin-bottom: 2rem;
    }
    .card {
        background: white;
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        border-left: 4px solid;
        transition: all 0.3s ease;
    }
    .card:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
    }
    .card.card-1 { border-left-color: #667eea; }
    .card.card-2 { border-left-color: #f093fb; }
    .card.card-3 { border-left-color: #4facfe; }
    .card.card-4 { border-left-color: #43e97b; }
    .card.card-5 { border-left-color: #fa709a; }
    .card-icon {
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
    }
    .card-title {
        color: #636e72;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 0.5rem;
    }
    .card-value {
        font-size: 2.2rem;
        font-weight: 800;
        color: #2d3436;
        margin-bottom: 0.3rem;
    }
    .card-desc {
        color: #b2bec3;
        font-size: 0.8rem;
    }
    .chart-box {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        margin-bottom: 1.5rem;
    }
    .chart-title {
        color: #2d3436;
        font-size: 1.2rem;
        font-weight: 700;
        margin-bottom: 1rem;
        padding-bottom: 0.8rem;
        border-bottom: 3px solid #f0f0f0;
    }
    .filter-bar {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    .business-summary {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 20px;
        color: white;
        margin: 2rem 0;
        box-shadow: 0 8px 30px rgba(102, 126, 234, 0.3);
    }
    .business-summary h3 {
        margin: 0 0 1rem 0;
        font-size: 1.5rem;
        font-weight: 800;
    }
    .summary-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1.5rem;
        margin-top: 1.5rem;
    }
    .summary-item {
        background: rgba(255,255,255,0.15);
        padding: 1.2rem;
        border-radius: 12px;
        backdrop-filter: blur(10px);
    }
    .summary-item-label {
        font-size: 0.85rem;
        opacity: 0.9;
        margin-bottom: 0.5rem;
        font-weight: 600;
    }
    .summary-item-value {
        font-size: 1.8rem;
        font-weight: 900;
    }
    </style>
    """, unsafe_allow_html=True)

    # Header
    now = datetime.now(WIB)
    st.markdown(f'''
    <div class="dashboard-header">
        <h1>📊 Dashboard TIME AUTOCARE</h1>
        <p>📅 {now.strftime("%A, %d %B %Y")} • ⏰ {now.strftime("%H:%M:%S")} WIB • 👤 {role}</p>
    </div>
    ''', unsafe_allow_html=True)
    
    # Load data transaksi
    df_trans = get_all_transactions()
    df_cust = get_all_customers()
    df_coffee = get_all_coffee_sales()
    df_kasir = get_all_kasir_transactions()
    
    # Filter tanggal - default hari ini
    today = datetime.now(WIB).date()
    
    # Initialize session state for date filter
    if 'dashboard_date_filter' not in st.session_state:
        st.session_state.dashboard_date_filter = (today, today)
    
    # ROLE-BASED DATE FILTER: Kasir only sees today's data
    if role == "Kasir":
        st.info("ℹ️ Kasir hanya dapat melihat data hari ini")
        date_filter = (today, today)  # Force today only
        st.session_state.dashboard_date_filter = date_filter
    else:
        # Admin and Supervisor can select date range
        date_filter = st.date_input("📅 Filter Periode", value=st.session_state.dashboard_date_filter, key="dashboard_date_input")
        # Update session state when user changes date input
        if date_filter != st.session_state.dashboard_date_filter:
            st.session_state.dashboard_date_filter = date_filter
    
    # Apply filter
    if isinstance(date_filter, (list, tuple)) and len(date_filter) == 2:
        start_date = date_filter[0].strftime('%d-%m-%Y')
        end_date = date_filter[1].strftime('%d-%m-%Y')
        df_filtered = get_transactions_by_date_range(start_date, end_date)
        
        # Filter coffee sales by date range
        df_coffee_filtered = df_coffee[
            (pd.to_datetime(df_coffee['tanggal'], format='%d-%m-%Y', errors='coerce') >= pd.to_datetime(start_date, format='%d-%m-%Y')) &
            (pd.to_datetime(df_coffee['tanggal'], format='%d-%m-%Y', errors='coerce') <= pd.to_datetime(end_date, format='%d-%m-%Y'))
        ]
        
        # Filter kasir transactions by date range
        df_kasir_filtered = df_kasir[
            (pd.to_datetime(df_kasir['tanggal'], format='%d-%m-%Y', errors='coerce') >= pd.to_datetime(start_date, format='%d-%m-%Y')) &
            (pd.to_datetime(df_kasir['tanggal'], format='%d-%m-%Y', errors='coerce') <= pd.to_datetime(end_date, format='%d-%m-%Y'))
        ]
    else:
        df_filtered = df_trans
        df_coffee_filtered = df_coffee
        df_kasir_filtered = df_kasir
    
    # Hitung statistik cuci mobil (yang belum masuk kasir)
    total_transaksi_wash = len(df_filtered)
    total_pendapatan_wash = df_filtered['harga'].sum() if not df_filtered.empty else 0
    transaksi_selesai = len(df_filtered[df_filtered['status'] == 'Selesai'])
    transaksi_proses = len(df_filtered[df_filtered['status'] == 'Dalam Proses'])
    
    # Hitung statistik kasir (transaksi gabungan)
    total_transaksi_kasir = len(df_kasir_filtered)
    total_pendapatan_kasir = df_kasir_filtered['total_bayar'].sum() if not df_kasir_filtered.empty else 0
    pendapatan_kasir_wash = df_kasir_filtered['harga_cuci'].sum() if not df_kasir_filtered.empty else 0
    pendapatan_kasir_coffee = df_kasir_filtered['harga_coffee'].sum() if not df_kasir_filtered.empty else 0
    
    # Hitung statistik coffee shop - gabungan dari coffee_sales dan kasir_transactions
    # Coffee dari tabel coffee_sales saja (bukan dari kasir)
    total_transaksi_coffee_only = len(df_coffee_filtered)
    total_pendapatan_coffee_only = df_coffee_filtered['total'].sum() if not df_coffee_filtered.empty else 0
    # Total semua pendapatan coffee (dari kasir + coffee only)
    total_pendapatan_coffee = pendapatan_kasir_coffee + total_pendapatan_coffee_only
    total_transaksi_coffee = total_transaksi_coffee_only + len(df_kasir_filtered[df_kasir_filtered['harga_coffee'] > 0])
    
    # Total keseluruhan (hitung semua pendapatan)
    # Note: cuci mobil yang sudah masuk kasir tidak dihitung lagi di total_pendapatan_wash
    total_pendapatan_gabungan = pendapatan_kasir_wash + total_pendapatan_coffee
    total_transaksi_gabungan = total_transaksi_kasir + total_transaksi_coffee_only
    total_customer = len(df_cust)
    
    # Cards
    st.markdown(f'''
    <div class="card-container">
        <div class="card card-1">
            <div class="card-icon">💰</div>
            <div class="card-title">Total Pendapatan</div>
            <div class="card-value">Rp {total_pendapatan_gabungan:,.0f}</div>
            <div class="card-desc">Car Wash + Coffee Shop</div>
        </div>
        <div class="card card-2">
            <div class="card-icon">🚗</div>
            <div class="card-title">Cuci Mobil</div>
            <div class="card-value">Rp {total_pendapatan_wash:,.0f}</div>
            <div class="card-desc">{total_transaksi_wash} transaksi</div>
        </div>
        <div class="card card-6" style="border-left-color: #f6d365;">
            <div class="card-icon">☕</div>
            <div class="card-title">Coffee Shop</div>
            <div class="card-value">Rp {total_pendapatan_coffee:,.0f}</div>
            <div class="card-desc">{total_transaksi_coffee} transaksi</div>
        </div>
        <div class="card card-3">
            <div class="card-icon">✅</div>
            <div class="card-title">Selesai</div>
            <div class="card-value">{transaksi_selesai}</div>
            <div class="card-desc">Sudah dikerjakan</div>
        </div>
        <div class="card card-4">
            <div class="card-icon">⏳</div>
            <div class="card-title">Dalam Proses</div>
            <div class="card-value">{transaksi_proses}</div>
            <div class="card-desc">Sedang dikerjakan</div>
        </div>
        <div class="card card-5">
            <div class="card-icon">👥</div>
            <div class="card-title">Total Customer</div>
            <div class="card-value">{total_customer}</div>
            <div class="card-desc">Customer terdaftar</div>
        </div>
    </div>
    ''', unsafe_allow_html=True)
    
    # Business Summary
    if total_transaksi_gabungan > 0:
        avg_kasir = total_pendapatan_kasir / total_transaksi_kasir if total_transaksi_kasir > 0 else 0
        avg_coffee = total_pendapatan_coffee / total_transaksi_coffee if total_transaksi_coffee > 0 else 0
        kasir_percentage = (total_pendapatan_kasir / total_pendapatan_gabungan * 100) if total_pendapatan_gabungan > 0 else 0
        coffee_percentage = (total_pendapatan_coffee / total_pendapatan_gabungan * 100) if total_pendapatan_gabungan > 0 else 0
        
        st.markdown(f'''
        <div class="business-summary">
            <h3>📈 Ringkasan Bisnis</h3>
            <div class="summary-grid">
                <div class="summary-item">
                    <div class="summary-item-label">💵 Rata-rata Transaksi Kasir</div>
                    <div class="summary-item-value">Rp {avg_kasir:,.0f}</div>
                </div>
                <div class="summary-item">
                    <div class="summary-item-label">☕ Rata-rata Coffee Only</div>
                    <div class="summary-item-value">Rp {avg_coffee:,.0f}</div>
                </div>
                <div class="summary-item">
                    <div class="summary-item-label">💳 Kontribusi Kasir</div>
                    <div class="summary-item-value">{kasir_percentage:.1f}%</div>
                </div>
                <div class="summary-item">
                    <div class="summary-item-label">☕ Kontribusi Coffee</div>
                    <div class="summary-item-value">{coffee_percentage:.1f}%</div>
                </div>
            </div>
        </div>
        ''', unsafe_allow_html=True)
    
    # Perolehan Per Akun (Admin & Supervisor only)
    if role in ["Admin", "Supervisor"] and not df_filtered.empty:
        st.markdown("---")
        st.subheader("👥 Perolehan Per Akun User")
        st.info("💡 Breakdown pendapatan cuci mobil berdasarkan user yang mencatat transaksi")
        
        # Group by created_by
        earnings_by_user = df_filtered.groupby('created_by').agg({
            'harga': 'sum',
            'id': 'count'
        }).reset_index()
        earnings_by_user.columns = ['User', 'Total Pendapatan (Rp)', 'Jumlah Transaksi']
        earnings_by_user = earnings_by_user.sort_values('Total Pendapatan (Rp)', ascending=False)
        
        # Format currency
        earnings_by_user['Pendapatan'] = earnings_by_user['Total Pendapatan (Rp)'].apply(lambda x: f"Rp {x:,.0f}")
        
        # Display as table
        col1, col2 = st.columns([2, 1])
        with col1:
            st.dataframe(
                earnings_by_user[['User', 'Pendapatan', 'Jumlah Transaksi']],
                use_container_width=True,
                hide_index=True
            )
        with col2:
            # Chart for user earnings
            chart_user = alt.Chart(earnings_by_user).mark_bar(cornerRadiusEnd=8).encode(
                x=alt.X('Total Pendapatan (Rp):Q', title='Total (Rp)'),
                y=alt.Y('User:N', sort='-x', title='User'),
                color=alt.Color('Total Pendapatan (Rp):Q', scale=alt.Scale(scheme='blues'), legend=None),
                tooltip=['User', alt.Tooltip('Total Pendapatan (Rp):Q', format=',.0f', title='Total Rp'), 'Jumlah Transaksi']
            ).properties(height=200)
            st.altair_chart(chart_user, use_container_width=True)
    
    # Grafik
    if not df_filtered.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 Pendapatan per Paket")
            paket_income = df_filtered.groupby('paket_cuci')['harga'].sum().reset_index()
            paket_income.columns = ['Paket', 'Total']
            
            chart = alt.Chart(paket_income).mark_bar(cornerRadiusEnd=8).encode(
                x=alt.X('Total:Q', title='Total Pendapatan (Rp)'),
                y=alt.Y('Paket:N', sort='-x', title='Paket Cuci'),
                color=alt.Color('Total:Q', scale=alt.Scale(scheme='viridis'), legend=None),
                tooltip=['Paket', alt.Tooltip('Total:Q', format=',.0f', title='Rp')]
            ).properties(height=300)
            st.altair_chart(chart, use_container_width=True)
        
        with col2:
            st.subheader("📈 Status Transaksi")
            status_count = df_filtered['status'].value_counts().reset_index()
            status_count.columns = ['Status', 'Jumlah']
            
            pie = alt.Chart(status_count).mark_arc(innerRadius=60, outerRadius=120).encode(
                theta='Jumlah:Q',
                color=alt.Color('Status:N', 
                    scale=alt.Scale(domain=['Selesai', 'Dalam Proses'], range=['#43e97b', '#f5576c']),
                    legend=alt.Legend(orient='bottom')
                ),
                tooltip=['Status', 'Jumlah']
            ).properties(height=300)
            st.altair_chart(pie, use_container_width=True)
        
        # Tabel transaksi terbaru
        st.subheader("� Transaksi Terbaru")
        df_display = df_filtered[['tanggal', 'nopol', 'nama_customer', 'paket_cuci', 'harga', 'status']].head(10)
        st.dataframe(df_display, use_container_width=True)
    else:
        st.info("📭 Belum ada transaksi untuk periode ini")


def transaksi_page(role):
    st.markdown("""
    <style>
    .trans-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    .trans-header h2 {
        margin: 0;
        font-size: 1.8rem;
        font-weight: 700;
    }
    .modern-card {
        background: white;
        padding: 1rem;
        border-radius: 12px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.06);
        margin-bottom: 1rem;
        border: 1px solid #f0f0f0;
        transition: all 0.3s ease;
    }
    .modern-card:hover {
        box-shadow: 0 6px 30px rgba(0,0,0,0.12);
        border-color: #667eea;
    }
    .section-header {
        display: flex;
        align-items: center;
        gap: 0.8rem;
        margin-bottom: 1.5rem;
        padding-bottom: 1rem;
        border-bottom: 3px solid #f0f0f0;
    }
    .section-header h3 {
        margin: 0;
        color: #2d3436;
        font-size: 1.3rem;
        font-weight: 700;
    }
    .stTextInput > div > div > input, 
    .stSelectbox > div > div > select,
    .stTextArea > div > div > textarea {
        border-radius: 8px !important;
        border: 2px solid #e0e0e0 !important;
        padding: 0.4rem 0.6rem !important;
        transition: all 0.3s ease !important;
        font-size: 0.95rem !important;
    }
    .stTextInput > div > div > input:focus, 
    .stSelectbox > div > div > select:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: #667eea !important;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
    }
    .stCheckbox {
        padding: 0.3rem;
        border-radius: 6px;
        transition: background 0.2s ease;
    }
    .stCheckbox:hover {
        background: #f8f9fa;
    }
    .stCheckbox > label {
        font-weight: 500;
        color: #2d3436;
    }
    .stTextInput > label, 
    .stSelectbox > label, 
    .stTextArea > label,
    .stDateInput > label,
    .stTimeInput > label {
        font-weight: 600 !important;
        color: #2d3436 !important;
        font-size: 0.85rem !important;
        margin-bottom: 0.3rem !important;
    }
    div[data-testid="stButton"] > button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        padding: 0.6rem 1.5rem !important;
        transition: all 0.3s ease !important;
    }
    div[data-testid="stButton"] > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0,0,0,0.15) !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="trans-header"><h2>🚗  TIME AUTOCARE</h2></div>', unsafe_allow_html=True)
    
    # Get current user
    current_user = st.session_state.get('login_user', '-')
    
    # Hitung perolehan personal user hari ini
    today = datetime.now(WIB).strftime('%d-%m-%Y')
    df_all = get_all_transactions()
    
    # Filter transaksi hari ini yang dibuat oleh user yang login
    df_today_user = df_all[
        (df_all['tanggal'] == today) & 
        (df_all['created_by'] == current_user)
    ]
    
    jumlah_mobil_today = len(df_today_user)
    pendapatan_today = df_today_user['harga'].sum() if not df_today_user.empty else 0
    
    # Card Perolehan Personal Hari Ini
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1.5rem; border-radius: 15px; margin-bottom: 1.5rem; box-shadow: 0 4px 20px rgba(102, 126, 234, 0.4);">
        <div style="color: white;">
            <div style="font-size: 1rem; margin-bottom: 0.5rem; font-weight: 600; text-shadow: 0 2px 4px rgba(0,0,0,0.2);">📊 Perolehan Hari Ini - {current_user.upper()}</div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 1rem;">
                <div style="background: rgba(255,255,255,0.95); padding: 1rem; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <div style="font-size: 0.8rem; color: #636e72; margin-bottom: 0.3rem; font-weight: 600;">🚗 MOBIL MASUK</div>
                    <div style="font-size: 2.2rem; font-weight: 900; color: #2d3436;">{jumlah_mobil_today}</div>
                    <div style="font-size: 0.75rem; color: #b2bec3; margin-top: 0.2rem;">unit</div>
                </div>
                <div style="background: rgba(255,255,255,0.95); padding: 1rem; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <div style="font-size: 0.8rem; color: #636e72; margin-bottom: 0.3rem; font-weight: 600;">💰 PENDAPATAN</div>
                    <div style="font-size: 1.8rem; font-weight: 900; color: #2d3436;">Rp {pendapatan_today:,.0f}</div>
                    <div style="font-size: 0.75rem; color: #b2bec3; margin-top: 0.2rem;">hari ini</div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Hitung jumlah transaksi dalam proses untuk badge
    jumlah_proses = len(df_all[df_all['status'] == 'Dalam Proses'])
    jumlah_selesai = len(df_all[df_all['status'] == 'Selesai'])
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📝 Transaksi Baru", 
        f"✅ Selesaikan Transaksi ({jumlah_proses})",
        f"📚 History Customer ({jumlah_selesai})",
        "✏️ Edit/Hapus Transaksi",
        "⚙️ Setting Paket Cuci"
    ])
    
    with tab1:
        # Load paket dan checklist dari database
        paket_cucian = get_paket_cucian()
        checklist_items = get_checklist_datang()
        
        # === SECTION 1: DATA KENDARAAN ===
        st.markdown("""
        <div style="margin-bottom: 0.5rem;">
            <h4 style="margin: 0; color: #2d3436; font-size: 1rem; font-weight: 600; padding: 0.6rem 0; border-bottom: 2px solid #e0e0e0;">🚘 Data Kendaraan</h4>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns([3, 2])
        
        with col1:
            nopol_input = st.text_input(
                "Nomor Polisi", 
                placeholder="Contoh: B1234XYZ", 
                key="trans_nopol", 
                help="Masukkan nomor polisi kendaraan",
                label_visibility="visible"
            ).upper()
            
            # Auto-fill dari database
            customer_data = None
            if nopol_input:
                customer_data = get_customer_by_nopol(nopol_input)
            
            if customer_data:
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); color: white; padding: 1rem 1.5rem; border-radius: 12px; margin: 1rem 0; box-shadow: 0 3px 12px rgba(67, 233, 123, 0.3);">
                    <div style="font-size: 1.1rem; font-weight: 600;">✅ Customer Terdaftar</div>
                    <div style="font-size: 1.3rem; font-weight: 800; margin-top: 0.5rem;">{customer_data['nama_customer']}</div>
                </div>
                """, unsafe_allow_html=True)
                nama_cust = customer_data['nama_customer']
                telp_cust = customer_data['no_telp']
                jenis_kendaraan_existing = customer_data.get('jenis_kendaraan', '')
                merk_kendaraan_existing = customer_data.get('merk_kendaraan', '')
                ukuran_mobil_existing = customer_data.get('ukuran_mobil', '')
                
                with st.expander("👁️ Lihat Detail Customer", expanded=False):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.write(f"**📞 Telepon:**")
                        st.info(f"{telp_cust}")
                    if jenis_kendaraan_existing or merk_kendaraan_existing or ukuran_mobil_existing:
                        st.write("**🚗 Info Kendaraan:**")
                        col_jenis, col_merk, col_ukuran = st.columns(3)
                        with col_jenis:
                            if jenis_kendaraan_existing:
                                st.info(f"Jenis: {jenis_kendaraan_existing}")
                        with col_merk:
                            if merk_kendaraan_existing:
                                st.info(f"Merk: {merk_kendaraan_existing}")
                        with col_ukuran:
                            if ukuran_mobil_existing:
                                st.info(f"Ukuran: {ukuran_mobil_existing}")
            else:
                if nopol_input:
                    st.markdown("""
                    <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 1rem 1.5rem; border-radius: 12px; margin: 1rem 0; box-shadow: 0 3px 12px rgba(240, 147, 251, 0.3);">
                        <div style="font-size: 1.1rem; font-weight: 600;">🆕 Customer Baru</div>
                        <div style="font-size: 0.95rem; margin-top: 0.3rem;">Silakan lengkapi data di bawah</div>
                    </div>
                    """, unsafe_allow_html=True)
                nama_cust = st.text_input("Nama Customer", key="trans_nama", 
                                         placeholder="Nama lengkap customer")
                telp_cust = st.text_input("No. Telepon", key="trans_telp", 
                                         placeholder="08xxxxxxxxxx")
                jenis_kendaraan_existing = ''
                merk_kendaraan_existing = ''
                ukuran_mobil_existing = ''
            
            # Input Info Kendaraan
            st.markdown("""
            <div style="margin: 1.5rem 0 0.5rem 0;">
                <h4 style="margin: 0; color: #2d3436; font-size: 1rem; font-weight: 600; padding: 0.6rem 0; border-bottom: 2px solid #e0e0e0;">🚙 Informasi Kendaraan</h4>
            </div>
            """, unsafe_allow_html=True)
            
            col_jenis, col_merk, col_ukuran = st.columns(3)
            with col_jenis:
                jenis_kendaraan = st.text_input(
                    "Jenis Kendaraan", 
                    value=jenis_kendaraan_existing,
                    key="trans_jenis", 
                    placeholder="Sedan/SUV/MPV/Hatchback"
                )
            with col_merk:
                merk_kendaraan = st.text_input(
                    "Merk Kendaraan", 
                    value=merk_kendaraan_existing,
                    key="trans_merk", 
                    placeholder="Toyota/Honda/Daihatsu"
                )
            with col_ukuran:
                ukuran_mobil = st.selectbox(
                    "Ukuran Mobil", 
                    options=["", "Kecil", "Sedang", "Besar", "Extra Besar"],
                    index=["", "Kecil", "Sedang", "Besar", "Extra Besar"].index(ukuran_mobil_existing) if ukuran_mobil_existing in ["", "Kecil", "Sedang", "Besar", "Extra Besar"] else 0,
                    key="trans_ukuran"
                )
        
        with col2:
            st.markdown("""
            <div style="margin-bottom: 0.5rem;">
                <h4 style="margin: 0; color: #2d3436; font-size: 1rem; font-weight: 600; padding: 0.6rem 0; border-bottom: 2px solid #e0e0e0;">🕐 Waktu Transaksi</h4>
            </div>
            """, unsafe_allow_html=True)
            now_wib = datetime.now(WIB)
            st.info(f"📅 Tanggal: **{now_wib.strftime('%d-%m-%Y')}**")
            st.info(f"⏰ Waktu Masuk: **{now_wib.strftime('%H:%M:%S')} WIB**")
            st.caption("Waktu dicatat otomatis oleh sistem")
        
        # Paket cuci
        st.markdown("""
        <div style="margin: 1rem 0 0.5rem 0;">
            <h4 style="margin: 0; color: #2d3436; font-size: 1rem; font-weight: 600; padding: 0.6rem 0; border-bottom: 2px solid #e0e0e0;">📦 Paket Cuci & Harga</h4>
        </div>
        """, unsafe_allow_html=True)
        
        col_paket, col_harga = st.columns([3, 2])
        with col_paket:
            paket = st.selectbox("Pilih Paket Cuci", options=list(paket_cucian.keys()), key="trans_paket")
        
        harga = paket_cucian[paket]
        
        # DYNAMIC PRICING: Add 5000 after 5 PM (17:00)
        now_wib = datetime.now(WIB)
        evening_surcharge = 0
        if now_wib.hour >= 17:
            evening_surcharge = 5000
            st.warning(f"🌙 **Harga Malam:** Tambahan Rp 5.000 setelah jam 17:00")
        
        # Hitung harga dengan multiplier berdasarkan ukuran
        multiplier_map = get_ukuran_multiplier()
        multiplier = multiplier_map.get(ukuran_mobil, 1.0) if ukuran_mobil else 1.0
        harga_final = int(harga * multiplier) + evening_surcharge
        
        with col_harga:
            if multiplier > 1.0 or evening_surcharge > 0:
                breakdown_text = ""
                if multiplier > 1.0:
                    breakdown_text += f"<div style=\"font-size: 0.75rem; opacity: 0.9; margin-bottom: 0.2rem;\">Harga Dasar: Rp {harga:,.0f}</div>"
                    breakdown_text += f"<div style=\"font-size: 0.75rem; opacity: 0.9; margin-bottom: 0.3rem;\">Multiplier {ukuran_mobil}: x{multiplier}</div>"
                if evening_surcharge > 0:
                    breakdown_text += f"<div style=\"font-size: 0.75rem; opacity: 0.9; margin-bottom: 0.3rem;\">🌙 Harga Malam: +Rp {evening_surcharge:,.0f}</div>"
                
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); color: white; padding: 0.8rem; border-radius: 10px; text-align: center; box-shadow: 0 3px 10px rgba(67, 233, 123, 0.3); margin-top: 1.7rem;">
                    {breakdown_text}
                    <div style="font-size: 1.2rem; font-weight: 800;">💰 Rp {harga_final:,.0f}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); color: white; padding: 0.8rem; border-radius: 10px; text-align: center; font-size: 1.2rem; font-weight: 800; box-shadow: 0 3px 10px rgba(67, 233, 123, 0.3); margin-top: 1.7rem;">
                    💰 Rp {harga_final:,.0f}
                </div>
                """, unsafe_allow_html=True)
        
        # Checklist saat datang
        st.markdown("""
        <div style="margin: 1rem 0 0.5rem 0;">
            <h4 style="margin: 0; color: #2d3436; font-size: 1rem; font-weight: 600; padding: 0.6rem 0; border-bottom: 2px solid #e0e0e0;">✅ Checklist Kondisi Mobil Saat Datang</h4>
        </div>
        """, unsafe_allow_html=True)
        
        selected_checks = []
        cols = st.columns(3)
        for idx, item in enumerate(checklist_items):
            with cols[idx % 3]:
                if st.checkbox(item, key=f"check_{idx}", value=False):
                    selected_checks.append(item)
        
        # QC Barang dalam mobil
        st.markdown("""
        <div style="margin: 1rem 0 0.5rem 0;">
            <h4 style="margin: 0; color: #2d3436; font-size: 1rem; font-weight: 600; padding: 0.6rem 0; border-bottom: 2px solid #e0e0e0;">📋 QC Barang dalam Mobil</h4>
        </div>
        """, unsafe_allow_html=True)
        qc_barang = st.text_area("📝 Catat barang-barang di dalam mobil", 
                                 placeholder="Contoh:\n• Dompet di dashboard\n• HP di tempat HP\n• Karpet di bagasi\n• Payung di pintu",
                                 key="trans_qc_barang", height=120)
        
        # Catatan tambahan
        catatan = st.text_area("� Catatan Tambahan", placeholder="Catatan khusus untuk pengerjaan...", 
                              key="trans_catatan", height=80)
        
        # Submit button
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            submit_btn = st.button("💾 Simpan Transaksi", type="primary", use_container_width=True, key="submit_trans_new")
        
        if submit_btn:
            if not nopol_input or not nama_cust or not paket:
                st.error("❌ Mohon isi Nomor Polisi, Nama Customer, dan Paket Cuci")
            else:
                # Simpan customer baru jika belum ada
                if not customer_data:
                    success, msg = save_customer(nopol_input, nama_cust, telp_cust or "", 
                                                jenis_kendaraan, merk_kendaraan, ukuran_mobil)
                    if not success and "sudah terdaftar" not in msg.lower():
                        st.error(f"❌ Gagal menyimpan customer: {msg}")
                        st.stop()
                else:
                    # Update vehicle info for existing customer if changed
                    if (jenis_kendaraan != jenis_kendaraan_existing or 
                        merk_kendaraan != merk_kendaraan_existing or 
                        ukuran_mobil != ukuran_mobil_existing):
                        conn = sqlite3.connect(DB_NAME)
                        c = conn.cursor()
                        c.execute("""
                            UPDATE customers 
                            SET jenis_kendaraan = ?, merk_kendaraan = ?, ukuran_mobil = ?
                            WHERE nopol = ?
                        """, (jenis_kendaraan, merk_kendaraan, ukuran_mobil, nopol_input.upper()))
                        conn.commit()
                        conn.close()
                
                # Gunakan waktu sistem otomatis
                now_wib = datetime.now(WIB)
                tanggal_str = now_wib.strftime('%d-%m-%Y')
                waktu_str = now_wib.strftime('%H:%M:%S')
                
                # Hitung harga dengan multiplier ukuran mobil
                multiplier_map = get_ukuran_multiplier()
                multiplier = multiplier_map.get(ukuran_mobil, 1.0) if ukuran_mobil else 1.0
                harga_final = int(harga * multiplier)
                
                # Simpan transaksi
                trans_data = {
                    'nopol': nopol_input,
                    'nama_customer': nama_cust,
                    'tanggal': tanggal_str,
                    'waktu_masuk': waktu_str,
                    'waktu_selesai': '',
                    'paket_cuci': paket,
                    'harga': harga_final,
                    'jenis_kendaraan': jenis_kendaraan,
                    'merk_kendaraan': merk_kendaraan,
                    'ukuran_mobil': ukuran_mobil,
                    'checklist_datang': json.dumps(selected_checks),
                    'checklist_selesai': '',
                    'qc_barang': qc_barang,
                    'catatan': catatan,
                    'status': 'Dalam Proses',
                    'created_by': st.session_state.get('login_user', '')
                }
                
                success, msg = save_transaction(trans_data)
                if success:
                    add_audit("transaksi_baru", f"Nopol: {nopol_input}, Paket: {paket}, Harga: Rp {harga:,.0f}")
                    st.success(f"✅ {msg}")
                    
                    # Generate konfirmasi WhatsApp untuk customer
                    if telp_cust:
                        toko_info = get_toko_info()
                        
                        # Format checklist
                        checklist_str = '\n'.join([f"• {item}" for item in selected_checks])
                        
                        # Generate pesan konfirmasi
                        konfirmasi_message = f"""*KONFIRMASI PENERIMAAN KENDARAAN*
*{toko_info.get('nama', 'TIME AUTOCARE')}*
_{toko_info.get('tagline', 'Detailing & Ceramic Coating')}_

📅 *DETAIL TRANSAKSI*

🔖 Nopol: *{nopol_input}*
👤 Customer: {nama_cust}
📅 Tanggal: {tanggal_str}
⏰ Waktu Masuk: {waktu_str} WIB

📦 *Paket: {paket}*
💰 *Harga: Rp {harga:,.0f}*

✅ *CHECKLIST KONDISI SAAT DATANG:*
{checklist_str}
"""
                        
                        if qc_barang:
                            konfirmasi_message += f"\n📋 *BARANG DI DALAM MOBIL:*\n{qc_barang}\n"
                        
                        if catatan:
                            konfirmasi_message += f"\n📝 *CATATAN:*\n{catatan}\n"
                        
                        konfirmasi_message += f"""\n{'='*35}

🔧 *STATUS: DALAM PROSES*

Mobil Anda sedang dalam proses pengerjaan.
Kami akan menghubungi Anda setelah selesai.

Terima kasih atas kepercayaan Anda! 🙏

📍 {toko_info.get('alamat', '')}
📞 {toko_info.get('telp', '')}"""
                        
                        whatsapp_link = create_whatsapp_link(telp_cust, konfirmasi_message)
                        
                        st.markdown("---")
                        st.markdown("### 📱 Konfirmasi Penerimaan Kendaraan")
                        st.markdown(f"**Customer:** {nama_cust}")
                        st.markdown(f"**No. Telp:** {telp_cust}")
                        st.link_button("💬 Kirim Konfirmasi via WhatsApp", whatsapp_link, use_container_width=True, type="primary")
                        
                        with st.expander("👁️ Preview Pesan Konfirmasi"):
                            st.text(konfirmasi_message)
                        
                        st.info("ℹ️ Silakan klik tombol di atas untuk mengirim konfirmasi penerimaan kendaraan ke customer")
                    else:
                        st.balloons()
                        st.rerun()
                else:
                    st.error(f"❌ {msg}")
    
    with tab2:
        st.markdown("""
        <div style="margin-bottom: 0.5rem;">
            <h4 style="margin: 0; color: #2d3436; font-size: 1.1rem; font-weight: 600; padding: 0.6rem 0; border-bottom: 2px solid #e0e0e0;">✅ Selesaikan Transaksi</h4>
        </div>
        """, unsafe_allow_html=True)
        
        checklist_selesai_items = get_checklist_selesai()
        
        # Load transaksi yang masih dalam proses - HANYA yang berstatus "Dalam Proses"
        df_trans = get_all_transactions()
        
        # PENTING: Filter KETAT hanya status "Dalam Proses" - EXACT MATCH
        df_proses = df_trans[df_trans['status'].str.strip() == 'Dalam Proses'].copy()
        
        # Reset index untuk menghindari masalah indexing
        df_proses = df_proses.reset_index(drop=True)
        
        # Debug info untuk Admin
        if st.session_state.get('role') == 'Admin':
            with st.expander("🔧 Debug Info (Admin Only)"):
                st.write(f"Total transaksi di database: {len(df_trans)}")
                st.write(f"Transaksi 'Dalam Proses': {len(df_proses)}")
                st.write(f"Transaksi 'Selesai': {len(df_trans[df_trans['status'] == 'Selesai'])}")
                if not df_trans.empty:
                    st.write("Status terakhir 5 transaksi:")
                    st.dataframe(df_trans[['id', 'nopol', 'tanggal', 'status']].head(5))
                
                # Tampilkan detail df_proses
                if not df_proses.empty:
                    st.write("Detail transaksi 'Dalam Proses':")
                    st.dataframe(df_proses[['id', 'nopol', 'tanggal', 'status', 'waktu_masuk']])
        
        if df_proses.empty:
            st.markdown("""
            <div style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); color: white; padding: 2rem; border-radius: 12px; text-align: center; margin: 2rem 0;">
                <div style="font-size: 3rem; margin-bottom: 1rem;">🎉</div>
                <div style="font-size: 1.3rem; font-weight: 600; margin-bottom: 0.5rem;">Semua Transaksi Selesai!</div>
                <div style="font-size: 1rem; opacity: 0.9;">Tidak ada transaksi yang sedang dalam proses</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1rem 1.5rem; border-radius: 10px; margin-bottom: 1rem; box-shadow: 0 3px 10px rgba(102, 126, 234, 0.3);">
                <div style="font-size: 1.1rem; font-weight: 600;">📋 {len(df_proses)} Transaksi Sedang Dalam Proses</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Tampilkan tabel transaksi dengan checkbox
            st.markdown("""
            <div style="margin: 1rem 0 0.5rem 0;">
                <h4 style="margin: 0; color: #2d3436; font-size: 1rem; font-weight: 600; padding: 0.6rem 0; border-bottom: 2px solid #e0e0e0;">📊 Daftar Transaksi Dalam Proses</h4>
            </div>
            """, unsafe_allow_html=True)
            
            # Buat tabel untuk display dengan checkbox
            df_display = df_proses[['id', 'tanggal', 'waktu_masuk', 'nopol', 'nama_customer', 'paket_cuci', 'harga']].copy()
            df_display.insert(0, 'Pilih', False)  # Tambahkan kolom checkbox di awal
            df_display['harga'] = df_display['harga'].apply(lambda x: f"Rp {x:,.0f}")
            df_display.columns = ['Pilih', 'ID', 'Tanggal', 'Jam Masuk', 'Nopol', 'Customer', 'Paket', 'Harga']
            
            # Tampilkan tabel dengan data editor untuk checkbox
            edited_df = st.data_editor(
                df_display,
                use_container_width=True,
                hide_index=True,
                height=min(400, (len(df_display) + 1) * 35 + 3),
                column_config={
                    "Pilih": st.column_config.CheckboxColumn(
                        "Pilih",
                        help="Centang untuk memilih transaksi",
                        default=False,
                    )
                },
                disabled=["ID", "Tanggal", "Jam Masuk", "Nopol", "Customer", "Paket", "Harga"],
                key="trans_table_editor"
            )
            
            # Cek apakah ada transaksi yang dipilih dari checkbox
            selected_rows = edited_df[edited_df['Pilih'] == True]
            
            if len(selected_rows) == 0:
                st.info("ℹ️ Centang checkbox pada tabel di atas untuk memilih transaksi yang akan diselesaikan")
            elif len(selected_rows) > 1:
                st.warning("⚠️ Silakan pilih hanya satu transaksi untuk diselesaikan")
            else:
                # Dapatkan ID dari transaksi yang dipilih
                selected_id = selected_rows.iloc[0]['ID']
                selected_trans = df_proses[df_proses['id'] == selected_id].iloc[0]
                
                # Double check status
                if selected_trans['status'].strip() != 'Dalam Proses':
                    st.error(f"❌ Error: Transaksi ini berstatus '{selected_trans['status']}', bukan 'Dalam Proses'")
                    st.warning("🔄 Halaman akan di-refresh otomatis...")
                    import time
                    time.sleep(2)
                    st.rerun()
                
                
                # Checklist Kondisi Saat Datang - harus dicheck ulang untuk memastikan kondisi tetap sesuai
                st.markdown("""
                <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px dashed #e0e0e0;">
                    <h4 style="margin: 0; color: #2d3436; font-size: 1rem; font-weight: 600; padding: 0.6rem 0; border-bottom: 2px solid #e0e0e0;">✅ Checklist Kondisi Saat Datang</h4>
                    <p style="font-size: 0.85rem; color: #6c757d; margin: 0.5rem 0;">⚠️ Pastikan kondisi setelah dibersihkan masih sesuai dengan saat datang</p>
                </div>
                """, unsafe_allow_html=True)
                
                selected_checks_datang_ulang = []
                try:
                    checks_datang = json.loads(selected_trans['checklist_datang'])
                    if checks_datang:
                        cols = st.columns(3)
                        for idx, check in enumerate(checks_datang):
                            with cols[idx % 3]:
                                # Checkbox untuk konfirmasi ulang kondisi masih sesuai
                                if st.checkbox(check, key=f"check_datang_ulang_{idx}", value=False):
                                    selected_checks_datang_ulang.append(check)
                    else:
                        st.info("ℹ️ Tidak ada checklist kondisi saat datang")
                except:
                    st.info("ℹ️ Tidak ada checklist kondisi saat datang")
                
                if selected_trans['qc_barang']:
                    st.markdown("""
                    <div style="margin-top: 0.8rem;">
                        <div style="font-size: 0.9rem; font-weight: 600; color: #2d3436; margin-bottom: 0.4rem;">📋 Barang dalam Mobil</div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.info(selected_trans['qc_barang'])
                
                if selected_trans['catatan']:
                    st.markdown("""
                    <div style="margin-top: 0.8rem;">
                        <div style="font-size: 0.9rem; font-weight: 600; color: #2d3436; margin-bottom: 0.4rem;">💬 Catatan Tambahan</div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.warning(selected_trans['catatan'])
            
                
                # Checklist selesai dengan design modern
                st.markdown("""
                <div style="margin: 1.5rem 0 0.5rem 0;">
                    <h4 style="margin: 0; color: #2d3436; font-size: 1rem; font-weight: 600; padding: 0.6rem 0; border-bottom: 2px solid #e0e0e0;">✅ Checklist QC Selesai Cuci</h4>
                </div>
                """, unsafe_allow_html=True)
                
                selected_checks_selesai = []
                cols = st.columns(3)
                for idx, item in enumerate(checklist_selesai_items):
                    with cols[idx % 3]:
                        if st.checkbox(item, key=f"check_done_{idx}", value=False):
                            selected_checks_selesai.append(item)
                
                # QC final barang dengan design modern
                st.markdown("""
                <div style="margin: 1.2rem 0 0.5rem 0;">
                    <h4 style="margin: 0; color: #2d3436; font-size: 1rem; font-weight: 600; padding: 0.6rem 0; border-bottom: 2px solid #e0e0e0;">📋 Konfirmasi Final</h4>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown("""
                <div style="margin: 0.5rem 0 0.3rem 0;">
                    <label style="font-weight: 600; color: #2d3436; font-size: 0.85rem;">✓ Konfirmasi Barang Customer Kembali Lengkap</label>
                </div>
                """, unsafe_allow_html=True)
                
                qc_final = st.text_area(
                    "Konfirmasi Barang",
                    value=selected_trans['qc_barang'],
                    placeholder="Pastikan semua barang customer kembali lengkap",
                    key="finish_qc", 
                    height=100,
                    label_visibility="collapsed"
                )
                
                st.markdown("""
                <div style="margin: 0.8rem 0 0.3rem 0;">
                    <label style="font-weight: 600; color: #2d3436; font-size: 0.85rem;">📝 Catatan Penyelesaian</label>
                </div>
                """, unsafe_allow_html=True)
                
                catatan_final = st.text_area(
                    "Catatan Penyelesaian",
                    placeholder="Hasil pengerjaan, kondisi akhir, dll...", 
                    key="finish_catatan", 
                    height=80,
                    label_visibility="collapsed"
                )
                
                # Finish button dengan design modern
                st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
                col1, col2, col3 = st.columns([1.5, 2, 1.5])
                with col2:
                    finish_btn = st.button("✅ Selesaikan Transaksi", type="primary", use_container_width=True, key="btn_finish_trans")
                
                if finish_btn:
                    # Validasi checklist minimal harus ada
                    if not selected_checks_datang_ulang:
                        st.error("❌ Mohon centang checklist kondisi saat datang untuk memastikan kondisi setelah dibersihkan masih sesuai!")
                    elif not selected_checks_selesai:
                        st.error("❌ Mohon pilih minimal 1 checklist QC selesai!")
                    elif not qc_final or qc_final.strip() == "":
                        st.error("❌ Mohon isi konfirmasi barang customer!")
                    else:
                        # Debug: tampilkan ID yang akan diupdate
                        st.warning(f"🔍 Akan mengupdate transaksi ID: **{selected_id}** (Tipe: {type(selected_id).__name__})")
                        
                        # Cek ulang status sebelum update (double check)
                        df_recheck = get_all_transactions()
                        matching_trans = df_recheck[df_recheck['id'] == selected_id]
                        
                        if len(matching_trans) == 0:
                            st.error(f"❌ Transaksi ID {selected_id} tidak ditemukan saat recheck!")
                            st.write("IDs yang ada:", df_recheck['id'].tolist()[:10])
                        else:
                            current_status = matching_trans['status'].iloc[0].strip()
                            
                            if current_status != 'Dalam Proses':
                                st.error(f"❌ Transaksi ini sudah berstatus '{current_status}'. Halaman akan di-refresh.")
                                import time
                                time.sleep(2)
                                st.rerun()
                            else:
                                # Pastikan ID adalah integer
                                trans_id_to_update = int(selected_id)
                                
                                # Gunakan waktu sistem otomatis saat tombol diklik
                                waktu_selesai_otomatis = datetime.now(WIB).strftime('%H:%M:%S')
                                
                                success, msg = update_transaction_finish(
                                    trans_id_to_update,
                                    waktu_selesai_otomatis,
                                    json.dumps(selected_checks_selesai),
                                    qc_final,
                                    catatan_final
                                )
                                
                                if success:
                                    add_audit("transaksi_selesai", f"ID: {selected_id}, Nopol: {selected_trans['nopol']}")
                                    
                                    # Clear any session state cache
                                    if 'finish_trans' in st.session_state:
                                        del st.session_state['finish_trans']
                                    
                                    st.success(f"✅ {msg} - Transaksi telah dipindahkan ke status Selesai")
                                    st.balloons()
                                    import time
                                    time.sleep(1)  # Delay untuk memastikan database ter-commit
                                    st.rerun()
                                else:
                                    st.error(f"❌ {msg}")
    
    with tab3:
        st.subheader("📚 History Customer - Transaksi Selesai")
        
        # Load transaksi yang sudah selesai
        df_trans = get_all_transactions()
        df_selesai = df_trans[df_trans['status'] == 'Selesai'].copy()
        
        if df_selesai.empty:
            st.info("📭 Belum ada transaksi yang selesai")
        else:
            st.success(f"📋 **{len(df_selesai)} transaksi** telah selesai dikerjakan")
            
            # Filter pencarian
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                search_nopol = st.text_input("🔍 Cari Nopol", key="search_history_nopol")
            with col2:
                search_customer = st.text_input("🔍 Cari Nama Customer", key="search_history_customer")
            
            # Apply filter
            if search_nopol:
                df_selesai = df_selesai[df_selesai['nopol'].str.contains(search_nopol, case=False, na=False)]
            if search_customer:
                df_selesai = df_selesai[df_selesai['nama_customer'].str.contains(search_customer, case=False, na=False)]
            
            # Tampilkan tabel history
            if not df_selesai.empty:
                st.markdown("---")
                
                # Tabel dengan checkbox
                st.markdown("### 📊 Daftar Transaksi Selesai")
                df_display = df_selesai[['id', 'tanggal', 'waktu_masuk', 'waktu_selesai', 'nopol', 'nama_customer', 'paket_cuci', 'harga']].copy()
                df_display.insert(0, 'Pilih', False)  # Tambahkan kolom checkbox
                df_display['harga'] = df_display['harga'].apply(lambda x: f"Rp {x:,.0f}")
                df_display.columns = ['Pilih', 'ID', '📅 Tanggal', '⏰ Masuk', '⏰ Selesai', '🔖 Nopol', '👤 Customer', '📦 Paket', '💰 Harga']
                
                # Tampilkan tabel dengan data editor untuk checkbox
                edited_df_selesai = st.data_editor(
                    df_display,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Pilih": st.column_config.CheckboxColumn(
                            "Pilih",
                            help="Centang untuk melihat detail atau kirim invoice",
                            default=False,
                        )
                    },
                    disabled=["ID", "📅 Tanggal", "⏰ Masuk", "⏰ Selesai", "🔖 Nopol", "👤 Customer", "📦 Paket", "💰 Harga"],
                    key="history_table_editor"
                )
                
                # Cek apakah ada transaksi yang dipilih
                selected_rows_selesai = edited_df_selesai[edited_df_selesai['Pilih'] == True]
                
                if len(selected_rows_selesai) > 0:
                    if len(selected_rows_selesai) > 1:
                        st.warning("⚠️ Silakan pilih hanya satu transaksi untuk melihat detail")
                    else:
                        # Ambil transaksi yang dipilih
                        selected_hist_id = selected_rows_selesai.iloc[0]['ID']
                        selected_hist = df_selesai[df_selesai['id'] == selected_hist_id].iloc[0]
                        
                        st.markdown("---")
                        st.markdown("### 📋 Detail Transaksi Terpilih")
                        
                        # Detail lengkap
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.markdown("**📋 Info Dasar**")
                            st.write(f"🔖 Nopol: `{selected_hist['nopol']}`")
                            st.write(f"👤 Customer: {selected_hist['nama_customer']}")
                            # Ambil telp dari tabel customer jika ada
                            cust_data = get_customer_by_nopol(selected_hist['nopol'])
                            telp_display = cust_data['no_telp'] if cust_data and cust_data.get('no_telp') else '-'
                            st.write(f"📞 Telp: {telp_display}")
                            st.write(f"📦 Paket: {selected_hist['paket_cuci']}")
                            st.write(f"💰 Harga: Rp {selected_hist['harga']:,.0f}")
                            
                            # Info Kendaraan
                            if selected_hist.get('jenis_kendaraan') or selected_hist.get('merk_kendaraan') or selected_hist.get('ukuran_mobil'):
                                st.markdown("**🚗 Info Kendaraan**")
                                if selected_hist.get('jenis_kendaraan'):
                                    st.write(f"Jenis: {selected_hist['jenis_kendaraan']}")
                                if selected_hist.get('merk_kendaraan'):
                                    st.write(f"Merk: {selected_hist['merk_kendaraan']}")
                                if selected_hist.get('ukuran_mobil'):
                                    st.write(f"Ukuran: {selected_hist['ukuran_mobil']}")
                        
                        with col2:
                            st.markdown("**⏰ Waktu**")
                            st.write(f"📅 Tanggal: {selected_hist['tanggal']}")
                            st.write(f"🕐 Masuk: {selected_hist['waktu_masuk']}")
                            st.write(f"🕐 Selesai: {selected_hist['waktu_selesai']}")
                            st.write(f"👤 Oleh: {selected_hist['created_by']}")
                        
                        with col3:
                            st.markdown("**✅ Checklist & QC**")
                            try:
                                checks = json.loads(selected_hist['checklist_datang'])
                                st.write("Saat Datang:")
                                for check in checks[:3]:
                                    st.write(f"✓ {check}")
                            except:
                                pass
                            
                            try:
                                checks_done = json.loads(selected_hist['checklist_selesai'])
                                st.write("Saat Selesai:")
                                for check in checks_done[:3]:
                                    st.write(f"✓ {check}")
                            except:
                                pass
                        
                        if selected_hist['catatan']:
                            st.markdown("**💬 Catatan:**")
                            st.info(selected_hist['catatan'])
                        
                        # Tombol kirim invoice via WhatsApp
                        st.markdown("---")
                        st.markdown("**📱 Kirim Invoice via WhatsApp**")
                        
                        # Ambil nomor telepon customer
                        cust_data = get_customer_by_nopol(selected_hist['nopol'])
                        phone_number = cust_data['no_telp'] if cust_data and cust_data.get('no_telp') else None
                        
                        if phone_number and phone_number.strip():
                            col_wa1, col_wa2 = st.columns([3, 2])
                            with col_wa1:
                                st.info(f"📞 Nomor Tujuan: **{phone_number}**")
                            with col_wa2:
                                # Generate invoice message
                                toko_info = get_setting("toko_info") or {
                                    "nama": "TIME AUTOCARE",
                                    "tagline": "Detailing & Ceramic Coating",
                                    "alamat": "Jl. Contoh No. 123",
                                    "telp": "08123456789",
                                    "email": "info@timeautocare.com"
                                }
                                
                                invoice_message = generate_invoice_message(selected_hist.to_dict(), toko_info)
                                wa_link = create_whatsapp_link(phone_number, invoice_message)
                                
                                # Tombol WhatsApp dengan link
                                st.markdown(f"""
                                    <a href="{wa_link}" target="_blank">
                                        <button style="
                                            background: linear-gradient(135deg, #25D366 0%, #128C7E 100%);
                                            color: white;
                                            border: none;
                                            padding: 12px 24px;
                                            border-radius: 10px;
                                            font-size: 16px;
                                            font-weight: 600;
                                            cursor: pointer;
                                            box-shadow: 0 4px 15px rgba(37, 211, 102, 0.3);
                                            width: 100%;
                                            transition: all 0.3s ease;
                                        " onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 6px 20px rgba(37, 211, 102, 0.4)';" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 15px rgba(37, 211, 102, 0.3)';">
                                            💬 Kirim Invoice
                                        </button>
                                    </a>
                                """, unsafe_allow_html=True)
                            
                            # Preview pesan
                            with st.expander("👁️ Preview Pesan Invoice"):
                                st.text(invoice_message)
                        else:
                            st.warning("⚠️ Nomor telepon customer belum terdaftar. Silakan update data customer terlebih dahulu.")
                else:
                    st.info("ℹ️ Centang checkbox pada tabel untuk melihat detail transaksi dan mengirim invoice")
            else:
                st.warning("⚠️ Tidak ada transaksi yang sesuai dengan pencarian")
    
    with tab4:
        st.markdown("""
        <div style="margin-bottom: 0.5rem;">
            <h4 style="margin: 0; color: #2d3436; font-size: 1.1rem; font-weight: 600; padding: 0.6rem 0; border-bottom: 2px solid #e0e0e0;">✏️ Edit / Hapus Transaksi Cuci Mobil</h4>
        </div>
        """, unsafe_allow_html=True)
        
        df_all_trans = get_all_transactions()
        
        if df_all_trans.empty:
            st.info("📭 Belum ada transaksi untuk diedit atau dihapus")
        else:
            st.warning("⚠️ Hanya dapat mengedit/menghapus transaksi yang belum masuk kasir")
            
            # Filter only transactions not in kasir
            df_editable = df_all_trans.copy()
            
            # Select transaction
            trans_options = {}
            for _, row in df_editable.iterrows():
                label = f"ID:{row['id']} | {row['tanggal']} | {row['nopol']} - {row['nama_customer']} | {row['paket_cuci']} | {row['status']}"
                trans_options[label] = row
            
            if trans_options:
                selected_trans = st.selectbox("Pilih Transaksi", list(trans_options.keys()), key="select_trans_edit")
                
                if selected_trans:
                    trans_data = trans_options[selected_trans]
                    
                    col_edit, col_delete = st.columns([3, 1])
                    
                    with col_edit:
                        st.markdown("#### ✏️ Edit Transaksi")
                        with st.form("edit_trans_form"):
                            st.info(f"📝 Edit transaksi ID: **{trans_data['id']}** - Nopol: **{trans_data['nopol']}**")
                            
                            # Get current paket options
                            paket_cucian = get_paket_cucian()
                            paket_list = list(paket_cucian.keys())
                            current_paket_idx = paket_list.index(trans_data['paket_cuci']) if trans_data['paket_cuci'] in paket_list else 0
                            
                            edit_paket = st.selectbox("Paket Cuci *", options=paket_list, index=current_paket_idx)
                            edit_harga = st.number_input("Harga (Rp) *", value=int(trans_data['harga']), min_value=0, step=10000)
                            edit_catatan = st.text_area("Catatan", value=trans_data['catatan'] or "")
                            
                            col_btn1, col_btn2 = st.columns(2)
                            with col_btn1:
                                submit_edit = st.form_submit_button("💾 Update Transaksi", type="primary", use_container_width=True)
                            with col_btn2:
                                cancel = st.form_submit_button("❌ Batal", use_container_width=True)
                            
                            if submit_edit:
                                success, msg = update_wash_transaction(
                                    trans_data['id'], edit_paket, edit_harga, edit_catatan
                                )
                                if success:
                                    add_audit("update_wash_trans", f"Update transaksi ID:{trans_data['id']} - {trans_data['nopol']}")
                                    st.success(f"✅ {msg}")
                                    st.balloons()
                                    st.rerun()
                                else:
                                    st.error(f"❌ {msg}")
                    
                    with col_delete:
                        st.markdown("#### 🗑️ Hapus Transaksi")
                        st.warning("⚠️ Aksi ini tidak dapat dibatalkan!")
                        
                        if st.button("🗑️ Hapus Transaksi", type="primary", use_container_width=True, key="delete_trans_btn"):
                            success, msg = delete_wash_transaction(trans_data['id'])
                            if success:
                                add_audit("delete_wash_trans", f"Hapus transaksi ID:{trans_data['id']} - {trans_data['nopol']}")
                                st.success(f"✅ {msg}")
                                st.rerun()
                            else:
                                st.error(f"❌ {msg}")
            else:
                st.info("📭 Semua transaksi sudah masuk kasir. Tidak ada yang bisa diedit.")
    
    with tab5:
        # Setting Paket Cuci
        st.markdown("""
        <div style="margin-bottom: 0.5rem;">
            <h4 style="margin: 0; color: #2d3436; font-size: 1.1rem; font-weight: 600; padding: 0.6rem 0; border-bottom: 2px solid #e0e0e0;">⚙️ Pengaturan Paket Cuci & Checklist</h4>
        </div>
        """, unsafe_allow_html=True)
        
        # Check role
        if role not in ["Admin", "Supervisor"]:
            st.warning("⚠️ Hanya Admin dan Supervisor yang dapat mengakses setting ini")
        else:
            subtab1, subtab2, subtab3, subtab4 = st.tabs(["📦 Paket Cuci", "🚗 Multiplier Ukuran", "✅ Checklist Datang", "✓ Checklist Selesai"])
            
            with subtab1:
                st.markdown("##### 📦 Kelola Paket Cucian")
                
                # Load paket cucian
                paket_cucian = get_paket_cucian()
                
                st.info("ℹ️ Tambah, edit, atau hapus paket cucian yang tersedia")
                
                # Tampilkan paket yang ada
                st.markdown("**Paket Cucian Saat Ini:**")
                menu_updated = paket_cucian.copy()
                
                for idx, (nama, harga) in enumerate(paket_cucian.items()):
                    col1, col2, col3 = st.columns([3, 2, 1])
                    with col1:
                        new_nama = st.text_input("Nama Paket", value=nama, key=f"paket_nama_{idx}", label_visibility="collapsed")
                    with col2:
                        new_harga = st.number_input("Harga", value=int(harga), min_value=0, step=5000, key=f"paket_harga_{idx}", label_visibility="collapsed")
                    with col3:
                        if st.button("🗑️", key=f"del_paket_{idx}", help="Hapus paket ini"):
                            del menu_updated[nama]
                            success, msg = update_setting("paket_cucian", menu_updated)
                            if success:
                                st.success(f"✅ {nama} berhasil dihapus")
                                add_audit("paket_delete", f"Hapus paket: {nama}")
                                st.rerun()
                            else:
                                st.error(msg)
                    
                    # Update jika berubah
                    if new_nama != nama or new_harga != harga:
                        if new_nama and new_harga > 0:
                            if nama in menu_updated:
                                del menu_updated[nama]
                            menu_updated[new_nama] = new_harga
                
                st.markdown("---")
                
                # Tambah paket baru
                st.markdown("**➕ Tambah Paket Baru:**")
                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    nama_baru = st.text_input("Nama Paket Baru", key="new_paket_nama", placeholder="Contoh: Cuci Express")
                with col2:
                    harga_baru = st.number_input("Harga", value=50000, min_value=0, step=5000, key="new_paket_harga")
                with col3:
                    if st.button("➕ Tambah", key="add_paket"):
                        if nama_baru and harga_baru > 0:
                            if nama_baru in menu_updated:
                                st.error(f"❌ Paket '{nama_baru}' sudah ada!")
                            else:
                                menu_updated[nama_baru] = harga_baru
                                success, msg = update_setting("paket_cucian", menu_updated)
                                if success:
                                    st.success(f"✅ Paket '{nama_baru}' berhasil ditambahkan")
                                    add_audit("paket_add", f"Tambah paket: {nama_baru} - Rp {harga_baru:,.0f}")
                                    st.rerun()
                                else:
                                    st.error(msg)
                        else:
                            st.error("❌ Mohon isi nama dan harga paket")
                
                st.markdown("---")
                
                if st.button("💾 Simpan Semua Perubahan Paket", type="primary", use_container_width=True):
                    success, msg = update_setting("paket_cucian", menu_updated)
                    if success:
                        st.success("✅ Semua perubahan paket berhasil disimpan!")
                        add_audit("paket_update", "Update paket cucian")
                        st.rerun()
                    else:
                        st.error(msg)
            
            with subtab2:
                st.markdown("##### 🚗 Multiplier Harga Berdasarkan Ukuran Mobil")
                
                st.info("ℹ️ Atur multiplier harga untuk setiap ukuran mobil. Harga paket akan dikalikan dengan multiplier ini.")
                
                # Load multiplier saat ini
                multiplier_map = get_ukuran_multiplier()
                
                st.markdown("**Multiplier Saat Ini:**")
                
                # Form untuk edit multiplier
                with st.form("multiplier_form"):
                    new_multiplier = {}
                    
                    ukuran_list = ["Kecil", "Sedang", "Besar", "Extra Besar"]
                    
                    for ukuran in ukuran_list:
                        col1, col2, col3 = st.columns([2, 2, 3])
                        with col1:
                            st.markdown(f"**{ukuran}**")
                        with col2:
                            current_value = multiplier_map.get(ukuran, 1.0)
                            new_value = st.number_input(
                                f"Multiplier {ukuran}",
                                value=float(current_value),
                                min_value=0.5,
                                max_value=5.0,
                                step=0.1,
                                key=f"mult_{ukuran}",
                                label_visibility="collapsed"
                            )
                            new_multiplier[ukuran] = new_value
                        with col3:
                            # Contoh perhitungan
                            example_price = 100000
                            final_price = int(example_price * new_value)
                            st.caption(f"Contoh: Rp 100.000 → Rp {final_price:,}")
                    
                    st.markdown("---")
                    
                    col1, col2, col3 = st.columns([1, 2, 1])
                    with col2:
                        submit_multiplier = st.form_submit_button("💾 Simpan Multiplier", type="primary", use_container_width=True)
                    
                    if submit_multiplier:
                        success, msg = update_setting("ukuran_multiplier", new_multiplier)
                        if success:
                            st.success("✅ Multiplier berhasil disimpan!")
                            add_audit("multiplier_update", f"Update multiplier ukuran mobil")
                            st.balloons()
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")
                
                # Info tambahan
                st.markdown("---")
                st.markdown("**ℹ️ Cara Kerja:**")
                st.write("- Multiplier akan mengalikan harga paket dasar dengan nilai yang ditentukan")
                st.write("- Contoh: Paket Rp 50.000 dengan multiplier 1.5 = Rp 75.000")
                st.write("- Multiplier 1.0 = harga tetap (tidak ada tambahan)")
            
            with subtab3:
                st.markdown("##### ✅ Kelola Checklist Mobil Datang")
                
                checklist_datang = get_checklist_datang()
                
                st.info("ℹ️ Checklist untuk memeriksa kondisi mobil saat pertama datang")
                
                # Tampilkan checklist yang ada
                new_checklist = []
                for idx, item in enumerate(checklist_datang):
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        new_item = st.text_input(f"Item {idx+1}", value=item, key=f"check_datang_{idx}", label_visibility="collapsed")
                        if new_item:
                            new_checklist.append(new_item)
                    with col2:
                        if st.button("🗑️", key=f"del_check_datang_{idx}", help="Hapus item"):
                            pass  # Item akan terhapus karena tidak masuk new_checklist
                
                st.markdown("---")
                
                # Tambah item baru
                st.markdown("**➕ Tambah Item Baru:**")
                col1, col2 = st.columns([5, 1])
                with col1:
                    item_baru = st.text_input("Item Checklist Baru", key="new_check_datang", placeholder="Contoh: Kondisi interior bersih")
                with col2:
                    if st.button("➕", key="add_check_datang"):
                        if item_baru:
                            new_checklist.append(item_baru)
                            success, msg = update_setting("checklist_datang", new_checklist)
                            if success:
                                st.success(f"✅ Item '{item_baru}' berhasil ditambahkan")
                                add_audit("checklist_add", f"Tambah checklist datang: {item_baru}")
                                st.rerun()
                            else:
                                st.error(msg)
                        else:
                            st.error("❌ Mohon isi item checklist")
                
                st.markdown("---")
                
                if st.button("💾 Simpan Perubahan Checklist", type="primary", use_container_width=True, key="save_checklist_datang"):
                    success, msg = update_setting("checklist_datang", new_checklist if new_checklist else checklist_datang)
                    if success:
                        st.success("✅ Checklist datang berhasil disimpan!")
                        add_audit("checklist_update", "Update checklist datang")
                        st.rerun()
                    else:
                        st.error(msg)
            
            with subtab4:
                st.markdown("##### ✓ Kelola Checklist QC Selesai")
                
                checklist_selesai = get_checklist_selesai()
                
                st.info("ℹ️ Checklist untuk quality control setelah selesai cuci")
                
                # Tampilkan checklist yang ada
                new_checklist_selesai = []
                for idx, item in enumerate(checklist_selesai):
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        new_item = st.text_input(f"Item {idx+1}", value=item, key=f"check_selesai_{idx}", label_visibility="collapsed")
                        if new_item:
                            new_checklist_selesai.append(new_item)
                    with col2:
                        if st.button("🗑️", key=f"del_check_selesai_{idx}", help="Hapus item"):
                            pass  # Item akan terhapus karena tidak masuk new_checklist_selesai
                
                st.markdown("---")
                
                # Tambah item baru
                st.markdown("**➕ Tambah Item Baru:**")
                col1, col2 = st.columns([5, 1])
                with col1:
                    item_baru_selesai = st.text_input("Item Checklist Baru", key="new_check_selesai", placeholder="Contoh: Velg mengkilap")
                with col2:
                    if st.button("➕", key="add_check_selesai"):
                        if item_baru_selesai:
                            new_checklist_selesai.append(item_baru_selesai)
                            success, msg = update_setting("checklist_selesai", new_checklist_selesai)
                            if success:
                                st.success(f"✅ Item '{item_baru_selesai}' berhasil ditambahkan")
                                add_audit("checklist_add", f"Tambah checklist selesai: {item_baru_selesai}")
                                st.rerun()
                            else:
                                st.error(msg)
                        else:
                            st.error("❌ Mohon isi item checklist")
                
                st.markdown("---")
                
                if st.button("💾 Simpan Perubahan Checklist", type="primary", use_container_width=True, key="save_checklist_selesai"):
                    success, msg = update_setting("checklist_selesai", new_checklist_selesai if new_checklist_selesai else checklist_selesai)
                    if success:
                        st.success("✅ Checklist selesai berhasil disimpan!")
                        add_audit("checklist_update", "Update checklist selesai")
                        st.rerun()
                    else:
                        st.error(msg)


def kasir_page(role):
    st.markdown("""
    <style>
    .kasir-header { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 1.2rem; border-radius: 12px; color: white; margin-bottom: 1rem; box-shadow: 0 4px 15px rgba(17, 153, 142, 0.3); }
    .kasir-card { background: white; padding: 1rem; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.06); }
    .pending-wash { background: #fff3cd; padding: 1rem; border-left: 4px solid #ffc107; border-radius: 8px; margin-bottom: 1rem; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="kasir-header"><h2>💰 KASIR</h2><p>Pusat Transaksi - Cuci Mobil & Coffee Shop</p></div>', unsafe_allow_html=True)

    # Hitung jumlah transaksi untuk badge
    df_sales_check = get_all_coffee_sales()
    df_kasir_check = get_all_kasir_transactions()
    jumlah_history_coffee = len(df_sales_check)
    jumlah_history_kasir = len(df_kasir_check)
    
    # Ambil transaksi cuci mobil yang pending pembayaran (status 'Dalam Proses' atau 'Selesai')
    df_pending = get_pending_wash_transactions()
    jumlah_pending = len(df_pending)
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        f"💰 Transaksi Kasir ({jumlah_pending} Pending)",
        f"☕️ Coffee Shop ({jumlah_history_coffee})",
        f"📜 History Kasir ({jumlah_history_kasir})",
        "✏️ Edit/Hapus Transaksi",
        "⚙️ Setting Menu"
    ])
    
    with tab1:
        st.subheader("💰 Transaksi Kasir - Pembayaran")
        st.info("💡 **Alur:** SPV input data cuci mobil → Data masuk ke Kasir → Customer bayar di sini")
        
        # Tampilkan daftar mobil yang pending pembayaran dalam bentuk tabel
        wash_trans_selected = None
        
        if not df_pending.empty:
            st.markdown("---")
            st.markdown("### 🚗 Mobil Pending Pembayaran")
            st.warning(f"⚠️ Ada **{len(df_pending)}** transaksi cuci mobil yang menunggu pembayaran")
            
            # Buat tabel dengan checkbox
            df_display = df_pending[['id', 'nopol', 'nama_customer', 'paket_cuci', 'tanggal', 'waktu_masuk', 'status', 'harga', 'created_by']].copy()
            df_display.insert(0, 'Pilih', False)
            df_display['harga'] = df_display['harga'].apply(lambda x: f"Rp {x:,.0f}")
            df_display.columns = ['Pilih', 'ID', 'Nopol', 'Customer', 'Paket', 'Tanggal', 'Jam Masuk', 'Status', 'Harga', 'SPV']
            
            # Tampilkan tabel dengan data editor
            edited_df = st.data_editor(
                df_display,
                use_container_width=True,
                hide_index=True,
                height=min(400, (len(df_display) + 1) * 35 + 3),
                column_config={
                    "Pilih": st.column_config.CheckboxColumn(
                        "Pilih",
                        help="Centang untuk memilih transaksi yang akan diproses",
                        default=False,
                    )
                },
                disabled=["ID", "Nopol", "Customer", "Paket", "Tanggal", "Jam Masuk", "Status", "Harga", "SPV"],
                key="pending_wash_table"
            )
            
            # Cek apakah ada yang dipilih
            selected_rows = edited_df[edited_df['Pilih'] == True]
            
            if len(selected_rows) > 1:
                st.warning("⚠️ Silakan pilih hanya satu transaksi untuk diproses")
            elif len(selected_rows) == 1:
                # Ambil data transaksi yang dipilih
                selected_id = selected_rows.iloc[0]['ID']
                wash_trans_selected = df_pending[df_pending['id'] == selected_id].iloc[0]
                
                # Tampilkan info transaksi yang dipilih
                st.success(f"✅ Dipilih: **{wash_trans_selected['nopol']}** - {wash_trans_selected['nama_customer']} | {wash_trans_selected['paket_cuci']} | Rp {wash_trans_selected['harga']:,.0f}")
        
        st.markdown("---")
        
        # Form pembayaran - hanya tampil jika ada transaksi yang dipilih atau tidak ada pending
        if wash_trans_selected is not None or df_pending.empty:
            st.markdown("### 💳 Form Pembayaran")
            
            # Data customer
            st.markdown("##### 👤 Data Customer")
            col1, col2, col3 = st.columns(3)
            
            # Auto-fill dari wash transaction jika dipilih
            default_nopol = wash_trans_selected['nopol'] if wash_trans_selected is not None else ""
            default_nama = wash_trans_selected['nama_customer'] if wash_trans_selected is not None else ""
            
            # Get customer info if nopol is available
            customer_telp = ""
            if default_nopol:
                cust_data = get_customer_by_nopol(default_nopol)
                if cust_data:
                    customer_telp = cust_data.get('no_telp', '')
            
            with col1:
                nopol_input = st.text_input("No. Polisi", value=default_nopol, key="kasir_nopol", placeholder="B1234XYZ")
            with col2:
                nama_input = st.text_input("Nama Customer", value=default_nama, key="kasir_nama", placeholder="Nama customer")
            with col3:
                telp_input = st.text_input("No. WhatsApp", value=customer_telp, key="kasir_telp", placeholder="08xxx atau 628xxx")
            
            # Coffee/Snack order
            st.markdown("---")
            st.markdown("##### ☕️ Tambah Coffee/Snack (Opsional)")
            
            menu = get_coffee_menu()
            coffee_order = {}
            
            if menu:
                for idx, (name, price) in enumerate(menu.items()):
                    c1, c2 = st.columns([3,1])
                    with c1:
                        st.write(f"**{name}** - Rp {price:,.0f}")
                    with c2:
                        qty = st.number_input(f"Qty", min_value=0, value=0, key=f"kasir_coffee_qty_{idx}", label_visibility="collapsed")
                    if qty and qty > 0:
                        coffee_order[name] = { 'price': price, 'qty': int(qty), 'subtotal': price * int(qty) }
            
            # Ringkasan pembayaran
            st.markdown("---")
            st.markdown("### 🧾 Ringkasan Pembayaran")
            
            harga_cuci = int(wash_trans_selected['harga']) if wash_trans_selected is not None else 0
            harga_coffee = sum(v['subtotal'] for v in coffee_order.values()) if coffee_order else 0
            total_bayar = harga_cuci + harga_coffee
            
            col1, col2 = st.columns(2)
            with col1:
                if wash_trans_selected is not None:
                    st.metric("🚗 Biaya Cuci Mobil", f"Rp {harga_cuci:,.0f}")
                if coffee_order:
                    st.metric("☕️ Biaya Coffee/Snack", f"Rp {harga_coffee:,.0f}")
            with col2:
                st.metric("💰 TOTAL PEMBAYARAN", f"Rp {total_bayar:,.0f}")
            
            # Detail coffee order jika ada
            if coffee_order:
                with st.expander("📋 Detail Pesanan Coffee/Snack"):
                    df_coffee = pd.DataFrame([{
                        'Item': k,
                        'Harga': f"Rp {v['price']:,.0f}",
                        'Qty': v['qty'],
                        'Subtotal': f"Rp {v['subtotal']:,.0f}"
                    } for k, v in coffee_order.items()])
                    st.table(df_coffee)
            
            # Catatan
            catatan_kasir = st.text_area("Catatan (Opsional)", key="catatan_kasir", placeholder="Catatan tambahan...")
            
            # Tombol simpan transaksi
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                save_kasir_btn = st.button("💾 SIMPAN & PROSES PEMBAYARAN", type="primary", use_container_width=True, key="save_kasir_trans")
            
            if save_kasir_btn:
                # Validasi
                if not nopol_input or not nama_input:
                    st.error("❌ Nopol dan Nama Customer harus diisi!")
                elif total_bayar <= 0:
                    st.error("❌ Minimal harus ada transaksi cuci mobil atau coffee!")
                else:
                    now_wib = datetime.now(WIB)
                    
                    # Siapkan data transaksi kasir
                    kasir_data = {
                        'nopol': nopol_input,
                        'nama_customer': nama_input,
                        'no_telp': telp_input,
                        'tanggal': now_wib.strftime('%d-%m-%Y'),
                        'waktu': now_wib.strftime('%H:%M:%S'),
                        'wash_trans_id': int(wash_trans_selected['id']) if wash_trans_selected is not None else None,
                        'paket_cuci': wash_trans_selected['paket_cuci'] if wash_trans_selected is not None else '',
                        'harga_cuci': harga_cuci,
                        'coffee_items': json.dumps([{'name': k, 'price': v['price'], 'qty': v['qty'], 'subtotal': v['subtotal']} for k, v in coffee_order.items()], ensure_ascii=False) if coffee_order else '',
                        'harga_coffee': harga_coffee,
                        'total_bayar': total_bayar,
                        'status_bayar': 'Lunas',  # Default Lunas
                        'metode_bayar': 'Tunai',  # Default Tunai
                        'created_by': st.session_state.get('login_user', ''),
                        'catatan': catatan_kasir
                    }
                    
                    success, msg, secret_code = save_kasir_transaction(kasir_data)
                    
                    if success:
                        st.success("✅ " + msg)
                        add_audit('kasir_transaction', f"Transaksi kasir {nopol_input} - Total: Rp {total_bayar:,.0f}")
                        
                        # Add secret_code to kasir_data for invoice
                        kasir_data['secret_code'] = secret_code
                        
                        # Generate WhatsApp invoice if phone number is provided
                        if telp_input:
                            toko_info = get_toko_info()
                            invoice_text = generate_kasir_invoice(kasir_data, toko_info)
                            whatsapp_link = create_whatsapp_link(telp_input, invoice_text)
                            
                            st.markdown("---")
                            st.markdown("### 📱 Invoice WhatsApp")
                            st.success(f"✅ Transaksi berhasil! Kirim invoice ke **{nama_input}**")
                            st.info(f"🔑 **Kode Review:** `{secret_code}` (Customer dapat memberikan review dengan kode ini)")
                            st.link_button("💬 Kirim Invoice via WhatsApp", whatsapp_link, use_container_width=True)
                            
                            with st.expander("👁️ Preview Invoice"):
                                st.text(invoice_text)
                        else:
                            st.rerun()
                    else:
                        st.error("❌ " + msg)
        else:
            st.info("ℹ️ Pilih salah satu transaksi dari tabel di atas untuk memproses pembayaran")
    
    with tab2:
        # Sub-tabs untuk Coffee Shop
        coffee_tab1, coffee_tab2 = st.tabs(["📝 Transaksi Coffee", "📜 History Coffee"])
        
        with coffee_tab1:
            st.subheader('☕️ Penjualan Coffee & Snack')
            st.info("💡 Untuk penjualan coffee/snack tanpa transaksi cuci mobil")
            
            menu = get_coffee_menu()
            if not menu:
                st.info("Belum ada menu coffee. Silakan hubungi Admin untuk menambahkan menu.")
            else:
                # Input customer info
                st.markdown("##### 👤 Data Customer (Opsional)")
                col1, col2 = st.columns(2)
                with col1:
                    nama_customer = st.text_input("Nama Customer", placeholder="Nama customer (opsional)", key="coffee_only_customer_name")
                with col2:
                    no_telp = st.text_input("No. WhatsApp", placeholder="08xxx atau 628xxx (opsional)", key="coffee_only_customer_wa")
                
                st.markdown("---")
                st.markdown("##### 📋 Menu Coffee & Snack")

                # Build order form
                order = {}
                for idx, (name, price) in enumerate(menu.items()):
                    c1, c2 = st.columns([3,1])
                    with c1:
                        st.write(f"**{name}** - Rp {price:,.0f}")
                    with c2:
                        qty = st.number_input(f"Qty", min_value=0, value=0, key=f"coffee_only_qty_{idx}", label_visibility="collapsed")
                    if qty and qty > 0:
                        order[name] = { 'price': price, 'qty': int(qty), 'subtotal': price * int(qty) }

                if order:
                    st.markdown("---")
                    st.subheader("🧾 Ringkasan Order")
                    df_order = pd.DataFrame([{
                        'Item': k,
                        'Harga': v['price'],
                        'Qty': v['qty'],
                        'Subtotal': v['subtotal']
                    } for k, v in order.items()])
                    df_order['Harga'] = df_order['Harga'].apply(lambda x: f"Rp {x:,.0f}")
                    df_order['Subtotal'] = df_order['Subtotal'].apply(lambda x: f"Rp {x:,.0f}")
                    st.table(df_order)

                    total = sum(v['subtotal'] for v in order.values())
                    st.success(f"💰 **Total: Rp {total:,.0f}**")

                    col1, col2, col3 = st.columns([2, 1, 2])
                    with col2:
                        save_btn = st.button("💾 Simpan Penjualan", type="primary", use_container_width=True, key="save_coffee_only_sale")

                    if save_btn:
                        now_wib = datetime.now(WIB)
                        trans = {
                            'items': [{'name': k, 'price': v['price'], 'qty': v['qty']} for k, v in order.items()],
                            'total': total,
                            'tanggal': now_wib.strftime('%d-%m-%Y'),
                            'waktu': now_wib.strftime('%H:%M:%S'),
                            'nama_customer': nama_customer,
                            'no_telp': no_telp,
                            'created_by': st.session_state.get('login_user', '')
                        }
                        success, msg = save_coffee_sale(trans)
                        if success:
                            st.success(msg)
                            add_audit('coffee_sale', f"Penjualan coffee total Rp {total:,.0f}")
                            
                            # Generate WhatsApp invoice if phone number is provided
                            if no_telp:
                                toko_info = get_toko_info()
                                invoice_text = generate_coffee_invoice(trans, toko_info)
                                whatsapp_link = create_whatsapp_link(no_telp, invoice_text)
                                
                                st.markdown("---")
                                st.markdown("### 📱 Invoice WhatsApp")
                                st.markdown(f"**Customer:** {nama_customer if nama_customer else 'Walk-in Customer'}")
                                st.link_button("💬 Kirim Invoice via WhatsApp", whatsapp_link, use_container_width=True)
                                
                                with st.expander("👁️ Preview Invoice"):
                                    st.text(invoice_text)
                            else:
                                st.rerun()
                        else:
                            st.error(msg)
                else:
                    st.info("📭 Belum ada item dipilih untuk dipesan. Silakan pilih menu dan masukkan jumlah.")
        
        with coffee_tab2:
            st.subheader('📜 History Penjualan Coffee')
            st.info("💡 Riwayat penjualan coffee/snack tanpa transaksi cuci mobil")
            
            df_sales = get_all_coffee_sales()
            if df_sales.empty:
                st.info('📭 Belum ada penjualan coffee tersimpan')
            else:
                # Filter pencarian
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    search_date = st.text_input("🔍 Cari Tanggal", placeholder="dd-mm-yyyy", key="search_coffee_date")
                with col2:
                    search_kasir = st.text_input("🔍 Cari Kasir", key="search_coffee_kasir")
                
                # Apply filter
                if search_date:
                    df_sales = df_sales[df_sales['tanggal'].str.contains(search_date, case=False, na=False)]
                if search_kasir:
                    df_sales = df_sales[df_sales['created_by'].str.contains(search_kasir, case=False, na=False)]
                
                if not df_sales.empty:
                    st.success(f"📊 **{len(df_sales)} transaksi** ditemukan")
                    
                    # parse items for display
                    def items_str(js):
                        try:
                            arr = json.loads(js)
                            return '\n'.join([f"{i['qty']}x {i['name']} (Rp {i['price']:,.0f})" for i in arr])
                        except:
                            return js

                    df_sales['Items Detail'] = df_sales['items'].apply(items_str)
                    df_disp = df_sales[['tanggal', 'waktu', 'Items Detail', 'total', 'created_by']].copy()
                    df_disp.columns = ['📅 Tanggal', '⏰ Waktu', '☕️ Items', '💰 Total', '👤 Kasir']
                    df_disp['💰 Total'] = df_disp['💰 Total'].apply(lambda x: f"Rp {x:,.0f}")
                    
                    st.dataframe(df_disp, use_container_width=True, hide_index=True)
                    
                    # Statistik ringkas
                    st.markdown("---")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        total_penjualan = df_sales['total'].sum()
                        st.metric("💰 Total Penjualan", f"Rp {total_penjualan:,.0f}")
                    with col2:
                        st.metric("📊 Jumlah Transaksi", len(df_sales))
                    with col3:
                        avg_transaksi = total_penjualan / len(df_sales) if len(df_sales) > 0 else 0
                        st.metric("📈 Rata-rata", f"Rp {avg_transaksi:,.0f}")
                else:
                    st.warning("⚠️ Tidak ada transaksi yang sesuai dengan pencarian")
    
    with tab3:
        st.subheader('📜 History Transaksi Kasir')
        st.info("💡 Riwayat transaksi gabungan (cuci mobil + coffee) yang diproses di kasir")
        
        df_kasir = get_all_kasir_transactions()
        if df_kasir.empty:
            st.info('📭 Belum ada transaksi kasir tersimpan')
        else:
            # Filter pencarian
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                search_date_kasir = st.text_input("🔍 Cari Tanggal", placeholder="dd-mm-yyyy", key="search_kasir_date")
            with col2:
                search_nopol_kasir = st.text_input("🔍 Cari Nopol", key="search_kasir_nopol")
            
            # Apply filter
            if search_date_kasir:
                df_kasir = df_kasir[df_kasir['tanggal'].str.contains(search_date_kasir, case=False, na=False)]
            if search_nopol_kasir:
                df_kasir = df_kasir[df_kasir['nopol'].str.contains(search_nopol_kasir, case=False, na=False)]
            
            if not df_kasir.empty:
                st.success(f"📊 **{len(df_kasir)} transaksi** ditemukan")
                
                # Display detailed
                for idx, row in df_kasir.iterrows():
                    with st.expander(f"💳 {row['tanggal']} | {row['nopol']} - {row['nama_customer']} | Total: Rp {row['total_bayar']:,.0f}"):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.write("**Data Customer:**")
                            st.write(f"Nopol: {row['nopol']}")
                            st.write(f"Nama: {row['nama_customer']}")
                            st.write(f"Telp: {row.get('no_telp', '-')}")
                        with col2:
                            st.write("**Detail Transaksi:**")
                            st.write(f"Tanggal: {row['tanggal']}")
                            st.write(f"Waktu: {row['waktu']}")
                            st.write(f"Kasir: {row.get('created_by', '-')}")
                        with col3:
                            st.write("**Pembayaran:**")
                            st.write(f"Metode: {row.get('metode_bayar', '-')}")
                            st.write(f"Status: {row.get('status_bayar', '-')}")
                        
                        st.markdown("---")
                        
                        # Detail biaya
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            if row.get('paket_cuci') and row.get('harga_cuci', 0) > 0:
                                st.metric("🚗 Cuci Mobil", f"Rp {row['harga_cuci']:,.0f}")
                                st.caption(f"Paket: {row['paket_cuci']}")
                        with col2:
                            if row.get('coffee_items') and row.get('harga_coffee', 0) > 0:
                                st.metric("☕️ Coffee/Snack", f"Rp {row['harga_coffee']:,.0f}")
                                try:
                                    items = json.loads(row['coffee_items'])
                                    items_text = ", ".join([f"{i['qty']}x {i['name']}" for i in items])
                                    st.caption(items_text)
                                except:
                                    pass
                        with col3:
                            st.metric("💰 TOTAL", f"Rp {row['total_bayar']:,.0f}")
                        
                        if row.get('catatan'):
                            st.info(f"📝 Catatan: {row['catatan']}")
                
                # Statistik ringkas
                st.markdown("---")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    total_kasir = df_kasir['total_bayar'].sum()
                    st.metric("💰 Total Penjualan", f"Rp {total_kasir:,.0f}")
                with col2:
                    st.metric("📊 Jumlah Transaksi", len(df_kasir))
                with col3:
                    avg_kasir = total_kasir / len(df_kasir) if len(df_kasir) > 0 else 0
                    st.metric("📈 Rata-rata", f"Rp {avg_kasir:,.0f}")
                with col4:
                    total_cuci = df_kasir['harga_cuci'].sum()
                    total_coffee = df_kasir['harga_coffee'].sum()
                    st.metric("🚗 Total Cuci", f"Rp {total_cuci:,.0f}")
            else:
                st.warning("⚠️ Tidak ada transaksi yang sesuai dengan pencarian")
    
    with tab4:
        st.subheader("✏️ Edit / Hapus Transaksi Kasir")
        st.warning("⚠️ Hati-hati saat menghapus transaksi! Data yang dihapus tidak dapat dikembalikan.")
        
        df_kasir_all = get_all_kasir_transactions()
        
        if df_kasir_all.empty:
            st.info("📭 Belum ada transaksi kasir untuk diedit atau dihapus")
        else:
            # Select transaction
            trans_options = {}
            for _, row in df_kasir_all.iterrows():
                label = f"ID:{row['id']} | {row['tanggal']} {row['waktu']} | {row['nopol']} - {row['nama_customer']} | Total: Rp {row['total_bayar']:,.0f}"
                trans_options[label] = row
            
            selected_trans = st.selectbox("Pilih Transaksi Kasir", list(trans_options.keys()), key="select_kasir_trans_edit")
            
            if selected_trans:
                trans_data = trans_options[selected_trans]
                
                # Show transaction details
                with st.expander("📋 Detail Transaksi", expanded=True):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.write("**Customer:**")
                        st.write(f"Nopol: {trans_data['nopol']}")
                        st.write(f"Nama: {trans_data['nama_customer']}")
                        st.write(f"Telp: {trans_data.get('no_telp', '-')}")
                    with col2:
                        st.write("**Waktu:**")
                        st.write(f"Tanggal: {trans_data['tanggal']}")
                        st.write(f"Waktu: {trans_data['waktu']}")
                        st.write(f"Kasir: {trans_data.get('created_by', '-')}")
                    with col3:
                        st.write("**Pembayaran:**")
                        st.write(f"Total: Rp {trans_data['total_bayar']:,.0f}")
                        st.write(f"Metode: {trans_data.get('metode_bayar', '-')}")
                        st.write(f"Status: {trans_data.get('status_bayar', '-')}")
                
                st.markdown("---")
                
                # Delete button
                col1, col2, col3 = st.columns([2, 1, 2])
                with col2:
                    if st.button("🗑️ Hapus Transaksi", type="primary", use_container_width=True, key="delete_kasir_trans_btn"):
                        success, msg = delete_kasir_transaction(trans_data['id'])
                        if success:
                            add_audit("delete_kasir_trans", f"Hapus transaksi kasir ID:{trans_data['id']} - {trans_data['nopol']}")
                            st.success(f"✅ {msg}")
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")
                
                st.info("ℹ️ Untuk mengedit detail transaksi kasir, silakan hapus dan buat transaksi baru.")
    
    with tab5:
        st.subheader("⚙️ Kelola Menu Coffee Shop")
        
        # Check role
        if role not in ["Admin", "Supervisor"]:
            st.warning("⚠️ Hanya Admin dan Supervisor yang dapat mengelola menu coffee")
            return
        
        coffee_menu = get_coffee_menu()
        
        st.info("ℹ️ Tambah, edit, atau hapus menu coffee dan snack yang tersedia")
        
        # Tampilkan menu yang ada
        st.markdown("##### ☕️ Menu Saat Ini:")
        menu_updated = coffee_menu.copy()
        
        for idx, (nama, harga) in enumerate(coffee_menu.items()):
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                new_nama = st.text_input("Nama Item", value=nama, key=f"coffee_menu_nama_{idx}", label_visibility="collapsed")
            with col2:
                new_harga = st.number_input("Harga", value=int(harga), min_value=0, step=1000, key=f"coffee_menu_harga_{idx}", label_visibility="collapsed")
            with col3:
                if st.button("🗑️", key=f"del_coffee_menu_{idx}", help="Hapus item ini"):
                    del menu_updated[nama]
                    success, msg = update_setting("coffee_menu", menu_updated)
                    if success:
                        st.success(f"✅ {nama} berhasil dihapus")
                        add_audit("coffee_menu_delete", f"Hapus menu: {nama}")
                        st.rerun()
                    else:
                        st.error(msg)
            
            # Update jika berubah
            if new_nama != nama or new_harga != harga:
                if new_nama and new_harga > 0:
                    if nama in menu_updated:
                        del menu_updated[nama]
                    menu_updated[new_nama] = new_harga
        
        st.markdown("---")
        
        # Tambah menu baru
        st.markdown("##### ➕ Tambah Menu Baru:")
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            nama_baru = st.text_input("Nama Item Baru", key="new_coffee_menu_nama", placeholder="Contoh: Green Tea Latte")
        with col2:
            harga_baru = st.number_input("Harga", value=20000, min_value=0, step=1000, key="new_coffee_menu_harga")
        with col3:
            if st.button("➕ Tambah", key="add_coffee_menu"):
                if nama_baru and harga_baru > 0:
                    if nama_baru in menu_updated:
                        st.error(f"❌ Menu '{nama_baru}' sudah ada!")
                    else:
                        menu_updated[nama_baru] = harga_baru
                        success, msg = update_setting("coffee_menu", menu_updated)
                        if success:
                            st.success(f"✅ Menu '{nama_baru}' berhasil ditambahkan")
                            add_audit("coffee_menu_add", f"Tambah menu: {nama_baru} - Rp {harga_baru:,.0f}")
                            st.rerun()
                        else:
                            st.error(msg)
                else:
                    st.error("❌ Mohon isi nama dan harga menu")
        
        st.markdown("---")
        
        # Simpan semua perubahan
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("💾 Simpan Semua Perubahan Menu", type="primary", use_container_width=True, key="save_all_coffee_menu"):
                success, msg = update_setting("coffee_menu", menu_updated)
                if success:
                    st.success("✅ Semua perubahan menu coffee berhasil disimpan!")
                    add_audit("coffee_menu_update", "Update menu coffee")
                    st.rerun()
                else:
                    st.error(msg)

def customer_page(role):
    st.markdown("""
    <style>
    .cust-header {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 15px rgba(79, 172, 254, 0.3);
    }
    .cust-header h2 {
        margin: 0;
        font-size: 1.8rem;
        font-weight: 700;
    }
    .customer-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        margin-bottom: 1rem;
        transition: transform 0.2s;
    }
    .customer-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 4px 20px rgba(0,0,0,0.12);
    }
    .search-box {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 1rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="cust-header"><h2>👥 Manajemen Customer</h2></div>', unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["📋 Daftar Customer", "➕ Tambah Customer Baru", "✏️ Edit/Hapus Customer"])
    
    with tab1:
        df_cust = get_all_customers()
        
        if df_cust.empty:
            st.info("📭 Belum ada customer terdaftar. Silakan tambah customer baru di tab sebelah →")
        else:
            # Search dengan UI lebih baik
            col1, col2 = st.columns([3, 1])
            with col1:
                search = st.text_input("🔍 Cari customer", key="cust_search", 
                                      placeholder="Ketik nopol atau nama customer...",
                                      label_visibility="collapsed")
            with col2:
                st.metric("📊 Total Customer", len(df_cust))
            
            if search:
                mask = df_cust['nopol'].str.contains(search, case=False, na=False) | \
                       df_cust['nama_customer'].str.contains(search, case=False, na=False)
                df_display = df_cust[mask]
                if not df_display.empty:
                    st.success(f"✅ Ditemukan {len(df_display)} customer")
                else:
                    st.warning("⚠️ Tidak ada customer yang cocok dengan pencarian")
            else:
                df_display = df_cust
            
            if not df_display.empty:
                # Display dengan styling lebih baik
                df_show = df_display[['nopol', 'nama_customer', 'no_telp', 'created_at']].copy()
                df_show.columns = ['🔖 Nopol', '👤 Nama', '📞 Telepon', '📅 Terdaftar']
                
                st.dataframe(
                    df_show,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "🔖 Nopol": st.column_config.TextColumn(width="small"),
                        "👤 Nama": st.column_config.TextColumn(width="medium"),
                        "📞 Telepon": st.column_config.TextColumn(width="medium"),
                        "📅 Terdaftar": st.column_config.TextColumn(width="small")
                    }
                )
                
                # Download Excel
                col1, col2, col3 = st.columns([2, 1, 2])
                with col2:
                    # Create Excel file in memory
                    from io import BytesIO
                    buffer = BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df_show.to_excel(writer, index=False, sheet_name='Customer List')
                    buffer.seek(0)
                    
                    st.download_button(
                        "📥 Download Excel", 
                        data=buffer, 
                        file_name=f"customer_list_{datetime.now(WIB).strftime('%d%m%Y')}.xlsx", 
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
    
    with tab2:
        st.markdown('<div class="customer-card">', unsafe_allow_html=True)
        st.subheader("📝 Form Customer Baru")
        
        with st.form("add_customer_form"):
            st.info("💡 Isi data customer dengan lengkap. Field dengan tanda * wajib diisi")
            
            col1, col2 = st.columns(2)
            with col1:
                nopol = st.text_input("🔖 Nomor Polisi *", placeholder="Contoh: B1234XYZ", 
                                     help="Format: huruf+angka+huruf").upper()
                nama = st.text_input("👤 Nama Customer *", placeholder="Nama lengkap customer")
            with col2:
                telp = st.text_input("📞 No. Telepon", placeholder="08xxxxxxxxxx",
                                    help="Format: 08xxx atau +62xxx")
            
            submitted = st.form_submit_button("💾 Simpan Customer", type="primary", use_container_width=True)
            
            if submitted:
                if not nopol or not nama:
                    st.error("❌ Nopol dan Nama wajib diisi")
                else:
                    success, msg = save_customer(nopol, nama, telp)
                    if success:
                        add_audit("customer_baru", f"Nopol: {nopol}, Nama: {nama}")
                        st.success(f"✅ {msg}")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
    
    with tab3:
        st.markdown('<div class="customer-card">', unsafe_allow_html=True)
        st.subheader("✏️ Edit / Hapus Data Customer")
        
        df_cust = get_all_customers()
        
        if df_cust.empty:
            st.info("📭 Belum ada customer untuk diedit atau dihapus")
        else:
            # Select customer to edit
            cust_options = {f"{row['nopol']} - {row['nama_customer']}": row for _, row in df_cust.iterrows()}
            selected_cust = st.selectbox("Pilih Customer", list(cust_options.keys()), key="select_cust_edit")
            
            if selected_cust:
                cust_data = cust_options[selected_cust]
                
                col_edit, col_delete = st.columns([3, 1])
                
                with col_edit:
                    st.markdown("#### ✏️ Edit Customer")
                    with st.form("edit_customer_form"):
                        st.info(f"📝 Edit data untuk: **{cust_data['nopol']}**")
                        
                        edit_nama = st.text_input("Nama Customer *", value=cust_data['nama_customer'])
                        edit_telp = st.text_input("No. Telepon", value=cust_data['no_telp'] or "")
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            edit_jenis = st.text_input("Jenis Kendaraan", value=cust_data.get('jenis_kendaraan', '') or "")
                        with col2:
                            edit_merk = st.text_input("Merk Kendaraan", value=cust_data.get('merk_kendaraan', '') or "")
                        with col3:
                            ukuran_options = ["", "Kecil", "Sedang", "Besar", "Extra Besar"]
                            current_ukuran = cust_data.get('ukuran_mobil', '') or ""
                            ukuran_idx = ukuran_options.index(current_ukuran) if current_ukuran in ukuran_options else 0
                            edit_ukuran = st.selectbox("Ukuran Mobil", options=ukuran_options, index=ukuran_idx)
                        
                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            submit_edit = st.form_submit_button("💾 Update Customer", type="primary", use_container_width=True)
                        with col_btn2:
                            cancel = st.form_submit_button("❌ Batal", use_container_width=True)
                        
                        if submit_edit:
                            if not edit_nama:
                                st.error("❌ Nama customer wajib diisi")
                            else:
                                success, msg = update_customer(
                                    cust_data['nopol'], edit_nama, edit_telp,
                                    edit_jenis, edit_merk, edit_ukuran
                                )
                                if success:
                                    add_audit("update_customer", f"Update customer {cust_data['nopol']}")
                                    st.success(f"✅ {msg}")
                                    st.balloons()
                                    st.rerun()
                                else:
                                    st.error(f"❌ {msg}")
                
                with col_delete:
                    st.markdown("#### 🗑️ Hapus Customer")
                    st.warning("⚠️ Aksi ini tidak dapat dibatalkan!")
                    
                    if st.button("🗑️ Hapus Customer", type="primary", use_container_width=True, key="delete_cust_btn"):
                        success, msg = delete_customer(cust_data['nopol'])
                        if success:
                            add_audit("delete_customer", f"Hapus customer {cust_data['nopol']}")
                            st.success(f"✅ {msg}")
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")

def laporan_page(role):
    st.markdown("""
    <style>
    .laporan-header {
        background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 20px rgba(250, 112, 154, 0.4);
    }
    .laporan-header h1 {
        margin: 0;
        font-size: 2.2rem;
        font-weight: 800;
    }
    .filter-section {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        margin-bottom: 2rem;
    }
    .summary-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 20px rgba(102, 126, 234, 0.3);
    }
    .summary-box h3 {
        margin: 0 0 1.5rem 0;
        font-size: 1.5rem;
        font-weight: 800;
    }
    .summary-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 1rem;
    }
    .summary-item {
        background: rgba(255,255,255,0.15);
        padding: 1rem;
        border-radius: 12px;
        backdrop-filter: blur(10px);
    }
    .summary-label {
        font-size: 0.8rem;
        opacity: 0.9;
        margin-bottom: 0.5rem;
    }
    .summary-value {
        font-size: 1.5rem;
        font-weight: 900;
    }
    .business-section {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        margin-bottom: 1.5rem;
    }
    .section-title {
        color: #2d3436;
        font-size: 1.2rem;
        font-weight: 700;
        margin-bottom: 1rem;
        padding-bottom: 0.8rem;
        border-bottom: 3px solid #f0f0f0;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('''
    <div class="laporan-header">
        <h1>📊 Laporan Keuangan</h1>
        <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">Laporan Terintegrasi: Car Wash & Coffee Shop</p>
    </div>
    ''', unsafe_allow_html=True)
    
    # Load data
    df_trans = get_all_transactions()
    df_coffee = get_all_coffee_sales()
    
    if df_trans.empty and df_coffee.empty:
        st.info("📭 Belum ada data transaksi")
        return
    
    # Filter bulan dan tahun
    st.markdown('<div class="filter-section">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 2])
    
    # Parse tanggal untuk wash
    df_trans['tanggal_dt'] = pd.to_datetime(df_trans['tanggal'], format='%d-%m-%Y', errors='coerce')
    df_trans['bulan'] = df_trans['tanggal_dt'].dt.month
    df_trans['tahun'] = df_trans['tanggal_dt'].dt.year
    
    # Parse tanggal untuk coffee
    df_coffee['tanggal_dt'] = pd.to_datetime(df_coffee['tanggal'], format='%d-%m-%Y', errors='coerce')
    df_coffee['bulan'] = df_coffee['tanggal_dt'].dt.month
    df_coffee['tahun'] = df_coffee['tanggal_dt'].dt.year
    
    # Get available years
    years_trans = df_trans['tahun'].dropna().unique() if not df_trans.empty else []
    years_coffee = df_coffee['tahun'].dropna().unique() if not df_coffee.empty else []
    all_years = sorted(set(list(years_trans) + list(years_coffee)), reverse=True)
    
    with col1:
        selected_year = st.selectbox("📅 Tahun", options=all_years, key="lap_year")
    
    with col2:
        month_names = ['Semua', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
                      'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']
        selected_month = st.selectbox("📆 Bulan", options=range(len(month_names)), 
                                     format_func=lambda x: month_names[x], key="lap_month")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Filter data wash
    df_wash_filtered = df_trans[df_trans['tahun'] == selected_year].copy() if not df_trans.empty else pd.DataFrame()
    if selected_month != 0 and not df_wash_filtered.empty:
        df_wash_filtered = df_wash_filtered[df_wash_filtered['bulan'] == selected_month]
    
    # Filter data coffee
    df_coffee_filtered = df_coffee[df_coffee['tahun'] == selected_year].copy() if not df_coffee.empty else pd.DataFrame()
    if selected_month != 0 and not df_coffee_filtered.empty:
        df_coffee_filtered = df_coffee_filtered[df_coffee_filtered['bulan'] == selected_month]
    
    # Control Panel untuk Adjustment
    with st.expander("⚙️ Control Panel - Adjustment Laporan Keuangan", expanded=False):
        st.markdown("""
        <div style="background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); padding: 1rem; border-radius: 10px; margin-bottom: 1rem;">
            <h4 style="margin: 0 0 0.5rem 0; color: #2d3436;">🎛️ Adjustment Pendapatan</h4>
            <p style="margin: 0; font-size: 0.85rem; color: #636e72;">Gunakan slider untuk menyesuaikan persentase pendapatan yang ditampilkan dalam laporan</p>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**🚗 Adjustment Car Wash**")
            wash_percentage = st.slider(
                "Persentase Car Wash",
                min_value=0,
                max_value=200,
                value=100,
                step=5,
                key="wash_adj",
                help="100% = Pendapatan aktual, 50% = Setengah dari aktual, 150% = 1.5x dari aktual",
                label_visibility="collapsed"
            )
            st.info(f"📊 Adjustment: **{wash_percentage}%** dari aktual")
        
        with col2:
            st.markdown("**☕ Adjustment Coffee Shop**")
            coffee_percentage = st.slider(
                "Persentase Coffee Shop",
                min_value=0,
                max_value=200,
                value=100,
                step=5,
                key="coffee_adj",
                help="100% = Pendapatan aktual, 50% = Setengah dari aktual, 150% = 1.5x dari aktual",
                label_visibility="collapsed"
            )
            st.info(f"📊 Adjustment: **{coffee_percentage}%** dari aktual")
        
        with col3:
            st.markdown("**🎯 Quick Presets**")
            if st.button("🔄 Reset ke 100%", use_container_width=True):
                st.session_state.wash_adj = 100
                st.session_state.coffee_adj = 100
                st.rerun()
            if st.button("📉 Konservatif (75%)", use_container_width=True):
                st.session_state.wash_adj = 75
                st.session_state.coffee_adj = 75
                st.rerun()
            if st.button("📈 Optimis (125%)", use_container_width=True):
                st.session_state.wash_adj = 125
                st.session_state.coffee_adj = 125
                st.rerun()
        
        # Show adjustment info
        if wash_percentage != 100 or coffee_percentage != 100:
            st.markdown("---")
            st.warning(f"⚠️ **Mode Adjustment Aktif** - Pendapatan ditampilkan dengan adjustment: Car Wash {wash_percentage}%, Coffee {coffee_percentage}%")
    
    # Apply adjustment ke data
    adjustment_wash = wash_percentage / 100 if 'wash_percentage' in locals() else 1.0
    adjustment_coffee = coffee_percentage / 100 if 'coffee_percentage' in locals() else 1.0
    
    # Hitung statistik dengan adjustment
    total_pendapatan_wash_actual = df_wash_filtered['harga'].sum() if not df_wash_filtered.empty else 0
    total_pendapatan_wash = total_pendapatan_wash_actual * adjustment_wash
    total_transaksi_wash = len(df_wash_filtered)
    
    total_pendapatan_coffee_actual = df_coffee_filtered['total'].sum() if not df_coffee_filtered.empty else 0
    total_pendapatan_coffee = total_pendapatan_coffee_actual * adjustment_coffee
    total_transaksi_coffee = len(df_coffee_filtered)
    
    total_pendapatan_gabungan = total_pendapatan_wash + total_pendapatan_coffee
    total_transaksi_gabungan = total_transaksi_wash + total_transaksi_coffee
    
    avg_wash = total_pendapatan_wash / total_transaksi_wash if total_transaksi_wash > 0 else 0
    avg_coffee = total_pendapatan_coffee / total_transaksi_coffee if total_transaksi_coffee > 0 else 0
    
    # Summary Box
    adjustment_note = ""
    if adjustment_wash != 1.0 or adjustment_coffee != 1.0:
        adjustment_note = f" <span style='font-size: 0.85rem; opacity: 0.9;'>(Adjusted: Wash {int(adjustment_wash*100)}%, Coffee {int(adjustment_coffee*100)}%)</span>"
    
    st.markdown(f'''
    <div class="summary-box">
        <h3>💼 Ringkasan Keuangan Periode {month_names[selected_month]} {selected_year}{adjustment_note}</h3>
        <div class="summary-grid">
            <div class="summary-item">
                <div class="summary-label">💰 Total Pendapatan</div>
                <div class="summary-value">Rp {total_pendapatan_gabungan:,.0f}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">🚗 Pendapatan Wash</div>
                <div class="summary-value">Rp {total_pendapatan_wash:,.0f}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">☕ Pendapatan Coffee</div>
                <div class="summary-value">Rp {total_pendapatan_coffee:,.0f}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">📊 Total Transaksi</div>
                <div class="summary-value">{total_transaksi_gabungan}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">📈 Avg. Wash</div>
                <div class="summary-value">Rp {avg_wash:,.0f}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">📈 Avg. Coffee</div>
                <div class="summary-value">Rp {avg_coffee:,.0f}</div>
            </div>
        </div>
    </div>
    ''', unsafe_allow_html=True)
    
    # Tabs untuk detail laporan
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🚗 Detail Cuci Mobil", "☕ Detail Coffee Shop", "📊 Perbandingan", "📈 Trend Analysis", "💼 Laporan Transaksi"])
    
    with tab1:
        st.markdown('<div class="business-section">', unsafe_allow_html=True)
        st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 0.8rem 1rem; border-radius: 8px; margin-bottom: 1.5rem;">
            <h3 style="color: white; margin: 0; font-size: 1.1rem; font-weight: 600;">
                🚗 Detail Cuci Mobil
            </h3>
        </div>
        """, unsafe_allow_html=True)
        
        if not df_wash_filtered.empty:
            # Apply adjustment ke data wash
            df_wash_adjusted = df_wash_filtered.copy()
            df_wash_adjusted['harga'] = df_wash_adjusted['harga'] * adjustment_wash
            
            # Tabel per paket
            st.markdown("**📦 Pendapatan per Paket Cuci**")
            paket_summary = df_wash_adjusted.groupby('paket_cuci').agg(
                Jumlah=('id', 'count'),
                Total_Pendapatan=('harga', 'sum'),
                Rata_rata=('harga', 'mean'),
                Min=('harga', 'min'),
                Max=('harga', 'max')
            ).reset_index()
            paket_summary.columns = ['Paket Cuci', 'Jumlah', 'Total Pendapatan', 'Rata-rata', 'Min', 'Max']
            paket_summary = paket_summary.sort_values('Total Pendapatan', ascending=False)
            
            # Add percentage
            paket_summary['% Kontribusi'] = (paket_summary['Total Pendapatan'] / paket_summary['Total Pendapatan'].sum() * 100).round(1)
            
            # Format tampilan
            df_display = paket_summary.copy()
            df_display['Total Pendapatan'] = df_display['Total Pendapatan'].apply(lambda x: f"Rp {x:,.0f}")
            df_display['Rata-rata'] = df_display['Rata-rata'].apply(lambda x: f"Rp {x:,.0f}")
            df_display['Min'] = df_display['Min'].apply(lambda x: f"Rp {x:,.0f}")
            df_display['Max'] = df_display['Max'].apply(lambda x: f"Rp {x:,.0f}")
            df_display['% Kontribusi'] = df_display['% Kontribusi'].apply(lambda x: f"{x}%")
            
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
            st.divider()
            # Grafik
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**📊 Volume Transaksi**")
                paket_count = df_wash_filtered.groupby('paket_cuci').size().reset_index(name='count')
                chart = alt.Chart(paket_count).mark_bar(cornerRadiusEnd=8).encode(
                    x=alt.X('count:Q', title='Jumlah'),
                    y=alt.Y('paket_cuci:N', sort='-x', title=''),
                    color=alt.Color('count:Q', scale=alt.Scale(scheme='purples'), legend=None),
                    tooltip=['paket_cuci:N', 'count:Q']
                ).properties(height=280)
                st.altair_chart(chart, use_container_width=True)
            
            with col2:
                st.markdown("**💰 Distribusi Pendapatan**")
                pie = alt.Chart(paket_summary).mark_arc(innerRadius=50).encode(
                    theta='Total Pendapatan:Q',
                    color=alt.Color('Paket Cuci:N', scale=alt.Scale(scheme='purples'), legend=alt.Legend(orient='bottom')),
                    tooltip=['Paket Cuci:N', alt.Tooltip('Total Pendapatan:Q', format=',.0f')]
                ).properties(height=280)
                st.altair_chart(pie, use_container_width=True)
            
            st.divider()
            # Status transaksi
            st.markdown("**✅ Status Transaksi**")
            status_summary = df_wash_filtered.groupby('status').agg(
                Jumlah=('id', 'count'),
                Total=('harga', 'sum')
            ).reset_index()
            col1, col2, col3 = st.columns(3)
            for idx, row in status_summary.iterrows():
                with [col1, col2, col3][idx % 3]:
                    st.metric(f"{row['status']}", f"{row['Jumlah']} transaksi", f"Rp {row['Total']:,.0f}")
        else:
            st.info("📭 Tidak ada data cuci mobil untuk periode ini")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tab2:
        st.markdown('<div class="business-section">', unsafe_allow_html=True)
        st.markdown("""
        <div style="background: linear-gradient(135deg, #f6d365 0%, #fda085 100%); 
                    padding: 0.8rem 1rem; border-radius: 8px; margin-bottom: 1.5rem;">
            <h3 style="color: white; margin: 0; font-size: 1.1rem; font-weight: 600;">
                ☕ Detail Coffee Shop
            </h3>
        </div>
        """, unsafe_allow_html=True)
        
        if not df_coffee_filtered.empty:
            # Statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("💰 Total Penjualan", f"Rp {total_pendapatan_coffee:,.0f}",
                         delta=f"{int(adjustment_coffee*100)}% adjustment" if adjustment_coffee != 1.0 else None)
            with col2:
                st.metric("🛒 Total Transaksi", total_transaksi_coffee)
            with col3:
                st.metric("📊 Rata-rata/Transaksi", f"Rp {avg_coffee:,.0f}")
            
            # Analisis item terjual
            st.markdown("**☕ Item Terlaris**")
            all_items = []
            for items_str in df_coffee_filtered['items']:
                try:
                    items = json.loads(items_str)
                    for item in items:
                        all_items.append(item)
                except:
                    pass
            
            if all_items:
                items_df = pd.DataFrame(all_items)
                
                # Deteksi nama kolom dengan helper function
                def get_column(df, possible_names):
                    for name in possible_names:
                        if name in df.columns:
                            return name
                    return None
                
                name_col = get_column(items_df, ['nama', 'name', 'item'])
                qty_col = get_column(items_df, ['qty', 'quantity', 'jumlah'])
                total_col = get_column(items_df, ['subtotal', 'total', 'harga'])
                
                if not name_col:
                    st.warning("⚠️ Struktur data items tidak sesuai. Kolom yang tersedia: " + ", ".join(items_df.columns.tolist()))
                elif not qty_col or not total_col:
                    st.warning("⚠️ Data items tidak memiliki kolom qty atau subtotal yang diperlukan")
                else:
                    # Apply adjustment to items
                    items_df[total_col] = items_df[total_col] * adjustment_coffee
                    
                    items_summary = items_df.groupby(name_col).agg(
                        Jumlah=(qty_col, 'sum'),
                        Total_Pendapatan=(total_col, 'sum')
                    ).reset_index()
                    items_summary.columns = ['Item', 'Qty Terjual', 'Total Pendapatan']
                    items_summary = items_summary.sort_values('Total Pendapatan', ascending=False)
                    
                    # Add percentage
                    items_summary['% Kontribusi'] = (items_summary['Total Pendapatan'] / items_summary['Total Pendapatan'].sum() * 100).round(1)
                    
                    # Format
                    df_display = items_summary.copy()
                    df_display['Total Pendapatan'] = df_display['Total Pendapatan'].apply(lambda x: f"Rp {x:,.0f}")
                    df_display['% Kontribusi'] = df_display['% Kontribusi'].apply(lambda x: f"{x}%")
                    
                    st.dataframe(df_display, use_container_width=True, hide_index=True)
                    
                    st.divider()
                    # Grafik
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**📊 Qty Terjual (Top 10)**")
                        top_items = items_summary.head(10)
                        chart = alt.Chart(top_items).mark_bar(cornerRadiusEnd=8).encode(
                            x=alt.X('Qty Terjual:Q', title='Quantity'),
                            y=alt.Y('Item:N', sort='-x', title=''),
                            color=alt.Color('Qty Terjual:Q', scale=alt.Scale(scheme='oranges'), legend=None),
                            tooltip=['Item:N', 'Qty Terjual:Q']
                        ).properties(height=320)
                        st.altair_chart(chart, use_container_width=True)
                    
                    with col2:
                        st.markdown("**💰 Pendapatan per Item**")
                        pie = alt.Chart(top_items).mark_arc(innerRadius=50).encode(
                            theta='Total Pendapatan:Q',
                            color=alt.Color('Item:N', scale=alt.Scale(scheme='oranges'), legend=alt.Legend(orient='bottom')),
                            tooltip=['Item:N', alt.Tooltip('Total Pendapatan:Q', format=',.0f')]
                        ).properties(height=320)
                        st.altair_chart(pie, use_container_width=True)
            else:
                st.info("📭 Tidak ada data item coffee untuk periode ini")
        else:
            st.info("📭 Tidak ada data coffee shop untuk periode ini")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tab3:
        st.markdown('<div class="business-section">', unsafe_allow_html=True)
        st.markdown("""
        <div style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); 
                    padding: 0.8rem 1rem; border-radius: 8px; margin-bottom: 1.5rem;">
            <h3 style="color: white; margin: 0; font-size: 1.1rem; font-weight: 600;">
                📊 Perbandingan Bisnis
            </h3>
        </div>
        """, unsafe_allow_html=True)
        
        # Show adjustment info if active
        if adjustment_wash != 1.0 or adjustment_coffee != 1.0:
            st.info(f"ℹ️ Adjustment: Wash **{int(adjustment_wash*100)}%**, Coffee **{int(adjustment_coffee*100)}%**")
        
        # Comparison metrics
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**🚗 Car Wash**")
            st.metric("💰 Total Pendapatan", f"Rp {total_pendapatan_wash:,.0f}")
            if adjustment_wash != 1.0:
                st.caption(f"Aktual: Rp {total_pendapatan_wash_actual:,.0f}")
            st.metric("🛒 Jumlah Transaksi", total_transaksi_wash)
            st.metric("📊 Rata-rata/Transaksi", f"Rp {avg_wash:,.0f}")
            wash_pct = (total_pendapatan_wash / total_pendapatan_gabungan * 100) if total_pendapatan_gabungan > 0 else 0
            st.metric("📈 Kontribusi", f"{wash_pct:.1f}%")
        
        with col2:
            st.markdown("**☕ Coffee Shop**")
            st.metric("💰 Total Pendapatan", f"Rp {total_pendapatan_coffee:,.0f}")
            if adjustment_coffee != 1.0:
                st.caption(f"Aktual: Rp {total_pendapatan_coffee_actual:,.0f}")
            st.metric("🛒 Jumlah Transaksi", total_transaksi_coffee)
            st.metric("📊 Rata-rata/Transaksi", f"Rp {avg_coffee:,.0f}")
            coffee_pct = (total_pendapatan_coffee / total_pendapatan_gabungan * 100) if total_pendapatan_gabungan > 0 else 0
            st.metric("📈 Kontribusi", f"{coffee_pct:.1f}%")
        
        st.divider()
        # Comparison charts
        st.markdown("**📊 Visualisasi Perbandingan**")
        
        comparison_data = pd.DataFrame({
            'Bisnis': ['Car Wash', 'Coffee Shop'],
            'Pendapatan': [total_pendapatan_wash, total_pendapatan_coffee],
            'Transaksi': [total_transaksi_wash, total_transaksi_coffee]
        })
        
        col1, col2 = st.columns(2)
        with col1:
            chart = alt.Chart(comparison_data).mark_bar(cornerRadiusEnd=10, size=60).encode(
                x=alt.X('Bisnis:N', title='', axis=alt.Axis(labelFontSize=12)),
                y=alt.Y('Pendapatan:Q', title='Pendapatan (Rp)'),
                color=alt.Color('Bisnis:N', scale=alt.Scale(domain=['Car Wash', 'Coffee Shop'], 
                                                            range=['#667eea', '#f6d365']), legend=None),
                tooltip=['Bisnis:N', alt.Tooltip('Pendapatan:Q', format=',.0f', title='Rp')]
            ).properties(height=320)
            st.altair_chart(chart, use_container_width=True)
        
        with col2:
            chart = alt.Chart(comparison_data).mark_bar(cornerRadiusEnd=10, size=60).encode(
                x=alt.X('Bisnis:N', title='', axis=alt.Axis(labelFontSize=12)),
                y=alt.Y('Transaksi:Q', title='Jumlah Transaksi'),
                color=alt.Color('Bisnis:N', scale=alt.Scale(domain=['Car Wash', 'Coffee Shop'], 
                                                            range=['#667eea', '#f6d365']), legend=None),
                tooltip=['Bisnis:N', 'Transaksi:Q']
            ).properties(height=320)
            st.altair_chart(chart, use_container_width=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tab4:
        st.markdown('<div class="business-section">', unsafe_allow_html=True)
        st.markdown("""
        <div style="background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); 
                    padding: 0.8rem 1rem; border-radius: 8px; margin-bottom: 1.5rem;">
            <h3 style="color: white; margin: 0; font-size: 1.1rem; font-weight: 600;">
                📈 Trend Analysis
            </h3>
        </div>
        """, unsafe_allow_html=True)
        
        if selected_month != 0:
            # Tren harian
            st.markdown("**📅 Tren Pendapatan Harian**")
            
            # Prepare daily data for wash dengan adjustment
            df_wash_daily = df_wash_filtered.copy() if not df_wash_filtered.empty else pd.DataFrame()
            if not df_wash_daily.empty:
                df_wash_daily['harga'] = df_wash_daily['harga'] * adjustment_wash
            
            daily_wash = df_wash_daily.groupby('tanggal')['harga'].sum().reset_index() if not df_wash_daily.empty else pd.DataFrame()
            if not daily_wash.empty:
                daily_wash.columns = ['tanggal', 'wash']
                daily_wash['tanggal_dt'] = pd.to_datetime(daily_wash['tanggal'], format='%d-%m-%Y')
            
            # Prepare daily data for coffee dengan adjustment
            df_coffee_daily = df_coffee_filtered.copy() if not df_coffee_filtered.empty else pd.DataFrame()
            if not df_coffee_daily.empty:
                df_coffee_daily['total'] = df_coffee_daily['total'] * adjustment_coffee
            
            daily_coffee = df_coffee_daily.groupby('tanggal')['total'].sum().reset_index() if not df_coffee_daily.empty else pd.DataFrame()
            if not daily_coffee.empty:
                daily_coffee.columns = ['tanggal', 'coffee']
                daily_coffee['tanggal_dt'] = pd.to_datetime(daily_coffee['tanggal'], format='%d-%m-%Y')
            
            # Merge data
            if not daily_wash.empty or not daily_coffee.empty:
                if not daily_wash.empty and not daily_coffee.empty:
                    daily_combined = pd.merge(daily_wash, daily_coffee, on='tanggal_dt', how='outer', suffixes=('', '_coffee'))
                    daily_combined['wash'] = daily_combined['wash'].fillna(0)
                    daily_combined['coffee'] = daily_combined['coffee'].fillna(0)
                    daily_combined['total'] = daily_combined['wash'] + daily_combined['coffee']
                elif not daily_wash.empty:
                    daily_combined = daily_wash.copy()
                    daily_combined['coffee'] = 0
                    daily_combined['total'] = daily_combined['wash']
                else:
                    daily_combined = daily_coffee.copy()
                    daily_combined['wash'] = 0
                    daily_combined['total'] = daily_combined['coffee']
                
                daily_combined = daily_combined.sort_values('tanggal_dt')
                
                # Create line chart
                daily_melted = daily_combined.melt(id_vars=['tanggal_dt'], 
                                                   value_vars=['wash', 'coffee', 'total'],
                                                   var_name='Bisnis', value_name='Pendapatan')
                daily_melted['Bisnis'] = daily_melted['Bisnis'].map({
                    'wash': 'Car Wash',
                    'coffee': 'Coffee Shop',
                    'total': 'Total'
                })
                
                chart = alt.Chart(daily_melted).mark_line(point=alt.OverlayMarkDef(size=60, filled=True), strokeWidth=3).encode(
                    x=alt.X('tanggal_dt:T', title='Tanggal', axis=alt.Axis(format='%d-%m', labelAngle=-45)),
                    y=alt.Y('Pendapatan:Q', title='Pendapatan (Rp)'),
                    color=alt.Color('Bisnis:N', scale=alt.Scale(domain=['Car Wash', 'Coffee Shop', 'Total'],
                                                                range=['#667eea', '#f6d365', '#43e97b']),
                                  legend=alt.Legend(orient='top', title=None)),
                    tooltip=[
                        alt.Tooltip('tanggal_dt:T', title='Tanggal', format='%d-%m-%Y'),
                        'Bisnis:N',
                        alt.Tooltip('Pendapatan:Q', format=',.0f', title='Rp')
                    ]
                ).properties(height=400)
                
                st.altair_chart(chart, use_container_width=True)
                
                st.divider()
                # Summary table
                st.markdown("**📋 Detail Tabel Harian**")
                daily_display = daily_combined[['tanggal_dt', 'wash', 'coffee', 'total']].copy()
                daily_display.columns = ['Tanggal', 'Car Wash', 'Coffee Shop', 'Total']
                daily_display['Tanggal'] = daily_display['Tanggal'].dt.strftime('%d-%m-%Y')
                daily_display['Car Wash'] = daily_display['Car Wash'].apply(lambda x: f"Rp {x:,.0f}")
                daily_display['Coffee Shop'] = daily_display['Coffee Shop'].apply(lambda x: f"Rp {x:,.0f}")
                daily_display['Total'] = daily_display['Total'].apply(lambda x: f"Rp {x:,.0f}")
                
                st.dataframe(daily_display, use_container_width=True, hide_index=True)
        else:
            st.info("ℹ️ Pilih bulan spesifik untuk melihat trend analysis harian")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tab5:
        st.markdown('<div class="business-section">', unsafe_allow_html=True)
        st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 0.8rem 1rem; border-radius: 8px; margin-bottom: 1.5rem;">
            <h3 style="color: white; margin: 0; font-size: 1.1rem; font-weight: 600;">
                💼 Laporan Transaksi Lengkap
            </h3>
        </div>
        """, unsafe_allow_html=True)
        
        # Filter data kasir_transactions berdasarkan periode yang dipilih
        df_kasir = get_all_kasir_transactions()
        
        if not df_kasir.empty:
            # Apply date filter
            df_kasir['tanggal_dt'] = pd.to_datetime(df_kasir['tanggal'], format='%d-%m-%Y', errors='coerce')
            df_kasir['bulan'] = df_kasir['tanggal_dt'].dt.month
            df_kasir['tahun'] = df_kasir['tanggal_dt'].dt.year
            
            df_kasir_filtered = df_kasir[df_kasir['tahun'] == selected_year].copy()
            if selected_month != 0:
                df_kasir_filtered = df_kasir_filtered[df_kasir_filtered['bulan'] == selected_month]
        else:
            df_kasir_filtered = pd.DataFrame()
        
        if not df_kasir_filtered.empty or not df_coffee_filtered.empty:
            # Statistik Gabungan - Summary Cards
            col1, col2, col3 = st.columns(3)
            
            # Hitung total dari kasir_transactions
            total_kasir_wash = df_kasir_filtered['harga_cuci'].sum() if not df_kasir_filtered.empty else 0
            total_kasir_coffee = df_kasir_filtered['harga_coffee'].sum() if not df_kasir_filtered.empty else 0
            
            # Hitung total dari coffee_sales (standalone)
            total_coffee_standalone = df_coffee_filtered['total'].sum() if not df_coffee_filtered.empty else 0
            
            # Grand total
            grand_total_wash = total_kasir_wash
            grand_total_coffee = total_kasir_coffee + total_coffee_standalone
            grand_total_all = grand_total_wash + grand_total_coffee
            
            # Count transactions
            count_wash_only = len(df_kasir_filtered[(df_kasir_filtered['harga_cuci'] > 0) & (df_kasir_filtered['harga_coffee'] == 0)])
            count_coffee_only = len(df_coffee_filtered)
            count_combo = len(df_kasir_filtered[(df_kasir_filtered['harga_cuci'] > 0) & (df_kasir_filtered['harga_coffee'] > 0)])
            
            with col1:
                st.markdown("""
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                            padding: 1rem; border-radius: 10px; text-align: center;">
                    <h4 style="color: white; margin: 0;">🚗 Cuci Mobil</h4>
                    <h2 style="color: white; margin: 0.5rem 0;">Rp {:,.0f}</h2>
                    <p style="color: rgba(255,255,255,0.9); margin: 0; font-size: 0.9rem;">{} transaksi</p>
                </div>
                """.format(grand_total_wash, count_wash_only + count_combo), unsafe_allow_html=True)
            
            with col2:
                st.markdown("""
                <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); 
                            padding: 1rem; border-radius: 10px; text-align: center;">
                    <h4 style="color: white; margin: 0;">☕ Coffee Shop</h4>
                    <h2 style="color: white; margin: 0.5rem 0;">Rp {:,.0f}</h2>
                    <p style="color: rgba(255,255,255,0.9); margin: 0; font-size: 0.9rem;">{} transaksi</p>
                </div>
                """.format(grand_total_coffee, count_coffee_only + count_combo), unsafe_allow_html=True)
            
            with col3:
                st.markdown("""
                <div style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); 
                            padding: 1rem; border-radius: 10px; text-align: center;">
                    <h4 style="color: white; margin: 0;">💰 Total Pendapatan</h4>
                    <h2 style="color: white; margin: 0.5rem 0;">Rp {:,.0f}</h2>
                    <p style="color: rgba(255,255,255,0.9); margin: 0; font-size: 0.9rem;">{} transaksi total</p>
                </div>
                """.format(grand_total_all, count_wash_only + count_coffee_only + count_combo), unsafe_allow_html=True)
            
            st.divider()
            
            # Tab untuk memisahkan jenis laporan
            tab_laporan = st.tabs(["🚗 Cuci Mobil", "☕ Coffee Shop", "🔄 Cuci + Coffee", "📊 Semua Transaksi"])
            
            # ========== TAB 1: CUCI MOBIL SAJA ==========
            with tab_laporan[0]:
                st.markdown("""
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                            padding: 0.7rem 1rem; border-radius: 8px; margin-bottom: 1rem;">
                    <h4 style="color: white; margin: 0; font-size: 1rem;">🚗 Transaksi Cuci Mobil Saja</h4>
                </div>
                """, unsafe_allow_html=True)
                
                # Filter hanya transaksi cuci mobil tanpa coffee
                if not df_kasir_filtered.empty:
                    df_wash_only = df_kasir_filtered[(df_kasir_filtered['harga_cuci'] > 0) & (df_kasir_filtered['harga_coffee'] == 0)].copy()
                    
                    if not df_wash_only.empty:
                        st.info(f"📋 Menampilkan {len(df_wash_only)} transaksi cuci mobil (tanpa pembelian coffee)")
                        
                        # Search filters
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            search_wash_nopol = st.text_input("🔍 Cari Nopol", key="wash_only_nopol")
                        with col2:
                            search_wash_customer = st.text_input("🔍 Cari Customer", key="wash_only_customer")
                        with col3:
                            search_wash_paket = st.selectbox("🔍 Filter Paket", 
                                                            ["Semua"] + sorted(df_wash_only['paket_cuci'].unique().tolist()),
                                                            key="wash_only_paket")
                        
                        # Apply filters
                        df_wash_display = df_wash_only.copy()
                        if search_wash_nopol:
                            df_wash_display = df_wash_display[df_wash_display['nopol'].str.contains(search_wash_nopol, case=False, na=False)]
                        if search_wash_customer:
                            df_wash_display = df_wash_display[df_wash_display['nama_customer'].str.contains(search_wash_customer, case=False, na=False)]
                        if search_wash_paket != "Semua":
                            df_wash_display = df_wash_display[df_wash_display['paket_cuci'] == search_wash_paket]
                        
                        if not df_wash_display.empty:
                            # Summary
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("💰 Total Pendapatan", f"Rp {df_wash_display['harga_cuci'].sum():,.0f}")
                            with col2:
                                st.metric("📊 Jumlah Transaksi", f"{len(df_wash_display)}")
                            with col3:
                                avg_price = df_wash_display['harga_cuci'].mean()
                                st.metric("📈 Rata-rata", f"Rp {avg_price:,.0f}")
                            
                            # Display table
                            df_show = df_wash_display[['tanggal', 'waktu', 'nopol', 'nama_customer', 
                                                       'paket_cuci', 'harga_cuci', 'metode_bayar', 'created_by']].copy()
                            df_show['harga_cuci'] = df_show['harga_cuci'].apply(lambda x: f"Rp {x:,.0f}")
                            df_show.columns = ['📅 Tanggal', '⏰ Waktu', '🚗 Nopol', '👤 Customer', 
                                              '📦 Paket', '💰 Harga', '💳 Pembayaran', '👨‍💼 Kasir']
                            
                            st.dataframe(df_show, use_container_width=True, hide_index=True, height=400)
                            
                            # Download
                            from io import BytesIO
                            buffer = BytesIO()
                            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                                df_show.to_excel(writer, index=False, sheet_name='Cuci Mobil')
                            buffer.seek(0)
                            
                            st.download_button(
                                label="📥 Download Data Cuci Mobil (Excel)",
                                data=buffer,
                                file_name=f"cuci_mobil_{month_names[selected_month]}_{selected_year}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            )
                        else:
                            st.warning("🔍 Tidak ada data yang sesuai dengan filter")
                    else:
                        st.info("📭 Tidak ada transaksi cuci mobil saja pada periode ini")
                else:
                    st.info("📭 Tidak ada data transaksi")
            
            # ========== TAB 2: COFFEE SHOP SAJA ==========
            with tab_laporan[1]:
                st.markdown("""
                <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); 
                            padding: 0.7rem 1rem; border-radius: 8px; margin-bottom: 1rem;">
                    <h4 style="color: white; margin: 0; font-size: 1rem;">☕ Transaksi Coffee Shop Saja</h4>
                </div>
                """, unsafe_allow_html=True)
                
                # Gabungkan coffee standalone dengan coffee dari kasir yang tidak ada cuci
                coffee_data = []
                
                # Add standalone coffee
                if not df_coffee_filtered.empty:
                    for idx, row in df_coffee_filtered.iterrows():
                        coffee_data.append({
                            'Tanggal': row['tanggal'],
                            'Waktu': row['waktu'],
                            'Customer': row.get('nama_customer', 'Walk-in'),
                            'Items': row['items'],
                            'Total': row['total'],
                            'Kasir': row.get('created_by', '-'),
                            'Sumber': 'Coffee Shop'
                        })
                
                # Add coffee-only from kasir (no wash)
                if not df_kasir_filtered.empty:
                    df_coffee_from_kasir = df_kasir_filtered[(df_kasir_filtered['harga_cuci'] == 0) & (df_kasir_filtered['harga_coffee'] > 0)].copy()
                    for idx, row in df_coffee_from_kasir.iterrows():
                        coffee_data.append({
                            'Tanggal': row['tanggal'],
                            'Waktu': row['waktu'],
                            'Customer': row['nama_customer'],
                            'Items': 'Coffee Items',
                            'Total': row['harga_coffee'],
                            'Kasir': row.get('created_by', '-'),
                            'Sumber': 'Kasir'
                        })
                
                if coffee_data:
                    df_coffee_only = pd.DataFrame(coffee_data)
                    
                    st.info(f"📋 Menampilkan {len(df_coffee_only)} transaksi coffee shop (tanpa cuci mobil)")
                    
                    # Search filter
                    col1, col2 = st.columns(2)
                    with col1:
                        search_coffee_cust = st.text_input("🔍 Cari Customer", key="coffee_only_customer")
                    with col2:
                        search_coffee_kasir = st.text_input("🔍 Cari Kasir", key="coffee_only_kasir")
                    
                    # Apply filters
                    df_coffee_display = df_coffee_only.copy()
                    if search_coffee_cust:
                        df_coffee_display = df_coffee_display[df_coffee_display['Customer'].str.contains(search_coffee_cust, case=False, na=False)]
                    if search_coffee_kasir:
                        df_coffee_display = df_coffee_display[df_coffee_display['Kasir'].str.contains(search_coffee_kasir, case=False, na=False)]
                    
                    if not df_coffee_display.empty:
                        # Summary
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("💰 Total Pendapatan", f"Rp {df_coffee_display['Total'].sum():,.0f}")
                        with col2:
                            st.metric("📊 Jumlah Transaksi", f"{len(df_coffee_display)}")
                        with col3:
                            avg_price = df_coffee_display['Total'].mean()
                            st.metric("📈 Rata-rata", f"Rp {avg_price:,.0f}")
                        
                        # Parse items for display
                        def parse_items(items_str):
                            try:
                                items = json.loads(items_str)
                                return ', '.join([f"{i['qty']}x {i['name']}" for i in items])
                            except:
                                return str(items_str)
                        
                        # Display table
                        df_show = df_coffee_display.copy()
                        df_show['Items'] = df_show['Items'].apply(parse_items)
                        df_show['Total'] = df_show['Total'].apply(lambda x: f"Rp {x:,.0f}")
                        df_show.columns = ['📅 Tanggal', '⏰ Waktu', '👤 Customer', '☕ Items', 
                                          '💰 Total', '👨‍💼 Kasir', '📍 Sumber']
                        
                        st.dataframe(df_show, use_container_width=True, hide_index=True, height=400)
                        
                        # Download
                        from io import BytesIO
                        buffer = BytesIO()
                        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                            df_show.to_excel(writer, index=False, sheet_name='Coffee Shop')
                        buffer.seek(0)
                        
                        st.download_button(
                            label="📥 Download Data Coffee Shop (Excel)",
                            data=buffer,
                            file_name=f"coffee_shop_{month_names[selected_month]}_{selected_year}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    else:
                        st.warning("🔍 Tidak ada data yang sesuai dengan filter")
                else:
                    st.info("📭 Tidak ada transaksi coffee shop saja pada periode ini")
            
            # ========== TAB 3: CUCI + COFFEE (COMBO) ==========
            with tab_laporan[2]:
                st.markdown("""
                <div style="background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); 
                            padding: 0.7rem 1rem; border-radius: 8px; margin-bottom: 1rem;">
                    <h4 style="color: white; margin: 0; font-size: 1rem;">🔄 Transaksi Cuci Mobil + Coffee (Combo)</h4>
                </div>
                """, unsafe_allow_html=True)
                
                # Filter transaksi yang ada cuci DAN coffee
                if not df_kasir_filtered.empty:
                    df_combo = df_kasir_filtered[(df_kasir_filtered['harga_cuci'] > 0) & (df_kasir_filtered['harga_coffee'] > 0)].copy()
                    
                    if not df_combo.empty:
                        st.info(f"📋 Menampilkan {len(df_combo)} transaksi combo (cuci mobil + coffee)")
                        
                        # Search filters
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            search_combo_nopol = st.text_input("🔍 Cari Nopol", key="combo_nopol")
                        with col2:
                            search_combo_customer = st.text_input("🔍 Cari Customer", key="combo_customer")
                        with col3:
                            search_combo_paket = st.selectbox("🔍 Filter Paket", 
                                                             ["Semua"] + sorted(df_combo['paket_cuci'].unique().tolist()),
                                                             key="combo_paket")
                        
                        # Apply filters
                        df_combo_display = df_combo.copy()
                        if search_combo_nopol:
                            df_combo_display = df_combo_display[df_combo_display['nopol'].str.contains(search_combo_nopol, case=False, na=False)]
                        if search_combo_customer:
                            df_combo_display = df_combo_display[df_combo_display['nama_customer'].str.contains(search_combo_customer, case=False, na=False)]
                        if search_combo_paket != "Semua":
                            df_combo_display = df_combo_display[df_combo_display['paket_cuci'] == search_combo_paket]
                        
                        if not df_combo_display.empty:
                            # Summary
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("🚗 Total Cuci", f"Rp {df_combo_display['harga_cuci'].sum():,.0f}")
                            with col2:
                                st.metric("☕ Total Coffee", f"Rp {df_combo_display['harga_coffee'].sum():,.0f}")
                            with col3:
                                st.metric("💰 Total Keseluruhan", f"Rp {df_combo_display['total_bayar'].sum():,.0f}")
                            with col4:
                                st.metric("📊 Jumlah Transaksi", f"{len(df_combo_display)}")
                            
                            # Display table
                            df_show = df_combo_display[['tanggal', 'waktu', 'nopol', 'nama_customer', 
                                                        'paket_cuci', 'harga_cuci', 'harga_coffee', 
                                                        'total_bayar', 'metode_bayar', 'created_by']].copy()
                            df_show['harga_cuci'] = df_show['harga_cuci'].apply(lambda x: f"Rp {x:,.0f}")
                            df_show['harga_coffee'] = df_show['harga_coffee'].apply(lambda x: f"Rp {x:,.0f}")
                            df_show['total_bayar'] = df_show['total_bayar'].apply(lambda x: f"Rp {x:,.0f}")
                            df_show.columns = ['📅 Tanggal', '⏰ Waktu', '🚗 Nopol', '👤 Customer', 
                                              '📦 Paket', '🚗 Cuci', '☕ Coffee', 
                                              '💰 Total', '💳 Pembayaran', '👨‍💼 Kasir']
                            
                            st.dataframe(df_show, use_container_width=True, hide_index=True, height=400)
                            
                            # Download
                            from io import BytesIO
                            buffer = BytesIO()
                            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                                df_show.to_excel(writer, index=False, sheet_name='Combo Cuci+Coffee')
                            buffer.seek(0)
                            
                            st.download_button(
                                label="📥 Download Data Combo (Excel)",
                                data=buffer,
                                file_name=f"combo_cuci_coffee_{month_names[selected_month]}_{selected_year}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            )
                        else:
                            st.warning("🔍 Tidak ada data yang sesuai dengan filter")
                    else:
                        st.info("📭 Tidak ada transaksi combo pada periode ini")
                else:
                    st.info("📭 Tidak ada data transaksi")
            
            # ========== TAB 4: SEMUA TRANSAKSI ==========
            with tab_laporan[3]:
                st.markdown("""
                <div style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); 
                            padding: 0.7rem 1rem; border-radius: 8px; margin-bottom: 1rem;">
                    <h4 style="color: white; margin: 0; font-size: 1rem;">📊 Semua Transaksi (Gabungan)</h4>
                </div>
                """, unsafe_allow_html=True)
                st.info("💡 Gabungan dari semua jenis transaksi: Cuci saja, Coffee saja, dan Combo")
                
                # Prepare combined data
                combined_data = []
                
                # Add kasir transactions
                if not df_kasir_filtered.empty:
                    for idx, row in df_kasir_filtered.iterrows():
                        jenis_transaksi = []
                        if row['harga_cuci'] > 0:
                            jenis_transaksi.append("Cuci")
                        if row['harga_coffee'] > 0:
                            jenis_transaksi.append("Coffee")
                        
                        combined_data.append({
                            'Tanggal': row['tanggal'],
                            'Waktu': row['waktu'],
                            'Nopol': row['nopol'],
                            'Customer': row['nama_customer'],
                            'Jenis': ' + '.join(jenis_transaksi),
                            'Detail': row.get('paket_cuci', '-'),
                            'Cuci': row['harga_cuci'],
                            'Coffee': row['harga_coffee'],
                            'Total': row['total_bayar'],
                            'Metode': row.get('metode_bayar', '-'),
                            'Kasir': row.get('created_by', '-')
                        })
                
                # Add standalone coffee transactions
                if not df_coffee_filtered.empty:
                    for idx, row in df_coffee_filtered.iterrows():
                        combined_data.append({
                            'Tanggal': row['tanggal'],
                            'Waktu': row['waktu'],
                            'Nopol': '-',
                            'Customer': row.get('nama_customer', 'Walk-in'),
                            'Jenis': 'Coffee',
                            'Detail': 'Standalone',
                            'Cuci': 0,
                            'Coffee': row['total'],
                            'Total': row['total'],
                            'Metode': 'Tunai',
                            'Kasir': row.get('created_by', '-')
                        })
                
                if combined_data:
                    df_combined = pd.DataFrame(combined_data)
                    
                    # Sort by date and time
                    df_combined['tanggal_sort'] = pd.to_datetime(df_combined['Tanggal'], format='%d-%m-%Y', errors='coerce')
                    df_combined = df_combined.sort_values(['tanggal_sort', 'Waktu'], ascending=[False, False])
                    df_combined = df_combined.drop('tanggal_sort', axis=1)
                    
                    # Search filters
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        search_all_customer = st.text_input("🔍 Cari Customer/Nopol", key="all_search_customer")
                    with col2:
                        search_all_jenis = st.selectbox("🔍 Filter Jenis", 
                                                       ["Semua", "Cuci", "Coffee", "Cuci + Coffee"], 
                                                       key="all_search_jenis")
                    with col3:
                        search_all_kasir = st.text_input("🔍 Cari Kasir", key="all_search_kasir")
                    
                    # Apply filters
                    df_combined_display = df_combined.copy()
                    if search_all_customer:
                        df_combined_display = df_combined_display[
                            df_combined_display['Customer'].str.contains(search_all_customer, case=False, na=False) |
                            df_combined_display['Nopol'].str.contains(search_all_customer, case=False, na=False)
                        ]
                    if search_all_jenis != "Semua":
                        df_combined_display = df_combined_display[df_combined_display['Jenis'] == search_all_jenis]
                    if search_all_kasir:
                        df_combined_display = df_combined_display[df_combined_display['Kasir'].str.contains(search_all_kasir, case=False, na=False)]
                    
                    if not df_combined_display.empty:
                        # Summary metrics
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("💰 Total Pendapatan", f"Rp {df_combined_display['Total'].sum():,.0f}")
                        with col2:
                            st.metric("🚗 Total Cuci", f"Rp {df_combined_display['Cuci'].sum():,.0f}")
                        with col3:
                            st.metric("☕ Total Coffee", f"Rp {df_combined_display['Coffee'].sum():,.0f}")
                        with col4:
                            st.metric("📊 Jumlah", f"{len(df_combined_display)} transaksi")
                        
                        st.markdown("---")
                        
                        # Format display
                        df_show_combined = df_combined_display.copy()
                        df_show_combined['Cuci'] = df_show_combined['Cuci'].apply(lambda x: f"Rp {x:,.0f}" if x > 0 else "-")
                        df_show_combined['Coffee'] = df_show_combined['Coffee'].apply(lambda x: f"Rp {x:,.0f}" if x > 0 else "-")
                        df_show_combined['Total'] = df_show_combined['Total'].apply(lambda x: f"Rp {x:,.0f}")
                        
                        # Reorder columns
                        df_show_combined = df_show_combined[['Tanggal', 'Waktu', 'Nopol', 'Customer', 
                                                              'Jenis', 'Detail', 'Cuci', 'Coffee', 'Total', 
                                                              'Metode', 'Kasir']]
                        
                        df_show_combined.columns = ['📅 Tanggal', '⏰ Waktu', '🚗 Nopol', '👤 Customer', 
                                                   '🔖 Jenis', '📝 Detail', '🚗 Cuci', '☕ Coffee', 
                                                   '💰 Total', '💳 Pembayaran', '👨‍💼 Kasir']
                        
                        st.dataframe(df_show_combined, use_container_width=True, hide_index=True, height=450)
                        
                        # Download button for combined data
                        from io import BytesIO
                        buffer = BytesIO()
                        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                            df_show_combined.to_excel(writer, index=False, sheet_name='Semua Transaksi')
                        buffer.seek(0)
                        
                        st.download_button(
                            label="📥 Download Semua Transaksi (Excel)",
                            data=buffer,
                            file_name=f"semua_transaksi_{month_names[selected_month]}_{selected_year}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    else:
                        st.warning("🔍 Tidak ada transaksi yang sesuai filter")
                else:
                    st.info("📭 Tidak ada data transaksi")
            
            # ========== ANALISIS & RINGKASAN ==========
            st.markdown("---")
            st.markdown("""
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        padding: 0.7rem 1rem; border-radius: 8px; margin: 1rem 0;">
                <h4 style="color: white; margin: 0; font-size: 1rem;">📊 Analisis Transaksi</h4>
            </div>
            """, unsafe_allow_html=True)
            
            if not df_kasir_filtered.empty:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("##### 💳 Metode Pembayaran")
                    payment_summary = df_kasir_filtered.groupby('metode_bayar').agg(
                        Jumlah=('id', 'count'),
                        Total=('total_bayar', 'sum')
                    ).reset_index()
                    payment_summary.columns = ['Metode', 'Jumlah', 'Total']
                    payment_summary = payment_summary.sort_values('Total', ascending=False)
                    
                    # Format display
                    df_payment_display = payment_summary.copy()
                    df_payment_display['Total'] = df_payment_display['Total'].apply(lambda x: f"Rp {x:,.0f}")
                    df_payment_display['%'] = (payment_summary['Jumlah'] / payment_summary['Jumlah'].sum() * 100).round(1).astype(str) + '%'
                    
                    st.dataframe(df_payment_display, use_container_width=True, hide_index=True)
                
                with col2:
                    st.markdown("##### 📈 Grafik Metode Pembayaran")
                    chart = alt.Chart(payment_summary).mark_arc(innerRadius=50).encode(
                        theta='Total:Q',
                        color=alt.Color('Metode:N', scale=alt.Scale(scheme='category10'), 
                                       legend=alt.Legend(orient='bottom')),
                        tooltip=['Metode:N', alt.Tooltip('Total:Q', format=',.0f', title='Rp'), 'Jumlah:Q']
                    ).properties(height=250)
                    st.altair_chart(chart, use_container_width=True)
        else:
            st.info("📭 Tidak ada data transaksi untuk periode ini")
        
        st.markdown('</div>', unsafe_allow_html=True)

def setting_toko_page(role):
    st.markdown("""
    <style>
    .setting-header {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 15px rgba(245, 87, 108, 0.3);
    }
    .setting-header h2 {
        margin: 0;
        font-size: 1.8rem;
        font-weight: 700;
    }
    .setting-section {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        margin-bottom: 1.5rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="setting-header"><h2>⚙️ Setting Toko</h2></div>', unsafe_allow_html=True)
    
    # Check role
    if role not in ["Admin", "Supervisor"]:
        st.warning("⚠️ Hanya Admin dan Supervisor yang dapat mengakses halaman ini")
        return
    
    # Create tabs
    tab1, tab2 = st.tabs(["🏪 Info Toko", "🗄️ Database Management"])
    
    with tab1:
        st.subheader("🏪 Informasi Toko")
        
        toko_info = get_setting("toko_info")
        if not toko_info:
            toko_info = {
                "nama": "TIME AUTOCARE",
                "tagline": "Detailing & Ceramic Coating",
                "alamat": "Jl. Contoh No. 123",
                "telp": "08123456789",
                "email": "info@timeautocare.com"
            }
        
        with st.form("toko_info_form"):
            st.info("ℹ️ Informasi ini akan muncul di laporan dan dokumen")
            
            nama_toko = st.text_input("🏪 Nama Toko", value=toko_info.get("nama", ""))
            tagline_toko = st.text_input("✨ Tagline", value=toko_info.get("tagline", ""), placeholder="Contoh: Detailing & Ceramic Coating")
            alamat_toko = st.text_area("📍 Alamat", value=toko_info.get("alamat", ""))
            col1, col2 = st.columns(2)
            with col1:
                telp_toko = st.text_input("📞 Telepon", value=toko_info.get("telp", ""))
            with col2:
                email_toko = st.text_input("📧 Email", value=toko_info.get("email", ""))
            
            submitted = st.form_submit_button("💾 Simpan Info Toko", type="primary", use_container_width=True)
            
            if submitted:
                new_toko_info = {
                    "nama": nama_toko,
                    "tagline": tagline_toko,
                    "alamat": alamat_toko,
                    "telp": telp_toko,
                    "email": email_toko
                }
                success, msg = update_setting("toko_info", new_toko_info)
                if success:
                    add_audit("setting_toko", "Update info toko")
                    st.success("✅ Info toko berhasil diupdate")
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")
    
    with tab2:
        st.subheader("🗄️ Database Management")
        st.warning("⚠️ **PERHATIAN:** Fitur ini hanya untuk Admin. Berhati-hatilah saat menggunakan fitur ini!")
        
        # Check database stats
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM customers")
        customer_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM wash_transactions")
        wash_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM kasir_transactions")
        kasir_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM employees")
        employee_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM customer_reviews")
        review_count = c.fetchone()[0]
        
        conn.close()
        
        st.markdown("### 📊 Status Database Saat Ini")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("👥 Pelanggan", customer_count)
        with col2:
            st.metric("🚗 Transaksi Cuci", wash_count)
        with col3:
            st.metric("💰 Transaksi Kasir", kasir_count)
        with col4:
            st.metric("👨‍💼 Karyawan", employee_count)
        with col5:
            st.metric("⭐ Review", review_count)
        
        st.markdown("---")
        
        col_a, col_b = st.columns(2)
        
        with col_a:
            st.markdown("### 🔄 Reset & Populate Data Dummy")
            st.info("""
            **Fitur ini akan:**
            1. Menghapus SEMUA data transaksi yang ada
            2. Membuat data dummy baru yang lengkap
            
            **Data yang dibuat:**
            - 30 pelanggan dummy
            - 6 karyawan dummy
            - 100 transaksi cuci mobil
            - 50 transaksi coffee/snack
            - Review pelanggan
            - Presensi & gaji karyawan
            """)
            
            # Confirmation checkbox
            confirm_reset = st.checkbox("✅ Saya mengerti risiko dan ingin reset database")
            
            if st.button("🔄 Reset & Populate Data Dummy", 
                        type="primary", 
                        use_container_width=True,
                        disabled=not confirm_reset):
                with st.spinner("🔄 Sedang reset database dan membuat data dummy..."):
                    # Reset database
                    success_reset, msg_reset = reset_database()
                    
                    if success_reset:
                        st.info(msg_reset)
                        
                        # Populate data dummy
                        success_populate, msg_populate = populate_dummy_data()
                        
                        if success_populate:
                            add_audit("reset_database", "Reset database dan populate data dummy")
                            st.success("✅ Database berhasil di-reset dan data dummy berhasil dibuat!")
                            st.balloons()
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error(f"❌ Error populate data: {msg_populate}")
                    else:
                        st.error(f"❌ Error reset database: {msg_reset}")
        
        with col_b:
            st.markdown("### 💾 Backup Database")
            st.info("""
            **Fitur ini akan:**
            - Membuat salinan database saat ini
            - File akan disimpan dengan timestamp
            """)
            
            if st.button("💾 Backup Database", type="secondary", use_container_width=True):
                import shutil
                from datetime import datetime
                
                try:
                    # Create backup filename with timestamp
                    backup_time = datetime.now(WIB).strftime("%Y%m%d_%H%M%S")
                    backup_filename = f"car_wash_backup_{backup_time}.db"
                    
                    # Copy database file
                    shutil.copy2(DB_NAME, backup_filename)
                    
                    st.success(f"✅ Backup berhasil dibuat: {backup_filename}")
                    add_audit("backup_database", f"Backup database: {backup_filename}")
                    
                    # Offer download
                    with open(backup_filename, 'rb') as f:
                        st.download_button(
                            label="📥 Download Backup",
                            data=f,
                            file_name=backup_filename,
                            mime="application/x-sqlite3"
                        )
                except Exception as e:
                    st.error(f"❌ Error backup database: {str(e)}")
            
            st.markdown("---")
            
            st.markdown("### 🧹 Hapus Data Lama")
            st.info("""
            **Fitur ini akan menghapus:**
            - Transaksi lebih dari X hari
            - Review lama
            - Audit trail lama
            
            *(Coming soon)*
            """)
            
            days_to_keep = st.number_input("Simpan data X hari terakhir", min_value=30, max_value=365, value=90)
            
            st.button("🧹 Bersihkan Data Lama", type="secondary", use_container_width=True, disabled=True)

def audit_trail_page():
    st.header("Audit Trail")
    role = st.session_state.get("login_role", "-")
    uname = st.session_state.get("login_user", "-")
    
    if role == "Supervisor":
        st.info("Sebagai Supervisor, Anda dapat melihat semua aktivitas dari semua user.")
    else:
        st.info("Anda hanya dapat melihat aktivitas Anda sendiri.")
    
    # Load audit trail dari database
    df_audit = load_audit_trail()

    # Filters
    c1, c2, c3 = st.columns([1,1,1.2])
    all_users = sorted(df_audit['user'].dropna().unique().tolist()) if not df_audit.empty else []
    with c1:
        if role == "Supervisor":
            user_filter = st.multiselect("Filter User", options=all_users, default=all_users)
        else:
            user_filter = [uname]
            st.multiselect("Filter User", options=[uname], default=[uname], disabled=True)
    with c2:
        search = st.text_input("Cari kata kunci", placeholder="action/detail...")
    with c3:
        if not df_audit.empty:
            # Parse timestamps dengan format fleksibel (support format lama dan baru)
            df_audit['timestamp_dt'] = pd.to_datetime(df_audit['timestamp'], format='mixed', dayfirst=True, errors='coerce')
            date_min = df_audit['timestamp_dt'].min().date()
            date_max = df_audit['timestamp_dt'].max().date()
        else:
            date_min = date_max = datetime.now().date()
        date_range = st.date_input("Rentang tanggal", value=(date_min, date_max))

    # Apply filters
    if not df_audit.empty:
        # timestamp_dt sudah di-parse di atas
        
        # Filter by user
        if user_filter:
            df_audit = df_audit[df_audit['user'].isin(user_filter)]
        
        # Filter by search keyword
        if search:
            mask = df_audit['action'].str.contains(search, case=False, na=False) | df_audit['detail'].str.contains(search, case=False, na=False)
            df_audit = df_audit[mask]
        
        # Filter by date range
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start_d, end_d = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
            df_audit = df_audit[(df_audit['timestamp_dt'] >= start_d) & (df_audit['timestamp_dt'] <= end_d + pd.Timedelta(days=1))]
        
        # Display results
        df_display = df_audit.drop(columns=['timestamp_dt', 'id']).sort_values('timestamp', ascending=False)
        st.dataframe(df_display, use_container_width=True)
        
        # Statistics
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Records", len(df_display))
        with col2:
            st.metric("Unique Users", df_display['user'].nunique())
        with col3:
            st.metric("Unique Actions", df_display['action'].nunique())
    else:
        st.info("Belum ada data audit trail.")

def user_setting_page():
    st.markdown("""
    <style>
    .user-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 20px rgba(102, 126, 234, 0.4);
    }
    .user-header h1 {
        margin: 0;
        font-size: 2rem;
        font-weight: 800;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('''
    <div class="user-header">
        <h1>👤 User Management</h1>
    </div>
    ''', unsafe_allow_html=True)
    
    uname = st.session_state.get("login_user", "-")
    role = st.session_state.get("login_role", "-")
    
    # Admin-only tabs
    if role == "Admin":
        tab1, tab2, tab3 = st.tabs(["👥 Kelola User", "➕ Tambah User", "🔐 Ganti Password Saya"])
        
        with tab1:
            st.subheader("📋 Daftar User")
            df_users = get_all_users()
            
            if not df_users.empty:
                # Display users
                st.dataframe(
                    df_users,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "id": st.column_config.NumberColumn("ID", width="small"),
                        "username": st.column_config.TextColumn("Username", width="medium"),
                        "role": st.column_config.TextColumn("Role", width="small"),
                        "created_at": st.column_config.TextColumn("Dibuat", width="medium"),
                        "created_by": st.column_config.TextColumn("Oleh", width="small"),
                        "last_login": st.column_config.TextColumn("Login Terakhir", width="medium")
                    }
                )
                
                st.markdown("---")
                st.subheader("✏️ Edit User")
                
                # Select user to edit
                usernames = df_users['username'].tolist()
                selected_user = st.selectbox("Pilih User", usernames, key="edit_user_select")
                
                if selected_user:
                    user_data = get_user_from_db(selected_user)
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.info(f"**Username:** {selected_user}")
                        st.info(f"**Role Saat Ini:** {user_data['role']}")
                    
                    with col2:
                        new_role = st.selectbox(
                            "Ganti Role",
                            ["Admin", "Supervisor", "Kasir"],
                            index=["Admin", "Supervisor", "Kasir"].index(user_data['role'])
                        )
                        new_password = st.text_input("Password Baru (opsional)", type="password", 
                                                    placeholder="Kosongkan jika tidak ingin mengubah")
                    
                    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
                    
                    with col_btn2:
                        if st.button("💾 Update User", type="primary", use_container_width=True):
                            if new_password and len(new_password) < 6:
                                st.error("❌ Password minimal 6 karakter!")
                            else:
                                success, msg = update_user(selected_user, new_password if new_password else None, new_role)
                                if success:
                                    add_audit("update_user", f"User {selected_user}: role → {new_role}" + 
                                             (", password diubah" if new_password else ""))
                                    st.success(f"✅ {msg}")
                                    st.balloons()
                                    st.rerun()
                                else:
                                    st.error(f"❌ {msg}")
                    
                    with col_btn3:
                        if selected_user != "admin" and selected_user != uname:
                            if st.button("🗑️ Hapus User", use_container_width=True):
                                success, msg = delete_user(selected_user)
                                if success:
                                    add_audit("delete_user", f"User {selected_user} dihapus")
                                    st.success(f"✅ {msg}")
                                    st.rerun()
                                else:
                                    st.error(f"❌ {msg}")
                        else:
                            st.caption("⚠️ Tidak dapat menghapus user ini")
            else:
                st.warning("⚠️ Tidak ada user dalam database")
        
        with tab2:
            st.subheader("➕ Tambah User Baru")
            
            with st.form("add_user_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    new_username = st.text_input("Username *", placeholder="username_baru").lower()
                    new_user_password = st.text_input("Password *", type="password", placeholder="Min. 6 karakter")
                
                with col2:
                    new_user_role = st.selectbox("Role *", ["Admin", "Supervisor", "Kasir"])
                    confirm_password = st.text_input("Konfirmasi Password *", type="password")
                
                submitted = st.form_submit_button("💾 Tambah User", type="primary", use_container_width=True)
                
                if submitted:
                    if not new_username or not new_user_password:
                        st.error("❌ Username dan Password wajib diisi!")
                    elif len(new_user_password) < 6:
                        st.error("❌ Password minimal 6 karakter!")
                    elif new_user_password != confirm_password:
                        st.error("❌ Konfirmasi password tidak cocok!")
                    else:
                        success, msg = add_user(new_username, new_user_password, new_user_role, uname)
                        if success:
                            add_audit("add_user", f"User baru: {new_username} ({new_user_role})")
                            st.success(f"✅ {msg}")
                            st.balloons()
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")
        
        with tab3:
            st.subheader("🔐 Ganti Password Saya")
            st.info(f"User: **{uname}** | Role: **{role}**")
            
            with st.form("change_my_password_form"):
                current_password = st.text_input("Password Saat Ini", type="password")
                my_new_password = st.text_input("Password Baru", type="password", placeholder="Min. 6 karakter")
                my_confirm_password = st.text_input("Konfirmasi Password Baru", type="password")
                
                submitted = st.form_submit_button("💾 Ganti Password", type="primary", use_container_width=True)
                
                if submitted:
                    user_data = get_user_from_db(uname)
                    if not user_data:
                        st.error("❌ User tidak ditemukan!")
                    elif current_password != user_data['password']:
                        st.error("❌ Password saat ini salah!")
                    elif len(my_new_password) < 6:
                        st.error("❌ Password baru minimal 6 karakter!")
                    elif my_new_password != my_confirm_password:
                        st.error("❌ Konfirmasi password tidak cocok!")
                    else:
                        success, msg = update_user(uname, my_new_password, None)
                        if success:
                            add_audit("change_password", "Password diubah")
                            st.success("✅ Password berhasil diubah!")
                            st.balloons()
                        else:
                            st.error(f"❌ {msg}")
    
    else:
        # Non-admin users can only change their own password
        st.subheader("🔐 Ganti Password")
        st.info(f"User: **{uname}** | Role: **{role}**")
        
        with st.form("change_password_form"):
            current_password = st.text_input("Password Saat Ini", type="password")
            new_password = st.text_input("Password Baru", type="password", placeholder="Min. 6 karakter")
            confirm_password = st.text_input("Konfirmasi Password Baru", type="password")
            
            submitted = st.form_submit_button("💾 Ganti Password", type="primary", use_container_width=True)
            
            if submitted:
                user_data = get_user_from_db(uname)
                if not user_data:
                    st.error("❌ User tidak ditemukan!")
                elif current_password != user_data['password']:
                    st.error("❌ Password saat ini salah!")
                elif len(new_password) < 6:
                    st.error("❌ Password baru minimal 6 karakter!")
                elif new_password != confirm_password:
                    st.error("❌ Konfirmasi password tidak cocok!")
                else:
                    success, msg = update_user(uname, new_password, None)
                    if success:
                        add_audit("change_password", "Password diubah")
                        st.success("✅ Password berhasil diubah!")
                        st.balloons()
                    else:
                        st.error(f"❌ {msg}")

def review_customer_page():
    st.markdown("""
    <style>
    .review-header {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 15px rgba(240, 147, 251, 0.3);
    }
    .review-detail-card {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 12px;
        border-left: 4px solid #f093fb;
        margin-top: 1rem;
    }
    .star-display {
        color: #ffd700;
        font-size: 1.5rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="review-header"><h2 style="margin:0;">⭐ Customer Reviews & Rewards</h2><p style="margin:0.5rem 0 0 0; opacity:0.9;">Evaluasi pelayanan dan manajemen poin customer</p></div>', unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["📝 Semua Review", "🎁 Customer Points", "📊 Statistik"])
    
    with tab1:
        st.subheader("📝 Daftar Review Customer")
        
        df_reviews = get_all_reviews()
        
        if df_reviews.empty:
            st.info("📭 Belum ada review dari customer")
        else:
            # Filter
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                search_name = st.text_input("🔍 Cari Nama Customer", key="search_review_name")
            with col2:
                filter_rating = st.selectbox("⭐ Filter Rating", ["Semua", "5", "4", "3", "2", "1"], key="filter_rating")
            
            # Apply filter
            df_filtered = df_reviews.copy()
            if search_name:
                df_filtered = df_filtered[df_filtered['nama_customer'].str.contains(search_name, case=False, na=False)]
            if filter_rating != "Semua":
                df_filtered = df_filtered[df_filtered['rating'] == int(filter_rating)]
            
            if not df_filtered.empty:
                st.success(f"📊 **{len(df_filtered)} review** ditemukan")
                
                # Prepare data for table
                df_display = df_filtered.copy()
                df_display['⭐ Rating'] = df_display['rating'].apply(lambda x: "⭐" * x)
                df_display['👤 Customer'] = df_display['nama_customer']
                df_display['🚗 Nopol'] = df_display['nopol'].apply(lambda x: x if x else 'Coffee Only')
                df_display['📅 Tanggal'] = df_display['review_date']
                df_display['⏰ Waktu'] = df_display['review_time']
                df_display['🎁 Poin'] = df_display['reward_points']
                
                # Add selection column
                df_display.insert(0, '📋', False)
                
                # Display editable table with selection
                edited_df = st.data_editor(
                    df_display[['📋', '👤 Customer', '🚗 Nopol', '⭐ Rating', '📅 Tanggal', '⏰ Waktu', '🎁 Poin']],
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "📋": st.column_config.CheckboxColumn(
                            "Pilih",
                            help="Pilih untuk melihat detail review",
                            default=False,
                        )
                    },
                    disabled=['👤 Customer', '🚗 Nopol', '⭐ Rating', '📅 Tanggal', '⏰ Waktu', '🎁 Poin'],
                    key="review_table"
                )
                
                # Show detail of selected review
                selected_rows = edited_df[edited_df['📋'] == True]
                
                if not selected_rows.empty:
                    st.markdown("---")
                    st.markdown("### 📖 Detail Review yang Dipilih")
                    
                    for idx, row in selected_rows.iterrows():
                        # Get original review data
                        original_idx = df_display[
                            (df_display['👤 Customer'] == row['👤 Customer']) & 
                            (df_display['📅 Tanggal'] == row['📅 Tanggal']) &
                            (df_display['⏰ Waktu'] == row['⏰ Waktu'])
                        ].index[0]
                        
                        review_data = df_filtered.loc[original_idx]
                        
                        with st.container():
                            st.markdown('<div class="review-detail-card">', unsafe_allow_html=True)
                            
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.markdown(f"**👤 Customer:** {review_data['nama_customer']}")
                                st.markdown(f"**🚗 Nopol:** {review_data['nopol'] if review_data['nopol'] else 'Coffee Only'}")
                                st.markdown(f"**📅 Tanggal:** {review_data['review_date']} {review_data['review_time']}")
                            with col2:
                                st.markdown(f'<div class="star-display" style="text-align:center;">{"⭐" * review_data["rating"]}<br>({review_data["rating"]}/5)</div>', unsafe_allow_html=True)
                                st.markdown(f"<div style='text-align:center; margin-top:0.5rem;'>🎁 **+{review_data['reward_points']} poin**</div>", unsafe_allow_html=True)
                            
                            st.markdown("---")
                            st.markdown("**💬 Review:**")
                            st.info(review_data['review_text'])
                            
                            st.markdown('</div>', unsafe_allow_html=True)
                            st.markdown("<br>", unsafe_allow_html=True)
                
                # Statistik singkat
                st.markdown("---")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    avg_rating = df_filtered['rating'].mean()
                    st.metric("📊 Rata-rata Rating", f"{avg_rating:.2f} ⭐")
                with col2:
                    rating_5 = len(df_filtered[df_filtered['rating'] == 5])
                    st.metric("⭐⭐⭐⭐⭐", rating_5)
                with col3:
                    rating_4 = len(df_filtered[df_filtered['rating'] == 4])
                    st.metric("⭐⭐⭐⭐", rating_4)
                with col4:
                    total_reviews = len(df_filtered)
                    st.metric("📝 Total Review", total_reviews)
            else:
                st.warning("⚠️ Tidak ada review yang sesuai filter")
    
    with tab2:
        st.subheader("🎁 Customer Reward Points")
        
        df_points = get_all_customer_points()
        
        if df_points.empty:
            st.info("📭 Belum ada customer yang mengumpulkan poin")
        else:
            st.success(f"👥 **{len(df_points)} customer** memiliki poin reward")
            
            # Display points leaderboard
            df_display = df_points[['nama_customer', 'nopol', 'no_telp', 'total_points', 'last_updated']].copy()
            df_display.columns = ['👤 Nama', '🚗 Nopol', '📱 Telp', '🎁 Total Poin', '📅 Update Terakhir']
            
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
            # Statistik
            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            with col1:
                total_points_given = df_points['total_points'].sum()
                st.metric("🎁 Total Poin Diberikan", total_points_given)
            with col2:
                avg_points = df_points['total_points'].mean()
                st.metric("📊 Rata-rata Poin/Customer", f"{avg_points:.1f}")
            with col3:
                top_customer = df_points.iloc[0] if not df_points.empty else None
                if top_customer is not None:
                    st.metric("🏆 Top Customer", f"{top_customer['nama_customer'][:15]}...")
    
    with tab3:
        st.subheader("📊 Statistik Review")
        
        df_reviews = get_all_reviews()
        
        if not df_reviews.empty:
            # Rating distribution
            st.markdown("#### ⭐ Distribusi Rating")
            rating_counts = df_reviews['rating'].value_counts().sort_index(ascending=False)
            
            for rating in [5, 4, 3, 2, 1]:
                count = rating_counts.get(rating, 0)
                percentage = (count / len(df_reviews) * 100) if len(df_reviews) > 0 else 0
                col1, col2, col3 = st.columns([1, 3, 1])
                with col1:
                    st.write(f"{'⭐' * rating}")
                with col2:
                    st.progress(percentage / 100)
                with col3:
                    st.write(f"{count} ({percentage:.1f}%)")
            
            # Review trend by date
            st.markdown("---")
            st.markdown("#### 📈 Trend Review")
            
            df_reviews['review_date_parsed'] = pd.to_datetime(df_reviews['review_date'], format='%d-%m-%Y', errors='coerce')
            reviews_by_date = df_reviews.groupby(df_reviews['review_date_parsed'].dt.date).size().reset_index()
            reviews_by_date.columns = ['Tanggal', 'Jumlah Review']
            
            if not reviews_by_date.empty:
                st.line_chart(reviews_by_date.set_index('Tanggal'))
            
            # Summary metrics
            st.markdown("---")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📝 Total Review", len(df_reviews))
            with col2:
                avg_rating = df_reviews['rating'].mean()
                st.metric("⭐ Rating Rata-rata", f"{avg_rating:.2f}")
            with col3:
                positive_reviews = len(df_reviews[df_reviews['rating'] >= 4])
                positive_pct = (positive_reviews / len(df_reviews) * 100)
                st.metric("👍 Review Positif", f"{positive_pct:.1f}%")
            with col4:
                total_points_given = len(df_reviews) * 10
                st.metric("🎁 Total Poin Diberikan", total_points_given)
        else:
            st.info("📭 Belum ada data review untuk ditampilkan")

def payroll_page(role):
    """Halaman Payroll - hanya bisa diakses Admin dan Kasir"""
    st.markdown('<p class="big-title">💼 Sistem Payroll</p>', unsafe_allow_html=True)
    st.markdown("---")
    
    # Tab untuk berbagai fitur payroll
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["👥 Data Karyawan", "📋 Presensi", "💰 Hitung Gaji", "📊 Riwayat Gaji", "💸 Kas Bon", "⚙️ Setting Shift"])
    
    with tab1:
        st.markdown("### 👥 Manajemen Data Karyawan")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Display employees
            employees = get_all_employees()
            if employees:
                df_emp = pd.DataFrame(employees)
                df_emp['gaji_display'] = df_emp.apply(
                    lambda x: f"Rp {x['gaji_tetap']:,.0f}" if x['role_karyawan'] in ['Kasir', 'Supervisor'] else f"{x['shift']} ({get_shift_settings()[0 if x['shift']=='Pagi' else 1]['persentase_gaji']}% dari pendapatan)",
                    axis=1
                )
                
                st.dataframe(
                    df_emp[['id', 'nama', 'role_karyawan', 'gaji_display', 'shift', 'jam_masuk_default', 'jam_pulang_default', 'status', 'no_telp']],
                    use_container_width=True
                )
            else:
                st.info("Belum ada data karyawan")
        
        with col2:
            st.markdown("#### ➕ Tambah Karyawan")
            with st.form("add_employee_form"):
                nama = st.text_input("Nama Lengkap*")
                role_karyawan = st.selectbox("Role Karyawan*", ["Worker Cuci Mobil", "Washer", "QC Inspector", "Kasir", "Supervisor"])
                
                if role_karyawan in ["Kasir", "Supervisor"]:
                    gaji_tetap = st.number_input("Gaji Tetap/Minggu (Rp)*", min_value=0, step=100000, value=500000)
                    shift = st.selectbox("Shift", ["Pagi", "Malam"])
                else:
                    gaji_tetap = 0
                    shift = st.selectbox("Shift*", ["Pagi", "Malam"])
                    st.info(f"💡 Gaji worker mengikuti persentase dari pendapatan cuci mobil")
                
                jam_masuk = st.time_input("Jam Masuk Default", value=dt_time(8, 0))
                jam_pulang = st.time_input("Jam Pulang Default", value=dt_time(17, 0))
                no_telp = st.text_input("No Telepon")
                
                submit = st.form_submit_button("Simpan Karyawan", use_container_width=True)
                
                if submit:
                    if nama and role_karyawan:
                        add_employee(
                            nama, role_karyawan, gaji_tetap, shift,
                            jam_masuk.strftime("%H:%M"), jam_pulang.strftime("%H:%M"),
                            no_telp, st.session_state.get('login_user')
                        )
                        add_audit("add_employee", f"Tambah karyawan: {nama} - {role_karyawan}")
                        st.success(f"✅ Karyawan {nama} berhasil ditambahkan!")
                        st.rerun()
                    else:
                        st.error("Nama dan role karyawan harus diisi!")
        
        # Edit/Delete employee
        if employees:
            st.markdown("---")
            st.markdown("#### ✏️ Edit / Hapus Karyawan")
            
            emp_names = {f"{e['id']} - {e['nama']}": e for e in employees}
            selected_emp_name = st.selectbox("Pilih Karyawan", list(emp_names.keys()))
            
            if selected_emp_name:
                emp = emp_names[selected_emp_name]
                
                col_edit, col_delete = st.columns([3, 1])
                
                with col_edit:
                    with st.form("edit_employee_form"):
                        st.markdown(f"**Edit Data: {emp['nama']}**")
                        
                        edit_nama = st.text_input("Nama", value=emp['nama'])
                        
                        # List semua role yang mungkin
                        all_roles = ["Worker Cuci Mobil", "Washer", "QC Inspector", "Kasir", "Supervisor"]
                        # Cari index dari role saat ini, default 0 jika tidak ditemukan
                        try:
                            role_index = all_roles.index(emp['role_karyawan'])
                        except ValueError:
                            role_index = 0
                        
                        edit_role = st.selectbox("Role", all_roles, index=role_index)
                        
                        if edit_role in ["Kasir", "Supervisor"]:
                            edit_gaji = st.number_input("Gaji Tetap/Minggu (Rp)", min_value=0, step=100000, value=emp['gaji_tetap'])
                        else:
                            edit_gaji = 0
                            st.info(f"💡 Gaji worker mengikuti persentase dari pendapatan cuci mobil")
                        
                        edit_shift = st.selectbox("Shift", ["Pagi", "Malam"], index=["Pagi", "Malam"].index(emp['shift']) if emp['shift'] in ["Pagi", "Malam"] else 0)
                        edit_jam_masuk = st.time_input("Jam Masuk", value=datetime.strptime(emp['jam_masuk_default'], "%H:%M").time())
                        edit_jam_pulang = st.time_input("Jam Pulang", value=datetime.strptime(emp['jam_pulang_default'], "%H:%M").time())
                        edit_no_telp = st.text_input("No Telepon", value=emp['no_telp'] or "")
                        edit_status = st.selectbox("Status", ["Aktif", "Nonaktif"], index=["Aktif", "Nonaktif"].index(emp['status']))
                        
                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            submit_edit = st.form_submit_button("💾 Update Data", use_container_width=True)
                        with col_btn2:
                            cancel_edit = st.form_submit_button("❌ Batal", use_container_width=True)
                        
                        if submit_edit:
                            update_employee(
                                emp['id'], edit_nama, edit_role, edit_gaji, edit_shift,
                                edit_jam_masuk.strftime("%H:%M"), edit_jam_pulang.strftime("%H:%M"),
                                edit_no_telp, edit_status
                            )
                            add_audit("update_employee", f"Update karyawan: {edit_nama}")
                            st.success("✅ Data karyawan berhasil diupdate!")
                            st.rerun()
                
                with col_delete:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🗑️ Hapus Karyawan", use_container_width=True, type="secondary"):
                        delete_employee(emp['id'])
                        add_audit("delete_employee", f"Hapus karyawan: {emp['nama']}")
                        st.success(f"✅ Karyawan {emp['nama']} berhasil dihapus!")
                        st.rerun()
    
    with tab2:
        st.markdown("### 📋 Presensi Karyawan")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown("#### ➕ Input Presensi")
            
            employees = get_all_employees()
            active_employees = [e for e in employees if e['status'] == 'Aktif']
            
            if active_employees:
                with st.form("attendance_form"):
                    emp_options = {f"{e['nama']} ({e['role_karyawan']})": e for e in active_employees}
                    selected_emp = st.selectbox("Pilih Karyawan*", list(emp_options.keys()))
                    
                    emp_data = emp_options[selected_emp]
                    
                    tanggal = st.date_input("Tanggal*", value=datetime.now(WIB))
                    
                    col_jam1, col_jam2 = st.columns(2)
                    with col_jam1:
                        default_masuk = datetime.strptime(emp_data['jam_masuk_default'], "%H:%M").time()
                        jam_masuk = st.time_input("Jam Masuk*", value=default_masuk)
                    with col_jam2:
                        default_pulang = datetime.strptime(emp_data['jam_pulang_default'], "%H:%M").time()
                        jam_pulang = st.time_input("Jam Pulang", value=default_pulang)
                    
                    shift = st.selectbox("Shift*", ["Pagi", "Malam"], index=["Pagi", "Malam"].index(emp_data['shift']) if emp_data['shift'] else 0)
                    status = st.selectbox("Status Kehadiran*", ["Hadir", "Terlambat", "Pulang Awal", "Izin", "Sakit", "Alpha"])
                    catatan = st.text_area("Catatan")
                    
                    submit_attendance = st.form_submit_button("💾 Simpan Presensi", use_container_width=True)
                    
                    if submit_attendance:
                        add_attendance(
                            emp_data['id'],
                            tanggal.strftime("%d-%m-%Y"),
                            jam_masuk.strftime("%H:%M"),
                            jam_pulang.strftime("%H:%M") if jam_pulang else None,
                            shift,
                            status,
                            catatan,
                            st.session_state.get('login_user')
                        )
                        add_audit("add_attendance", f"Presensi: {emp_data['nama']} - {tanggal.strftime('%d-%m-%Y')}")
                        st.success(f"✅ Presensi {emp_data['nama']} berhasil disimpan!")
                        st.rerun()
            else:
                st.warning("⚠️ Belum ada karyawan aktif")
        
        with col2:
            st.markdown("#### 📊 Data Presensi")
            
            # Filter tanggal
            col_date1, col_date2 = st.columns(2)
            with col_date1:
                start_date = st.date_input("Dari Tanggal", value=datetime.now(WIB) - timedelta(days=7))
            with col_date2:
                end_date = st.date_input("Sampai Tanggal", value=datetime.now(WIB))
            
            attendance_data = get_attendance_by_date_range(
                start_date.strftime("%d-%m-%Y"),
                end_date.strftime("%d-%m-%Y")
            )
            
            if attendance_data:
                df_att = pd.DataFrame(attendance_data)
                st.dataframe(
                    df_att[['tanggal', 'nama', 'role_karyawan', 'shift', 'jam_masuk', 'jam_pulang', 'status', 'catatan']],
                    use_container_width=True
                )
                
                # Summary
                st.markdown("---")
                col_sum1, col_sum2, col_sum3 = st.columns(3)
                with col_sum1:
                    total_hadir = len(df_att[df_att['status'] == 'Hadir'])
                    st.metric("✅ Total Hadir", total_hadir)
                with col_sum2:
                    total_terlambat = len(df_att[df_att['status'] == 'Terlambat'])
                    st.metric("⏰ Terlambat", total_terlambat)
                with col_sum3:
                    total_izin = len(df_att[df_att['status'].isin(['Izin', 'Sakit'])])
                    st.metric("📝 Izin/Sakit", total_izin)
            else:
                st.info("📭 Belum ada data presensi untuk periode ini")
    
    with tab3:
        st.markdown("### 💰 Perhitungan Gaji Mingguan")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("#### 🧮 Hitung Gaji Periode")
            
            with st.form("calculate_salary_form"):
                # Pilih periode
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    periode_awal = st.date_input("Periode Awal*", value=datetime.now(WIB) - timedelta(days=7))
                with col_p2:
                    periode_akhir = st.date_input("Periode Akhir*", value=datetime.now(WIB))
                
                # Pilih karyawan
                employees = get_all_employees()
                active_employees = [e for e in employees if e['status'] == 'Aktif']
                
                if active_employees:
                    emp_options = {f"{e['id']} - {e['nama']} ({e['role_karyawan']})": e for e in active_employees}
                    selected_emp = st.selectbox("Pilih Karyawan*", list(emp_options.keys()))
                    emp_data = emp_options[selected_emp]
                    
                    st.info(f"**Role:** {emp_data['role_karyawan']}\n\n**Shift:** {emp_data['shift']}")
                    
                    # Bonus dan potongan
                    bonus = st.number_input("Bonus (Rp)", min_value=0, step=50000, value=0)
                    potongan = st.number_input("Potongan (Rp)", min_value=0, step=50000, value=0)
                    catatan = st.text_area("Catatan")
                    
                    calculate_btn = st.form_submit_button("🧮 Hitung Gaji", use_container_width=True)
                    
                    if calculate_btn:
                        # Get attendance data untuk periode ini
                        attendance_data = get_attendance_by_date_range(
                            periode_awal.strftime("%d-%m-%Y"),
                            periode_akhir.strftime("%d-%m-%Y")
                        )
                        
                        # Filter by employee
                        emp_attendance = [a for a in attendance_data if a['employee_id'] == emp_data['id']]
                        total_hari_kerja = len([a for a in emp_attendance if a['status'] in ['Hadir', 'Terlambat', 'Pulang Awal']])
                        
                        # Calculate salary
                        if emp_data['role_karyawan'] in ['Kasir', 'Supervisor']:
                            # Gaji tetap
                            total_gaji = emp_data['gaji_tetap']
                        else:
                            # Worker - hitung berdasarkan pendapatan
                            total_gaji = 0
                            for att in emp_attendance:
                                if att['status'] in ['Hadir', 'Terlambat', 'Pulang Awal']:
                                    salary = calculate_worker_salary(
                                        emp_data['id'],
                                        att['tanggal'],
                                        att['jam_masuk'],
                                        att['jam_pulang'],
                                        att['shift']
                                    )
                                    total_gaji += salary
                        
                        gaji_bersih = total_gaji + bonus - potongan
                        
                        # Display calculation
                        st.session_state['calculated_salary'] = {
                            'employee_id': emp_data['id'],
                            'nama': emp_data['nama'],
                            'periode_awal': periode_awal.strftime("%d-%m-%Y"),
                            'periode_akhir': periode_akhir.strftime("%d-%m-%Y"),
                            'total_hari_kerja': total_hari_kerja,
                            'total_gaji': total_gaji,
                            'bonus': bonus,
                            'potongan': potongan,
                            'gaji_bersih': gaji_bersih,
                            'catatan': catatan
                        }
                        st.rerun()
                else:
                    st.warning("⚠️ Belum ada karyawan aktif")
                    # Submit button required even when no employees
                    st.form_submit_button("🧮 Hitung Gaji", use_container_width=True, disabled=True)
        
        with col2:
            st.markdown("#### 📋 Hasil Perhitungan")
            
            if 'calculated_salary' in st.session_state:
                calc = st.session_state['calculated_salary']
                
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 10px; color: white;">
                    <h3 style="margin:0; color: white;">💼 {calc['nama']}</h3>
                    <p style="margin:5px 0;">Periode: {calc['periode_awal']} s/d {calc['periode_akhir']}</p>
                    <p style="margin:5px 0;">Hari Kerja: {calc['total_hari_kerja']} hari</p>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    st.metric("💵 Total Gaji", f"Rp {calc['total_gaji']:,.0f}")
                    st.metric("🎁 Bonus", f"Rp {calc['bonus']:,.0f}")
                with col_r2:
                    st.metric("✂️ Potongan", f"Rp {calc['potongan']:,.0f}")
                    st.metric("💰 Gaji Bersih", f"Rp {calc['gaji_bersih']:,.0f}", delta=None)
                
                if calc['catatan']:
                    st.info(f"📝 Catatan: {calc['catatan']}")
                
                st.markdown("---")
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("💾 Simpan ke Payroll", use_container_width=True, type="primary"):
                        add_payroll(
                            calc['employee_id'],
                            calc['periode_awal'],
                            calc['periode_akhir'],
                            calc['total_hari_kerja'],
                            calc['total_gaji'],
                            calc['bonus'],
                            calc['potongan'],
                            calc['gaji_bersih'],
                            'Pending',
                            None,
                            calc['catatan'],
                            st.session_state.get('login_user')
                        )
                        add_audit("add_payroll", f"Payroll: {calc['nama']} - Rp {calc['gaji_bersih']:,.0f}")
                        st.success("✅ Payroll berhasil disimpan!")
                        del st.session_state['calculated_salary']
                        st.rerun()
                
                with col_btn2:
                    if st.button("🔄 Hitung Ulang", use_container_width=True):
                        del st.session_state['calculated_salary']
                        st.rerun()
            else:
                st.info("💡 Silakan hitung gaji terlebih dahulu")
    
    with tab4:
        st.markdown("### 📊 Riwayat Pembayaran Gaji")
        
        # Filter
        col_f1, col_f2 = st.columns([2, 1])
        with col_f1:
            employees = get_all_employees()
            emp_filter_options = ["Semua Karyawan"] + [f"{e['id']} - {e['nama']}" for e in employees]
            selected_filter = st.selectbox("Filter Karyawan", emp_filter_options)
        
        with col_f2:
            status_filter = st.selectbox("Status", ["Semua", "Pending", "Dibayar"])
        
        # Get payroll data
        if selected_filter == "Semua Karyawan":
            payroll_data = get_payroll_history()
        else:
            emp_id = int(selected_filter.split(" - ")[0])
            payroll_data = get_payroll_history(emp_id)
        
        # Filter by status
        if status_filter != "Semua":
            payroll_data = [p for p in payroll_data if p['status'] == status_filter]
        
        if payroll_data:
            # Summary cards
            col_sum1, col_sum2, col_sum3, col_sum4 = st.columns(4)
            
            total_pending = sum(p['gaji_bersih'] for p in payroll_data if p['status'] == 'Pending')
            total_dibayar = sum(p['gaji_bersih'] for p in payroll_data if p['status'] == 'Dibayar')
            
            with col_sum1:
                st.metric("📋 Total Record", len(payroll_data))
            with col_sum2:
                pending_count = len([p for p in payroll_data if p['status'] == 'Pending'])
                st.metric("⏳ Pending", pending_count)
            with col_sum3:
                st.metric("💰 Total Pending", f"Rp {total_pending:,.0f}")
            with col_sum4:
                st.metric("✅ Total Dibayar", f"Rp {total_dibayar:,.0f}")
            
            st.markdown("---")
            
            # Display payroll table
            for idx, p in enumerate(payroll_data):
                with st.expander(f"💼 {p['nama']} - {p['periode_awal']} s/d {p['periode_akhir']} | Rp {p['gaji_bersih']:,.0f} | {p['status']}"):
                    col_p1, col_p2, col_p3 = st.columns([2, 2, 1])
                    
                    with col_p1:
                        st.write(f"**Nama:** {p['nama']}")
                        st.write(f"**Role:** {p['role_karyawan']}")
                        st.write(f"**Periode:** {p['periode_awal']} - {p['periode_akhir']}")
                        st.write(f"**Hari Kerja:** {p['total_hari_kerja']} hari")
                    
                    with col_p2:
                        st.write(f"**Total Gaji:** Rp {p['total_gaji']:,.0f}")
                        st.write(f"**Bonus:** Rp {p['bonus']:,.0f}")
                        st.write(f"**Potongan:** Rp {p['potongan']:,.0f}")
                        st.write(f"**Gaji Bersih:** Rp {p['gaji_bersih']:,.0f}")
                    
                    with col_p3:
                        st.write(f"**Status:** {p['status']}")
                        if p['tanggal_bayar']:
                            st.write(f"**Tgl Bayar:** {p['tanggal_bayar']}")
                        st.write(f"**Dibuat:** {p['created_at']}")
                    
                    if p['catatan']:
                        st.info(f"📝 {p['catatan']}")
                    
                    # Action buttons
                    if p['status'] == 'Pending':
                        if st.button(f"✅ Tandai Sudah Dibayar", key=f"pay_{p['id']}", use_container_width=True):
                            tanggal_bayar = datetime.now(WIB).strftime("%d-%m-%Y %H:%M:%S")
                            update_payroll_status(p['id'], 'Dibayar', tanggal_bayar)
                            add_audit("update_payroll", f"Pembayaran gaji: {p['nama']} - Rp {p['gaji_bersih']:,.0f}")
                            st.success(f"✅ Gaji {p['nama']} sudah ditandai dibayar!")
                            st.rerun()
        else:
            st.info("📭 Belum ada data payroll")
    
    with tab5:
        st.markdown("### 💸 Manajemen Kas Bon / Hutang Karyawan")
        
        col_kasbon1, col_kasbon2 = st.columns([2, 1])
        
        with col_kasbon1:
            st.markdown("#### 📋 Daftar Kas Bon")
            
            # Filter
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                employees = get_all_employees()
                emp_options = ["Semua Karyawan"] + [f"{e['id']} - {e['nama']}" for e in employees]
                filter_emp = st.selectbox("Filter Karyawan", emp_options, key="kasbon_filter_emp")
            with col_f2:
                filter_status = st.selectbox("Status", ["Semua", "Belum Lunas", "Lunas"], key="kasbon_filter_status")
            
            # Get kas bon data
            if filter_emp == "Semua Karyawan":
                if filter_status == "Semua":
                    kas_bon_list = get_all_kas_bon()
                else:
                    kas_bon_list = get_all_kas_bon(filter_status)
            else:
                emp_id = int(filter_emp.split(" - ")[0])
                if filter_status == "Semua":
                    kas_bon_list = get_kas_bon_by_employee(emp_id)
                else:
                    kas_bon_list = get_kas_bon_by_employee(emp_id, filter_status)
            
            if kas_bon_list:
                # Summary
                total_hutang = sum(kb['sisa_hutang'] for kb in kas_bon_list if kb['status'] == 'Belum Lunas')
                total_lunas = sum(kb['jumlah'] for kb in kas_bon_list if kb['status'] == 'Lunas')
                
                col_s1, col_s2, col_s3 = st.columns(3)
                with col_s1:
                    st.metric("📝 Total Record", len(kas_bon_list))
                with col_s2:
                    st.metric("💸 Total Hutang Aktif", f"Rp {total_hutang:,.0f}")
                with col_s3:
                    st.metric("✅ Total Lunas", f"Rp {total_lunas:,.0f}")
                
                st.markdown("---")
                
                # Display kas bon list
                for kb in kas_bon_list:
                    status_icon = "⏳" if kb['status'] == 'Belum Lunas' else "✅"
                    with st.expander(f"{status_icon} {kb['nama']} - Rp {kb['jumlah']:,.0f} | Sisa: Rp {kb['sisa_hutang']:,.0f} | {kb['tanggal']}"):
                        col_kb1, col_kb2 = st.columns([2, 1])
                        
                        with col_kb1:
                            st.write(f"**Nama:** {kb['nama']}")
                            st.write(f"**Role:** {kb['role_karyawan']}")
                            st.write(f"**Tanggal Pinjam:** {kb['tanggal']}")
                            st.write(f"**Jumlah Pinjam:** Rp {kb['jumlah']:,.0f}")
                            st.write(f"**Sisa Hutang:** Rp {kb['sisa_hutang']:,.0f}")
                            st.write(f"**Status:** {kb['status']}")
                            if kb['keterangan']:
                                st.info(f"📝 {kb['keterangan']}")
                        
                        with col_kb2:
                            # Riwayat pembayaran
                            pembayaran_list = get_pembayaran_kas_bon(kb['id'])
                            if pembayaran_list:
                                st.markdown("**💰 Riwayat Bayar:**")
                                for p in pembayaran_list:
                                    st.write(f"- {p['tanggal_bayar']}: Rp {p['jumlah_bayar']:,.0f}")
                            
                            # Bayar cicilan
                            if kb['status'] == 'Belum Lunas':
                                st.markdown("---")
                                with st.form(f"bayar_kasbon_{kb['id']}"):
                                    st.markdown("**Bayar Cicilan**")
                                    max_bayar = kb['sisa_hutang']
                                    jumlah_bayar = st.number_input(
                                        "Jumlah Bayar (Rp)",
                                        min_value=0,
                                        max_value=max_bayar,
                                        step=10000,
                                        value=min(50000, max_bayar),
                                        key=f"jumlah_bayar_{kb['id']}"
                                    )
                                    metode = st.selectbox("Metode", ["Potong Gaji", "Tunai", "Transfer"], key=f"metode_{kb['id']}")
                                    ket_bayar = st.text_input("Keterangan", key=f"ket_bayar_{kb['id']}")
                                    
                                    submit_bayar = st.form_submit_button("💰 Bayar", use_container_width=True)
                                    
                                    if submit_bayar and jumlah_bayar > 0:
                                        tanggal_bayar = datetime.now(WIB).strftime("%d-%m-%Y")
                                        success = add_pembayaran_kas_bon(
                                            kb['id'], None, tanggal_bayar, jumlah_bayar,
                                            metode, ket_bayar, st.session_state.get('login_user')
                                        )
                                        if success:
                                            add_audit("bayar_kasbon", f"Pembayaran kas bon {kb['nama']}: Rp {jumlah_bayar:,.0f}")
                                            st.success("✅ Pembayaran berhasil dicatat!")
                                            st.rerun()
                                        else:
                                            st.error("❌ Pembayaran gagal!")
                        
                        # Delete button (only for admin)
                        if role == "Admin":
                            if st.button(f"🗑️ Hapus", key=f"del_kasbon_{kb['id']}", use_container_width=True):
                                if delete_kas_bon(kb['id']):
                                    add_audit("delete_kasbon", f"Hapus kas bon {kb['nama']}")
                                    st.success("✅ Kas bon berhasil dihapus!")
                                    st.rerun()
                                else:
                                    st.error("❌ Gagal menghapus kas bon!")
            else:
                st.info("📭 Belum ada data kas bon")
        
        with col_kasbon2:
            st.markdown("#### ➕ Tambah Kas Bon Baru")
            
            with st.form("add_kasbon_form"):
                employees = get_all_employees()
                if employees:
                    emp_options = {f"{e['id']} - {e['nama']}": e for e in employees}
                    selected_emp = st.selectbox("Pilih Karyawan*", list(emp_options.keys()), key="kasbon_emp")
                    emp_data = emp_options[selected_emp]
                    
                    # Show total hutang saat ini
                    total_hutang_now = get_total_hutang_by_employee(emp_data['id'])
                    if total_hutang_now > 0:
                        st.warning(f"⚠️ Total hutang saat ini: Rp {total_hutang_now:,.0f}")
                    
                    tanggal_pinjam = st.date_input("Tanggal Pinjam*", value=datetime.now(WIB), key="kasbon_tgl")
                    jumlah_pinjam = st.number_input("Jumlah Pinjam (Rp)*", min_value=0, step=10000, value=100000, key="kasbon_jumlah")
                    keterangan_pinjam = st.text_area("Keterangan", placeholder="Contoh: Keperluan mendesak", key="kasbon_ket")
                    
                    submit_kasbon = st.form_submit_button("💾 Simpan Kas Bon", use_container_width=True)
                    
                    if submit_kasbon:
                        if jumlah_pinjam > 0:
                            add_kas_bon(
                                emp_data['id'],
                                tanggal_pinjam.strftime("%d-%m-%Y"),
                                jumlah_pinjam,
                                keterangan_pinjam,
                                st.session_state.get('login_user')
                            )
                            add_audit("add_kasbon", f"Kas bon baru: {emp_data['nama']} - Rp {jumlah_pinjam:,.0f}")
                            st.success("✅ Kas bon berhasil ditambahkan!")
                            st.rerun()
                        else:
                            st.error("❌ Jumlah pinjam harus lebih dari 0!")
                else:
                    st.warning("⚠️ Belum ada data karyawan")
                    st.form_submit_button("💾 Simpan Kas Bon", use_container_width=True, disabled=True)
            
            st.markdown("---")
            st.markdown("### 📖 Panduan Kas Bon")
            st.markdown("""
            **Cara Kerja:**
            1. Input kas bon/pinjaman karyawan
            2. Sistem mencatat hutang
            3. Bayar cicilan manual atau otomatis potong gaji
            4. Status otomatis berubah jadi "Lunas" saat lunas
            
            **Fitur:**
            - ✅ Tracking hutang per karyawan
            - ✅ Riwayat pembayaran
            - ✅ Multiple payment methods
            - ✅ Auto potong gaji (manual input)
            
            **Tips:**
            - Gunakan "Potong Gaji" saat membayar dari gaji karyawan
            - Total hutang otomatis ter-update setiap pembayaran
            - Admin dapat hapus record kas bon
            """)
    
    with tab6:
        st.markdown("### ⚙️ Setting Shift & Persentase Gaji")
        
        shifts = get_shift_settings()
        
        if shifts:
            col1, col2 = st.columns(2)
            
            for idx, shift in enumerate(shifts):
                with col1 if idx == 0 else col2:
                    st.markdown(f"#### {shift['shift_name']}")
                    
                    with st.form(f"shift_form_{shift['id']}"):
                        jam_mulai = st.time_input(
                            "Jam Mulai",
                            value=datetime.strptime(shift['jam_mulai'], "%H:%M").time(),
                            key=f"start_{shift['id']}"
                        )
                        jam_selesai = st.time_input(
                            "Jam Selesai",
                            value=datetime.strptime(shift['jam_selesai'], "%H:%M").time(),
                            key=f"end_{shift['id']}"
                        )
                        persentase = st.slider(
                            "Persentase Gaji (%)",
                            min_value=10.0,
                            max_value=60.0,
                            value=shift['persentase_gaji'],
                            step=0.5,
                            key=f"pct_{shift['id']}"
                        )
                        
                        st.info(f"💡 Worker shift {shift['shift_name']} akan mendapat **{persentase}%** dari total pendapatan cuci mobil selama periode kerja mereka.")
                        
                        # Example calculation
                        example_revenue = 1000000
                        example_salary = int(example_revenue * persentase / 100)
                        st.success(f"📊 Contoh: Pendapatan Rp {example_revenue:,.0f} → Gaji Rp {example_salary:,.0f}")
                        
                        submit_shift = st.form_submit_button("💾 Update Setting", use_container_width=True)
                        
                        if submit_shift:
                            update_shift_settings(
                                shift['shift_name'],
                                jam_mulai.strftime("%H:%M"),
                                jam_selesai.strftime("%H:%M"),
                                persentase
                            )
                            add_audit("update_shift", f"Update shift {shift['shift_name']}: {persentase}%")
                            st.success(f"✅ Setting shift {shift['shift_name']} berhasil diupdate!")
                            st.rerun()
        
        st.markdown("---")
        st.markdown("### 📖 Panduan Sistem Payroll")
        
        st.markdown("""
        #### 💡 Cara Kerja Sistem:
        
        **1. Karyawan dengan Gaji Tetap (Kasir & Supervisor):**
        - Gaji dihitung per minggu dengan nominal tetap
        - Tidak terpengaruh pendapatan harian
        
        **2. Worker Cuci Mobil:**
        - Gaji dihitung dari persentase pendapatan cuci mobil
        - Shift Pagi (8:00-17:00): 35% dari total pendapatan
        - Shift Malam (17:00-08:00): 45% dari total pendapatan
        - Gaji dihitung berdasarkan jam kerja aktual
        
        **3. Presensi:**
        - Kasir input jam masuk dan pulang karyawan
        - Jika pulang lebih awal, gaji hanya dihitung sampai jam pulang
        - Jika terlambat, gaji dihitung dari jam masuk aktual
        
        **4. Perhitungan Gaji Mingguan:**
        - Pilih periode (biasanya 7 hari)
        - Sistem otomatis menghitung berdasarkan presensi
        - Bisa tambah bonus atau potongan
        - Simpan ke payroll dan tandai sudah dibayar
        
        **5. Riwayat:**
        - Semua pembayaran tercatat
        - Status: Pending atau Sudah Dibayar
        - Bisa filter per karyawan
        """)

def main():
    st.set_page_config(page_title="TIME AUTOCARE - Detailing & Ceramic Coating", layout="wide", page_icon="🚗")
    
    # Initialize database di awal sebelum login
    init_db()
    
    # Auto-populate data dummy jika database kosong (untuk deployment pertama kali)
    if check_database_empty():
        with st.spinner("🔄 Database kosong, sedang membuat data dummy..."):
            success, message = populate_dummy_data()
            if success:
                st.success(message)
                st.info("✨ Database siap digunakan!")
                time.sleep(2)
                st.rerun()
    
    if "is_logged_in" not in st.session_state or not st.session_state["is_logged_in"]:
        login_page()
        return
    
    role = st.session_state.get("login_role", "Kasir")
    
    # Custom sidebar styling
    st.sidebar.markdown("""
    <style>
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
    }
    .sidebar-user-info {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
    }
    .sidebar-user-info h3 {
        margin: 0 0 0.5rem 0;
        font-size: 1.1rem;
        font-weight: 600;
    }
    .sidebar-user-info p {
        margin: 0.25rem 0;
        font-size: 0.9rem;
        opacity: 0.95;
    }
    .menu-title {
        color: #2d3436;
        font-size: 0.85rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin: 1.5rem 0 0.8rem 0;
        padding-left: 0.3rem;
    }
    [data-testid="stSidebar"] .stButton > button {
        width: 100% !important;
        padding: 0.85rem 1rem !important;
        margin-bottom: 0.5rem !important;
        background: #ffffff;
        border: 2px solid #e8e8e8;
        border-radius: 10px;
        color: #2d3436;
        font-size: 0.95rem !important;
        font-weight: 500;
        transition: all 0.3s ease;
        text-align: left;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        min-height: 3rem !important;
        height: auto !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: #f8f9fa;
        border-color: #667eea;
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
    }
    [data-testid="stSidebar"] .stButton > button[kind="secondary"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        border-color: #667eea !important;
        color: white !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3) !important;
        min-height: 3rem !important;
        padding: 0.85rem 1rem !important;
    }
    [data-testid="stSidebar"] .stButton > button[kind="primary"] {
        width: 100% !important;
        padding: 0.85rem 1rem !important;
        min-height: 3rem !important;
    }
    [data-testid="stSidebar"] .logout-btn > button {
        background: #ff6b6b !important;
        border: none !important;
        color: white !important;
        font-weight: 600 !important;
        margin-top: 1.5rem !important;
        box-shadow: 0 4px 12px rgba(255, 107, 107, 0.3) !important;
    }
    [data-testid="stSidebar"] .logout-btn > button:hover {
        background: #ff5252 !important;
        box-shadow: 0 6px 20px rgba(255, 107, 107, 0.4) !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Sidebar
    st.sidebar.markdown(f"""
    <div class="sidebar-user-info">
        <h3>👤 {st.session_state.get('login_user', '-').upper()}</h3>
        <p>🎯 Role: {role}</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.markdown('<p class="menu-title">🚗 TIME AUTOCARE</p>', unsafe_allow_html=True)
    
    
    # Menu items based on role
    if role == "Admin":
        # Admin/Owner has access to everything including Financial Reports
        menu_items = [
            ("Dashboard", "📊"),
            ("Cuci Mobil", "🚗"),
            ("Kasir", "💰"),
            ("Payroll", "💼"),
            ("Customer", "👥"),
            ("Review Customer", "⭐"),
            ("Laporan", "📊"),
            ("Setting Toko", "⚙️"),
            ("Audit Trail", "📜"),
            ("User Setting", "👤")
        ]
    elif role == "Supervisor":
        # Supervisor only has access to Cuci Mobil and Dashboard
        menu_items = [
            ("Dashboard", "📊"),
            ("Cuci Mobil", "🚗")
        ]
    elif role == "Kasir":
        # Kasir has access to Dashboard (daily only), Kasir, and Payroll
        menu_items = [
            ("Dashboard", "📊"),
            ("Kasir", "💰"),
            ("Payroll", "💼")
        ]
    else:
        # Default: no access
        menu_items = []
    
    # Set default menu based on role if not set
    if "menu" not in st.session_state or st.session_state["menu"] not in [m[0] for m in menu_items]:
        if menu_items:
            st.session_state["menu"] = menu_items[0][0]
    
    for menu_name, icon in menu_items:
        button_type = "secondary" if st.session_state["menu"] == menu_name else "primary"
        if st.sidebar.button(f"{icon}  {menu_name}", key=f"menu_{menu_name}", use_container_width=True, type=button_type):
            st.session_state["menu"] = menu_name
            st.rerun()
    
    # Logout button
    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    st.sidebar.markdown('<div class="logout-btn">', unsafe_allow_html=True)
    if st.sidebar.button("🚪  Logout", key="logout_btn", use_container_width=True):
        add_audit("logout", f"Logout user {st.session_state.get('login_user','-')}")
        st.session_state.clear()
        st.rerun()
    st.sidebar.markdown('</div>', unsafe_allow_html=True)
    
    
    menu = st.session_state["menu"]

    # Access control check
    def has_access(menu_name, user_role):
        """Check if user role has access to specific menu"""
        if user_role == "Admin":
            return True  # Admin/Owner has access to everything
        elif user_role == "Supervisor":
            return menu_name in ["Dashboard", "Cuci Mobil"]
        elif user_role == "Kasir":
            return menu_name in ["Dashboard", "Kasir", "Payroll"]
        return False
    
    # Verify access before showing page
    if not has_access(menu, role):
        st.error(f"⛔ Akses Ditolak! Role '{role}' tidak memiliki akses ke menu '{menu}'.")
        st.info("Silakan hubungi administrator untuk mendapatkan akses.")
        return

    # Route to pages
    if menu == "Dashboard":
        dashboard_page(role)
    elif menu == "Cuci Mobil":
        transaksi_page(role)
    elif menu == "Kasir":
        kasir_page(role)
    elif menu == "Payroll":
        payroll_page(role)
    elif menu == "Customer":
        customer_page(role)
    elif menu == "Laporan":
        laporan_page(role)
    elif menu == "Setting Toko":
        setting_toko_page(role)
    elif menu == "Review Customer":
        review_customer_page()
    elif menu == "User Setting":
        user_setting_page()
    elif menu == "Audit Trail":
        audit_trail_page()

if __name__ == "__main__":
    main()
