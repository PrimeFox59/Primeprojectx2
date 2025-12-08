import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime, date
import altair as alt
import pytz
import json
import urllib.parse

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
            alamat TEXT,
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
    
    conn.commit()
    conn.close()


# --- Simpan & Load Customer ---
def save_customer(nopol, nama, telp, alamat):
    """Simpan data customer baru"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    now_wib = datetime.now(WIB)
    try:
        c.execute("""
            INSERT INTO customers (nopol, nama_customer, no_telp, alamat, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (nopol.upper(), nama, telp, alamat, now_wib.strftime("%d-%m-%Y %H:%M:%S")))
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
            'alamat': result[4],
            'created_at': result[5]
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
             checklist_datang, checklist_selesai, qc_barang, catatan, status, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['nopol'].upper(),
            data['nama_customer'],
            data['tanggal'],
            data['waktu_masuk'],
            data.get('waktu_selesai', ''),
            data['paket_cuci'],
            data['harga'],
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
        c.execute("""
            INSERT INTO kasir_transactions 
            (nopol, nama_customer, no_telp, tanggal, waktu, wash_trans_id, paket_cuci, harga_cuci,
             coffee_items, harga_coffee, total_bayar, status_bayar, metode_bayar, created_by, catatan)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            data.get('catatan', '')
        ))
        conn.commit()
        return True, "Transaksi kasir berhasil disimpan"
    except Exception as e:
        return False, f"Error: {str(e)}"
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



USERS = {
    "admin": {"password": "admin123", "role": "Admin"},
    "kasir": {"password": "kasir123", "role": "Kasir"},
    "supervisor": {"password": "super123", "role": "Supervisor"},
}

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
    st.set_page_config(page_title="Login TIME AUTOCARE", layout="centered")
    
    st.markdown("""
    <style>
    .login-container {
        max-width: 400px;
        margin: 0 auto;
        padding: 2rem;
        background: white;
        border-radius: 15px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.title("TIME AUTOCARE 🚗")
    st.markdown("---")
    
    username = st.text_input("👤 Username", key="login_username")
    password = st.text_input("🔒 Password", type="password", key="login_password")
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        login_btn = st.button("🔐 Login", key="login_btn", use_container_width=True)
    
    if login_btn:
        uname = username.strip().lower()
        if uname in USERS and password == USERS[uname]["password"]:
            st.session_state["is_logged_in"] = True
            st.session_state["login_user"] = uname
            st.session_state["login_role"] = USERS[uname]["role"]
            add_audit("login", f"Login sebagai {USERS[uname]['role']}")
            st.success(f"✅ Login berhasil sebagai {USERS[uname]['role']}")
            st.rerun()
        else:
            st.error("❌ Username atau password salah.")
    
    st.markdown("---")
    st.info("💡 **Demo Account:**\n- admin / admin123\n- kasir / kasir123\n- supervisor / super123")


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
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        date_filter = st.date_input("📅 Filter Periode", value=(today, today))
    with col2:
        if st.button("📊 Hari Ini", use_container_width=True):
            date_filter = (today, today)
            st.rerun()
    with col3:
        if st.button("📅 Bulan Ini", use_container_width=True):
            first_day = today.replace(day=1)
            date_filter = (first_day, today)
            st.rerun()
    
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
    
    # Hitung statistik coffee shop (yang tidak melalui kasir gabungan)
    total_transaksi_coffee = len(df_coffee_filtered)
    total_pendapatan_coffee = df_coffee_filtered['total'].sum() if not df_coffee_filtered.empty else 0
    
    # Hitung statistik kasir (transaksi gabungan)
    total_transaksi_kasir = len(df_kasir_filtered)
    total_pendapatan_kasir = df_kasir_filtered['total_bayar'].sum() if not df_kasir_filtered.empty else 0
    pendapatan_kasir_wash = df_kasir_filtered['harga_cuci'].sum() if not df_kasir_filtered.empty else 0
    pendapatan_kasir_coffee = df_kasir_filtered['harga_coffee'].sum() if not df_kasir_filtered.empty else 0
    
    # Total keseluruhan (hitung semua pendapatan)
    # Note: cuci mobil yang sudah masuk kasir tidak dihitung lagi di total_pendapatan_wash
    total_pendapatan_gabungan = total_pendapatan_kasir + total_pendapatan_coffee
    total_transaksi_gabungan = total_transaksi_kasir + total_transaksi_coffee
    total_customer = len(df_cust)
    
    # Cards
    st.markdown(f'''
    <div class="card-container">
        <div class="card card-1">
            <div class="card-icon">�</div>
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
    
    # Hitung jumlah transaksi dalam proses untuk badge
    df_check = get_all_transactions()
    jumlah_proses = len(df_check[df_check['status'] == 'Dalam Proses'])
    jumlah_selesai = len(df_check[df_check['status'] == 'Selesai'])
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "📝 Transaksi Baru", 
        f"✅ Selesaikan Transaksi ({jumlah_proses})",
        f"📚 History Customer ({jumlah_selesai})",
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
                alamat_cust = customer_data['alamat']
                
                with st.expander("👁️ Lihat Detail Customer", expanded=False):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.write(f"**📞 Telepon:**")
                        st.info(f"{telp_cust}")
                    with col_b:
                        st.write(f"**📍 Alamat:**")
                        st.info(f"{alamat_cust}")
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
                col_tel, col_addr = st.columns(2)
                with col_tel:
                    telp_cust = st.text_input("No. Telepon", key="trans_telp", 
                                             placeholder="08xxxxxxxxxx")
                with col_addr:
                    alamat_cust = st.text_input("Alamat", key="trans_alamat", 
                                               placeholder="Alamat customer")
        
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
        with col_harga:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); color: white; padding: 0.8rem; border-radius: 10px; text-align: center; font-size: 1.2rem; font-weight: 800; box-shadow: 0 3px 10px rgba(67, 233, 123, 0.3); margin-top: 1.7rem;">
                💰 Rp {harga:,.0f}
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
                if st.checkbox(item, key=f"check_{idx}", value=True):
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
                    success, msg = save_customer(nopol_input, nama_cust, telp_cust or "", alamat_cust or "")
                    if not success and "sudah terdaftar" not in msg.lower():
                        st.error(f"❌ Gagal menyimpan customer: {msg}")
                        st.stop()
                
                # Gunakan waktu sistem otomatis
                now_wib = datetime.now(WIB)
                tanggal_str = now_wib.strftime('%d-%m-%Y')
                waktu_str = now_wib.strftime('%H:%M:%S')
                
                # Simpan transaksi
                trans_data = {
                    'nopol': nopol_input,
                    'nama_customer': nama_cust,
                    'tanggal': tanggal_str,
                    'waktu_masuk': waktu_str,
                    'waktu_selesai': '',
                    'paket_cuci': paket,
                    'harga': harga,
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
                st.stop()
            elif len(selected_rows) > 1:
                st.warning("⚠️ Silakan pilih hanya satu transaksi untuk diselesaikan")
                st.stop()
            
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
                st.stop()
            
            
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
                        st.stop()
                    
                    current_status = matching_trans['status'].iloc[0].strip()
                    
                    if current_status != 'Dalam Proses':
                        st.error(f"❌ Transaksi ini sudah berstatus '{current_status}'. Halaman akan di-refresh.")
                        import time
                        time.sleep(2)
                        st.rerun()
                        st.stop()
                    
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
        st.subheader("⚙️ Setting Paket Cuci & Checklist")
        
        # Check role
        if role not in ["Admin", "Supervisor"]:
            st.warning("⚠️ Hanya Admin dan Supervisor yang dapat mengakses setting ini")
            return
        
        subtab1, subtab2, subtab3 = st.tabs(["📦 Paket Cuci", "✅ Checklist Datang", "✓ Checklist Selesai"])
        
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
        
        with subtab3:
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
        "☕️ Coffee Only",
        f"📜 History Kasir ({jumlah_history_kasir})",
        f"📜 History Coffee ({jumlah_history_coffee})",
        "⚙️ Setting Menu"
    ])
    
    with tab1:
        st.subheader("💰 Transaksi Kasir - Pembayaran")
        st.info("💡 **Alur:** SPV input data cuci mobil → Data masuk ke Kasir → Customer bayar di sini")
        
        # Tampilkan daftar mobil yang pending pembayaran
        if not df_pending.empty:
            st.markdown("---")
            st.markdown("### 🚗 Mobil Pending Pembayaran")
            st.warning(f"⚠️ Ada **{len(df_pending)}** transaksi cuci mobil yang menunggu pembayaran")
            
            for idx, row in df_pending.iterrows():
                with st.expander(f"🚗 {row['nopol']} - {row['nama_customer']} | {row['paket_cuci']} | Rp {row['harga']:,.0f}", expanded=False):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Nopol:** {row['nopol']}")
                        st.write(f"**Nama:** {row['nama_customer']}")
                        st.write(f"**Paket:** {row['paket_cuci']}")
                        st.write(f"**Tanggal:** {row['tanggal']}")
                    with col2:
                        st.write(f"**Waktu Masuk:** {row['waktu_masuk']}")
                        st.write(f"**Status:** {row['status']}")
                        st.write(f"**Harga Cuci:** Rp {row['harga']:,.0f}")
                        st.write(f"**SPV:** {row.get('created_by', '-')}")
                    
                    if st.button(f"✅ Proses Pembayaran", key=f"pay_{row['id']}", type="primary"):
                        st.session_state[f'selected_wash_{row["id"]}'] = True
                        st.rerun()
        
        st.markdown("---")
        
        # Form pembayaran
        st.markdown("### 💳 Form Pembayaran")
        
        # Pilih transaksi cuci mobil (jika ada)
        wash_trans_selected = None
        if not df_pending.empty:
            st.markdown("##### 🚗 Transaksi Cuci Mobil")
            
            # Cek apakah ada yang dipilih dari tombol di atas
            selected_id = None
            for key in st.session_state.keys():
                if key.startswith('selected_wash_') and st.session_state[key]:
                    selected_id = int(key.replace('selected_wash_', ''))
                    break
            
            wash_options = ["Tidak ada"] + [f"{row['nopol']} - {row['nama_customer']} - {row['paket_cuci']} (Rp {row['harga']:,.0f})" for _, row in df_pending.iterrows()]
            
            # Set default index jika ada yang dipilih
            default_idx = 0
            if selected_id:
                for i, (_, row) in enumerate(df_pending.iterrows(), 1):
                    if row['id'] == selected_id:
                        default_idx = i
                        break
            
            wash_choice = st.selectbox("Pilih Transaksi Cuci Mobil", wash_options, index=default_idx, key="wash_select")
            
            if wash_choice != "Tidak ada":
                wash_idx = wash_options.index(wash_choice) - 1
                wash_trans_selected = df_pending.iloc[wash_idx]
        
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
        
        # Metode pembayaran dan catatan
        col1, col2 = st.columns(2)
        with col1:
            metode_bayar = st.selectbox("Metode Pembayaran", ["Tunai", "Transfer", "QRIS", "Kartu Debit/Kredit"], key="metode_bayar")
        with col2:
            status_bayar = st.selectbox("Status Pembayaran", ["Lunas", "DP", "Belum Bayar"], key="status_bayar")
        
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
                    'coffee_items': json.dumps([{'name': k, 'price': v['price'], 'qty': v['qty']} for k, v in coffee_order.items()], ensure_ascii=False) if coffee_order else '',
                    'harga_coffee': harga_coffee,
                    'total_bayar': total_bayar,
                    'status_bayar': status_bayar,
                    'metode_bayar': metode_bayar,
                    'created_by': st.session_state.get('login_user', ''),
                    'catatan': catatan_kasir
                }
                
                success, msg = save_kasir_transaction(kasir_data)
                
                if success:
                    st.success("✅ " + msg)
                    add_audit('kasir_transaction', f"Transaksi kasir {nopol_input} - Total: Rp {total_bayar:,.0f}")
                    
                    # Generate WhatsApp invoice if phone number is provided
                    if telp_input:
                        toko_info = get_toko_info()
                        invoice_text = generate_kasir_invoice(kasir_data, toko_info)
                        whatsapp_link = create_whatsapp_link(telp_input, invoice_text)
                        
                        st.markdown("---")
                        st.markdown("### 📱 Invoice WhatsApp")
                        st.success(f"✅ Transaksi berhasil! Kirim invoice ke **{nama_input}**")
                        st.link_button("💬 Kirim Invoice via WhatsApp", whatsapp_link, use_container_width=True)
                        
                        with st.expander("👁️ Preview Invoice"):
                            st.text(invoice_text)
                        
                        # Clear selected state
                        for key in list(st.session_state.keys()):
                            if key.startswith('selected_wash_'):
                                del st.session_state[key]
                    else:
                        st.rerun()
                else:
                    st.error("❌ " + msg)
    
    with tab2:
        st.subheader('☕️ Penjualan Coffee Only')
        st.info("💡 Untuk penjualan coffee/snack tanpa transaksi cuci mobil")
        
        menu = get_coffee_menu()
        if not menu:
            st.info("Belum ada menu coffee. Silakan hubungi Admin untuk menambahkan menu.")
            return

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
        st.subheader('📜 History Penjualan Coffee Only')
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
    
    tab1, tab2 = st.tabs(["📋 Daftar Customer", "➕ Tambah Customer Baru"])
    
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
                df_show = df_display[['nopol', 'nama_customer', 'no_telp', 'alamat', 'created_at']].copy()
                df_show.columns = ['🔖 Nopol', '👤 Nama', '📞 Telepon', '📍 Alamat', '📅 Terdaftar']
                
                st.dataframe(
                    df_show,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "🔖 Nopol": st.column_config.TextColumn(width="small"),
                        "👤 Nama": st.column_config.TextColumn(width="medium"),
                        "📞 Telepon": st.column_config.TextColumn(width="small"),
                        "📍 Alamat": st.column_config.TextColumn(width="large"),
                        "📅 Terdaftar": st.column_config.TextColumn(width="small")
                    }
                )
                
                # Download CSV
                col1, col2, col3 = st.columns([2, 1, 2])
                with col2:
                    csv = df_show.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "📥 Download CSV", 
                        data=csv, 
                        file_name=f"customer_list_{datetime.now(WIB).strftime('%d%m%Y')}.csv", 
                        mime="text/csv",
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
                alamat = st.text_area("📍 Alamat", placeholder="Alamat lengkap customer", height=100)
            
            submitted = st.form_submit_button("💾 Simpan Customer", type="primary", use_container_width=True)
            
            if submitted:
                if not nopol or not nama:
                    st.error("❌ Nopol dan Nama wajib diisi")
                else:
                    success, msg = save_customer(nopol, nama, telp, alamat)
                    if success:
                        add_audit("customer_baru", f"Nopol: {nopol}, Nama: {nama}")
                        st.success(f"✅ {msg}")
                        st.balloons()
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
    tab1, tab2, tab3, tab4 = st.tabs(["🚗 Detail Cuci Mobil", "☕ Detail Coffee Shop", "📊 Perbandingan", "📈 Trend Analysis"])
    
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
    st.header("⚙️ User Setting")
    st.info("Fitur ganti password dan nama user.")
    uname = st.session_state.get("login_user", "-")
    role = st.session_state.get("login_role", "-")
    st.write(f"**Username:** {uname}")
    st.write(f"**Role:** {role}")
    
    st.markdown("---")
    
    with st.form("user_setting_form"):
        st.subheader("Ubah Informasi")
        new_name = st.text_input("Ganti Nama Tampilan", value=uname)
        new_pass = st.text_input("Ganti Password", type="password", placeholder="Kosongkan jika tidak ingin mengubah")
        confirm_pass = st.text_input("Konfirmasi Password Baru", type="password")
        
        submitted = st.form_submit_button("💾 Simpan Perubahan", type="primary", use_container_width=True)
        
        if submitted:
            changes = []
            
            if new_name and new_name != uname:
                st.session_state["login_user"] = new_name
                changes.append(f"username: {uname} → {new_name}")
            
            if new_pass:
                if new_pass != confirm_pass:
                    st.error("❌ Konfirmasi password tidak cocok!")
                    st.stop()
                elif len(new_pass) < 6:
                    st.error("❌ Password minimal 6 karakter!")
                    st.stop()
                else:
                    USERS[uname]["password"] = new_pass
                    changes.append("password diubah")
            
            if changes:
                add_audit("update_user_setting", f"User setting: {', '.join(changes)}")
                st.success("✅ Perubahan user disimpan (hanya berlaku sesi ini)")
                st.balloons()
                st.rerun()
            else:
                st.info("ℹ️ Tidak ada perubahan.")

def main():
    st.set_page_config(page_title="TIME AUTOCARE - Detailing & Ceramic Coating", layout="wide", page_icon="🚗")
    
    # Initialize database di awal sebelum login
    init_db()
    
    if "is_logged_in" not in st.session_state or not st.session_state["is_logged_in"]:
        login_page()
        return
    
    role = st.session_state.get("login_role", "Kasir")
    
    # Initialize menu state
    if "menu" not in st.session_state:
        st.session_state["menu"] = "Dashboard"
    
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
    .stButton > button {
        width: 100%;
        padding: 0.85rem 1rem;
        margin-bottom: 0.5rem;
        background: #ffffff;
        border: 2px solid #e8e8e8;
        border-radius: 10px;
        color: #2d3436;
        font-size: 0.95rem;
        font-weight: 500;
        transition: all 0.3s ease;
        text-align: left;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stButton > button:hover {
        background: #f8f9fa;
        border-color: #667eea;
        transform: translateX(4px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
    }
    .stButton > button[kind="secondary"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        border-color: #667eea !important;
        color: white !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3) !important;
    }
    .logout-btn > button {
        background: #ff6b6b !important;
        border: none !important;
        color: white !important;
        font-weight: 600 !important;
        margin-top: 1.5rem !important;
        box-shadow: 0 4px 12px rgba(255, 107, 107, 0.3) !important;
    }
    .logout-btn > button:hover {
        background: #ff5252 !important;
        transform: translateY(-2px) !important;
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
    
    
    # Menu items
    menu_items = [
        ("Dashboard", "📊"),
        ("Cuci Mobil", "🚗"),
        ("Kasir", "💰"),
        ("Customer", "👥"),
        ("Laporan", "📊"),
        ("Setting Toko", "⚙️"),
        ("Audit Trail", "📜"),
        ("User Setting", "👤")
    ]
    
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

    # Route to pages
    if menu == "Dashboard":
        dashboard_page(role)
    elif menu == "Cuci Mobil":
        transaksi_page(role)
    elif menu == "Kasir":
        kasir_page(role)
    elif menu == "Customer":
        customer_page(role)
    elif menu == "Laporan":
        laporan_page(role)
    elif menu == "Setting Toko":
        setting_toko_page(role)
    elif menu == "User Setting":
        user_setting_page()
    elif menu == "Audit Trail":
        audit_trail_page()

if __name__ == "__main__":
    main()
