"""
Script untuk mengisi database dengan data dummy yang lengkap
Termasuk: Pelanggan, Transaksi, Karyawan, Presensi, Gaji, Review, dll.
"""

import sqlite3
import random
from datetime import datetime, timedelta, date, time
import json
import pytz
import secrets

# Timezone GMT+7 (WIB)
WIB = pytz.timezone('Asia/Jakarta')

DB_NAME = "car_wash.db"

# Data dummy untuk generate
NAMA_DEPAN = [
    "Budi", "Siti", "Ahmad", "Dewi", "Rudi", "Ani", "Agus", "Sri", "Bambang", "Lina",
    "Hendra", "Maya", "Andi", "Rina", "Doni", "Sari", "Eko", "Wati", "Fajar", "Indah",
    "Joko", "Nur", "Teguh", "Putri", "Wahyu", "Ayu", "Yudi", "Lestari", "Rahmat", "Kartika"
]

NAMA_BELAKANG = [
    "Santoso", "Wijaya", "Pratama", "Kusuma", "Putra", "Putri", "Setiawan", "Wibowo",
    "Hidayat", "Nugroho", "Permana", "Saputra", "Kurniawan", "Suryanto", "Gunawan",
    "Susanto", "Prasetyo", "Haryanto", "Sutanto", "Hermawan"
]

JENIS_KENDARAAN = ["Mobil", "Motor"]

MERK_MOBIL = [
    "Toyota", "Honda", "Suzuki", "Daihatsu", "Mitsubishi", "Nissan", "Mazda", 
    "Mercedes-Benz", "BMW", "Audi", "Hyundai", "Kia"
]

MERK_MOTOR = [
    "Honda", "Yamaha", "Suzuki", "Kawasaki", "Vespa"
]

UKURAN_MOBIL = ["Kecil", "Sedang", "Besar", "Extra Besar"]

PAKET_CUCI = {
    "Cuci Reguler": 50000,
    "Cuci Premium": 75000,
    "Cuci + Wax": 100000,
    "Full Detailing": 200000,
    "Interior Only": 60000,
    "Exterior Only": 40000
}

COFFEE_MENU = {
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

CHECKLIST_DATANG = [
    "Ban lengkap dan baik",
    "Wiper berfungsi", 
    "Kaca tidak retak",
    "Body tidak penyok",
    "Lampu lengkap",
    "Spion lengkap"
]

CHECKLIST_SELESAI = [
    "Interior bersih",
    "Exterior bersih",
    "Kaca bersih",
    "Ban hitam mengkilap",
    "Dashboard bersih",
    "Tidak ada noda"
]

REVIEW_TEXTS = [
    "Sangat puas dengan pelayanan, mobil bersih dan wangi!",
    "Pelayanan cepat dan hasil memuaskan.",
    "Harga terjangkau, hasil maksimal. Recommended!",
    "Staff ramah dan profesional.",
    "Tempat bersih, hasil cucian bagus.",
    "Kualitas cucian sangat baik, akan kembali lagi.",
    "Detailing nya mantap, mobil jadi kinclong!",
    "Pelayanan oke, tapi agak lama.",
    "Hasil cucian bagus, tapi harga sedikit mahal.",
    "Overall sangat memuaskan!"
]

METODE_BAYAR = ["Tunai", "Transfer", "QRIS", "Debit"]

def generate_nopol():
    """Generate nomor polisi kendaraan random"""
    huruf = ['B', 'D', 'L', 'F', 'N', 'T', 'S', 'H', 'K', 'R']
    angka = random.randint(1000, 9999)
    huruf_akhir = random.choice(['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z'])
    huruf_akhir2 = random.choice(['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T'])
    return f"{random.choice(huruf)}{angka}{huruf_akhir}{huruf_akhir2}"

def generate_phone():
    """Generate nomor telepon random"""
    return f"08{random.randint(1, 9)}{random.randint(10000000, 99999999)}"

def generate_nama():
    """Generate nama random"""
    return f"{random.choice(NAMA_DEPAN)} {random.choice(NAMA_BELAKANG)}"

def generate_secret_code():
    """Generate unique 8-character secret code"""
    return secrets.token_urlsafe(6).upper().replace('-', 'X').replace('_', 'Y')[:8]

def format_date(date_obj):
    """Format datetime ke string dd-mm-yyyy"""
    return date_obj.strftime('%d-%m-%Y')

def format_time(time_obj):
    """Format time ke string HH:MM"""
    if isinstance(time_obj, str):
        return time_obj
    return time_obj.strftime('%H:%M')

def format_datetime(dt):
    """Format datetime ke string dd-mm-yyyy HH:MM:SS"""
    return dt.strftime('%d-%m-%Y %H:%M:%S')

def populate_customers(conn, num_customers=50):
    """Populate customers table dengan data dummy"""
    print(f"Membuat {num_customers} pelanggan dummy...")
    c = conn.cursor()
    customers = []
    
    for i in range(num_customers):
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
        
        # Tanggal registrasi dalam 6 bulan terakhir
        days_ago = random.randint(1, 180)
        created_at = datetime.now(WIB) - timedelta(days=days_ago)
        
        try:
            c.execute("""
                INSERT INTO customers (nopol, nama_customer, no_telp, jenis_kendaraan, merk_kendaraan, ukuran_mobil, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (nopol, nama, no_telp, jenis_kendaraan, merk, ukuran, format_datetime(created_at)))
            
            customers.append({
                'nopol': nopol,
                'nama': nama,
                'no_telp': no_telp,
                'jenis_kendaraan': jenis_kendaraan,
                'merk': merk,
                'ukuran': ukuran,
                'created_at': created_at
            })
        except sqlite3.IntegrityError:
            # Nopol duplikat, skip
            continue
    
    conn.commit()
    print(f"✓ {len(customers)} pelanggan berhasil ditambahkan")
    return customers

def populate_employees(conn, num_employees=8):
    """Populate employees table dengan data dummy"""
    print(f"Membuat {num_employees} karyawan dummy...")
    c = conn.cursor()
    
    roles = ["Washer", "QC Inspector", "Kasir", "Supervisor"]
    gaji_ranges = {
        "Washer": (3000000, 4000000),
        "QC Inspector": (3500000, 4500000),
        "Kasir": (3500000, 4500000),
        "Supervisor": (5000000, 6000000)
    }
    
    shifts = ["Pagi", "Malam"]
    shift_times = {
        "Pagi": ("08:00", "17:00"),
        "Malam": ("17:00", "08:00")
    }
    
    employees = []
    now = datetime.now(WIB)
    
    for i in range(num_employees):
        nama = generate_nama()
        role = random.choice(roles)
        gaji_min, gaji_max = gaji_ranges[role]
        gaji = random.randint(gaji_min // 100000, gaji_max // 100000) * 100000
        shift = random.choice(shifts)
        jam_masuk, jam_pulang = shift_times[shift]
        no_telp = generate_phone()
        
        created_at = now - timedelta(days=random.randint(30, 365))
        
        c.execute("""
            INSERT INTO employees (nama, role_karyawan, gaji_tetap, shift, jam_masuk_default, 
                                   jam_pulang_default, status, no_telp, created_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (nama, role, gaji, shift, jam_masuk, jam_pulang, "Aktif", no_telp, 
              format_datetime(created_at), "admin"))
        
        employee_id = c.lastrowid
        employees.append({
            'id': employee_id,
            'nama': nama,
            'role': role,
            'gaji': gaji,
            'shift': shift,
            'jam_masuk': jam_masuk,
            'jam_pulang': jam_pulang,
            'created_at': created_at
        })
    
    conn.commit()
    print(f"✓ {len(employees)} karyawan berhasil ditambahkan")
    return employees

def populate_attendance(conn, employees, days=60):
    """Populate attendance table dengan data presensi dummy"""
    print(f"Membuat data presensi {days} hari terakhir...")
    c = conn.cursor()
    
    attendance_records = []
    now = datetime.now(WIB)
    
    for employee in employees:
        # Generate attendance untuk 60 hari terakhir
        for day in range(days):
            tanggal = now - timedelta(days=day)
            
            # 90% hadir, 5% izin, 5% alpha
            rand = random.random()
            if rand < 0.90:
                status = "Hadir"
                
                # Jam masuk dengan sedikit variasi
                jam_masuk_base = datetime.strptime(employee['jam_masuk'], "%H:%M")
                variasi_menit = random.randint(-15, 30)
                jam_masuk = (datetime.combine(tanggal.date(), jam_masuk_base.time()) + 
                            timedelta(minutes=variasi_menit))
                
                # Jam pulang dengan sedikit variasi
                jam_pulang_base = datetime.strptime(employee['jam_pulang'], "%H:%M")
                variasi_menit = random.randint(-30, 15)
                jam_pulang = (datetime.combine(tanggal.date(), jam_pulang_base.time()) + 
                             timedelta(minutes=variasi_menit))
                
                c.execute("""
                    INSERT INTO attendance (employee_id, tanggal, jam_masuk, jam_pulang, 
                                           shift, status, catatan, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (employee['id'], format_date(tanggal), format_time(jam_masuk), 
                      format_time(jam_pulang), employee['shift'], status, "", "system"))
                
                attendance_records.append({
                    'employee_id': employee['id'],
                    'tanggal': tanggal,
                    'status': status
                })
            elif rand < 0.95:
                status = "Izin"
                c.execute("""
                    INSERT INTO attendance (employee_id, tanggal, jam_masuk, jam_pulang,
                                           shift, status, catatan, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (employee['id'], format_date(tanggal), "", "", 
                      employee['shift'], status, "Izin keluarga", "system"))
                
                attendance_records.append({
                    'employee_id': employee['id'],
                    'tanggal': tanggal,
                    'status': status
                })
            else:
                status = "Alpha"
                c.execute("""
                    INSERT INTO attendance (employee_id, tanggal, jam_masuk, jam_pulang,
                                           shift, status, catatan, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (employee['id'], format_date(tanggal), "", "", 
                      employee['shift'], status, "", "system"))
                
                attendance_records.append({
                    'employee_id': employee['id'],
                    'tanggal': tanggal,
                    'status': status
                })
    
    conn.commit()
    print(f"✓ {len(attendance_records)} record presensi berhasil ditambahkan")
    return attendance_records

def populate_payroll(conn, employees, attendance_records):
    """Populate payroll table dengan data gaji dummy"""
    print("Membuat data gaji bulanan...")
    c = conn.cursor()
    
    # Load shift settings untuk persentase
    c.execute("SELECT shift_name, persentase_gaji FROM shift_settings")
    shift_percentages = dict(c.fetchall())
    
    payroll_records = []
    now = datetime.now(WIB)
    
    # Generate payroll untuk 3 bulan terakhir
    for month_offset in range(3):
        # Tentukan periode
        if month_offset == 0:
            # Bulan ini (tanggal 1 sampai hari ini)
            periode_akhir = now
            periode_awal = datetime(now.year, now.month, 1, tzinfo=WIB)
        else:
            # Bulan sebelumnya (full month)
            target_month = now.month - month_offset
            target_year = now.year
            if target_month <= 0:
                target_month += 12
                target_year -= 1
            
            periode_awal = datetime(target_year, target_month, 1, tzinfo=WIB)
            
            # Akhir bulan
            if target_month == 12:
                next_month = 1
                next_year = target_year + 1
            else:
                next_month = target_month + 1
                next_year = target_year
            periode_akhir = datetime(next_year, next_month, 1, tzinfo=WIB) - timedelta(days=1)
        
        for employee in employees:
            # Hitung hari kerja dari attendance
            hari_kerja = sum(1 for att in attendance_records 
                           if att['employee_id'] == employee['id'] 
                           and att['status'] == 'Hadir'
                           and periode_awal <= att['tanggal'] <= periode_akhir)
            
            # Hitung gaji berdasarkan shift
            shift = employee['shift']
            persentase = shift_percentages.get(shift, 100.0) / 100.0
            
            # Total gaji = gaji tetap * persentase * (hari kerja / hari dalam periode)
            total_hari_periode = (periode_akhir - periode_awal).days + 1
            gaji_harian = employee['gaji'] * persentase / total_hari_periode
            total_gaji = int(gaji_harian * hari_kerja)
            
            # Bonus random (0-500k)
            bonus = random.randint(0, 5) * 100000
            
            # Potongan random (0-200k)
            potongan = random.randint(0, 2) * 100000
            
            gaji_bersih = total_gaji + bonus - potongan
            
            # Status: Lunas untuk bulan lalu, Pending untuk bulan ini
            if month_offset == 0:
                status = "Pending"
                tanggal_bayar = None
            else:
                status = "Lunas"
                # Tanggal bayar: tanggal 5 bulan berikutnya
                if periode_akhir.month == 12:
                    tanggal_bayar = datetime(periode_akhir.year + 1, 1, 5, tzinfo=WIB)
                else:
                    tanggal_bayar = datetime(periode_akhir.year, periode_akhir.month + 1, 5, tzinfo=WIB)
            
            c.execute("""
                INSERT INTO payroll (employee_id, periode_awal, periode_akhir, total_hari_kerja,
                                    total_gaji, bonus, potongan, gaji_bersih, status, 
                                    tanggal_bayar, catatan, created_at, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (employee['id'], format_date(periode_awal), format_date(periode_akhir), 
                  hari_kerja, total_gaji, bonus, potongan, gaji_bersih, status,
                  format_date(tanggal_bayar) if tanggal_bayar else None,
                  f"Shift {shift} - {persentase*100:.0f}% dari gaji tetap",
                  format_datetime(now), "admin"))
            
            payroll_records.append({
                'employee_id': employee['id'],
                'periode': f"{format_date(periode_awal)} - {format_date(periode_akhir)}",
                'gaji_bersih': gaji_bersih
            })
    
    conn.commit()
    print(f"✓ {len(payroll_records)} record gaji berhasil ditambahkan")
    return payroll_records

def populate_wash_transactions(conn, customers, num_transactions=200):
    """Populate wash_transactions table dengan data transaksi cuci dummy"""
    print(f"Membuat {num_transactions} transaksi cuci dummy...")
    c = conn.cursor()
    
    transactions = []
    now = datetime.now(WIB)
    
    # Load ukuran multiplier
    c.execute("SELECT setting_value FROM settings WHERE setting_key = 'ukuran_multiplier'")
    result = c.fetchone()
    if result:
        ukuran_multiplier = json.loads(result[0])
    else:
        ukuran_multiplier = {
            "Kecil": 1.0,
            "Sedang": 1.2,
            "Besar": 1.5,
            "Extra Besar": 2.0
        }
    
    for i in range(num_transactions):
        customer = random.choice(customers)
        
        # Tanggal transaksi dalam 90 hari terakhir
        days_ago = random.randint(0, 90)
        tanggal = now - timedelta(days=days_ago)
        
        # Waktu masuk (jam 8 pagi - 8 malam)
        jam_masuk = random.randint(8, 20)
        menit_masuk = random.randint(0, 59)
        waktu_masuk = f"{jam_masuk:02d}:{menit_masuk:02d}"
        
        # Waktu selesai (1-3 jam setelah masuk)
        durasi_jam = random.randint(1, 3)
        waktu_selesai_dt = datetime.combine(tanggal.date(), 
                                           datetime.strptime(waktu_masuk, "%H:%M").time()) + \
                           timedelta(hours=durasi_jam, minutes=random.randint(0, 59))
        waktu_selesai = format_time(waktu_selesai_dt)
        
        # Pilih paket
        paket = random.choice(list(PAKET_CUCI.keys()))
        harga_base = PAKET_CUCI[paket]
        
        # Hitung harga dengan multiplier ukuran
        multiplier = ukuran_multiplier.get(customer['ukuran'], 1.0)
        harga = int(harga_base * multiplier)
        
        # Checklist
        checklist_datang_items = random.sample(CHECKLIST_DATANG, random.randint(4, 6))
        checklist_selesai_items = random.sample(CHECKLIST_SELESAI, random.randint(4, 6))
        
        # Status (95% Selesai, 5% Dalam Proses untuk transaksi hari ini)
        if days_ago == 0 and random.random() < 0.05:
            status = "Dalam Proses"
            waktu_selesai = None
            checklist_selesai_items = []
        else:
            status = "Selesai"
        
        c.execute("""
            INSERT INTO wash_transactions (nopol, nama_customer, tanggal, waktu_masuk, waktu_selesai,
                                          paket_cuci, harga, jenis_kendaraan, merk_kendaraan, ukuran_mobil,
                                          checklist_datang, checklist_selesai, qc_barang, catatan, 
                                          status, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (customer['nopol'], customer['nama'], format_date(tanggal), waktu_masuk, waktu_selesai,
              paket, harga, customer['jenis_kendaraan'], customer['merk'], customer['ukuran'],
              json.dumps(checklist_datang_items), json.dumps(checklist_selesai_items),
              "OK", "", status, "admin"))
        
        trans_id = c.lastrowid
        transactions.append({
            'id': trans_id,
            'nopol': customer['nopol'],
            'nama': customer['nama'],
            'no_telp': customer['no_telp'],
            'tanggal': tanggal,
            'waktu_masuk': waktu_masuk,
            'paket': paket,
            'harga': harga,
            'status': status
        })
    
    conn.commit()
    print(f"✓ {len(transactions)} transaksi cuci berhasil ditambahkan")
    return transactions

def populate_coffee_sales(conn, num_sales=150):
    """Populate coffee_sales table dengan data penjualan kopi/snack dummy"""
    print(f"Membuat {num_sales} transaksi coffee/snack dummy...")
    c = conn.cursor()
    
    sales = []
    now = datetime.now(WIB)
    
    for i in range(num_sales):
        # Tanggal dalam 90 hari terakhir
        days_ago = random.randint(0, 90)
        tanggal = now - timedelta(days=days_ago)
        
        # Waktu (jam 8 pagi - 8 malam)
        jam = random.randint(8, 20)
        menit = random.randint(0, 59)
        waktu = f"{jam:02d}:{menit:02d}"
        
        # Pilih 1-3 item
        num_items = random.randint(1, 3)
        items = []
        total = 0
        
        for _ in range(num_items):
            item_name = random.choice(list(COFFEE_MENU.keys()))
            qty = random.randint(1, 2)
            price = COFFEE_MENU[item_name]
            subtotal = price * qty
            total += subtotal
            
            items.append({
                'nama': item_name,
                'harga': price,
                'qty': qty,
                'subtotal': subtotal
            })
        
        # 30% chance ada nama customer
        if random.random() < 0.3:
            nama_customer = generate_nama()
            no_telp = generate_phone()
        else:
            nama_customer = None
            no_telp = None
        
        c.execute("""
            INSERT INTO coffee_sales (items, total, tanggal, waktu, nama_customer, no_telp, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (json.dumps(items), total, format_date(tanggal), waktu, 
              nama_customer, no_telp, "kasir"))
        
        sales.append({
            'tanggal': tanggal,
            'total': total
        })
    
    conn.commit()
    print(f"✓ {len(sales)} transaksi coffee/snack berhasil ditambahkan")
    return sales

def populate_kasir_transactions(conn, wash_transactions, coffee_sales_count):
    """Populate kasir_transactions table dengan data transaksi kasir dummy"""
    print(f"Membuat transaksi kasir dari transaksi cuci...")
    c = conn.cursor()
    
    kasir_trans = []
    
    # Untuk setiap wash transaction yang sudah selesai, buat kasir transaction
    for wash_trans in wash_transactions:
        if wash_trans['status'] == 'Selesai':
            # 40% chance juga beli coffee/snack
            has_coffee = random.random() < 0.4
            
            if has_coffee:
                # Generate coffee items
                num_items = random.randint(1, 2)
                coffee_items = []
                harga_coffee = 0
                
                for _ in range(num_items):
                    item_name = random.choice(list(COFFEE_MENU.keys()))
                    qty = random.randint(1, 2)
                    price = COFFEE_MENU[item_name]
                    subtotal = price * qty
                    harga_coffee += subtotal
                    
                    coffee_items.append({
                        'nama': item_name,
                        'harga': price,
                        'qty': qty,
                        'subtotal': subtotal
                    })
            else:
                coffee_items = []
                harga_coffee = 0
            
            total_bayar = wash_trans['harga'] + harga_coffee
            
            # Generate secret code
            secret_code = generate_secret_code()
            
            # Metode bayar
            metode_bayar = random.choice(METODE_BAYAR)
            
            c.execute("""
                INSERT INTO kasir_transactions (nopol, nama_customer, no_telp, tanggal, waktu,
                                               wash_trans_id, paket_cuci, harga_cuci, 
                                               coffee_items, harga_coffee, total_bayar, 
                                               status_bayar, metode_bayar, secret_code, 
                                               created_by, catatan)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (wash_trans['nopol'], wash_trans['nama'], wash_trans['no_telp'],
                  format_date(wash_trans['tanggal']), wash_trans['waktu_masuk'],
                  wash_trans['id'], wash_trans['paket'], wash_trans['harga'],
                  json.dumps(coffee_items) if coffee_items else None, harga_coffee,
                  total_bayar, "Lunas", metode_bayar, secret_code, "kasir", ""))
            
            kasir_id = c.lastrowid
            kasir_trans.append({
                'id': kasir_id,
                'secret_code': secret_code,
                'nopol': wash_trans['nopol'],
                'no_telp': wash_trans['no_telp'],
                'nama': wash_trans['nama'],
                'tanggal': wash_trans['tanggal'],
                'total_bayar': total_bayar
            })
    
    conn.commit()
    print(f"✓ {len(kasir_trans)} transaksi kasir berhasil ditambahkan")
    return kasir_trans

def populate_customer_reviews(conn, kasir_transactions):
    """Populate customer_reviews table dengan data review dummy"""
    print(f"Membuat review pelanggan...")
    c = conn.cursor()
    
    reviews = []
    
    # 60% dari kasir transactions dapat review
    trans_with_review = random.sample(kasir_transactions, 
                                     int(len(kasir_transactions) * 0.6))
    
    for trans in trans_with_review:
        # Rating 3-5 (mostly 4-5)
        rating = random.choices([3, 4, 5], weights=[10, 40, 50])[0]
        
        # Review text
        review_text = random.choice(REVIEW_TEXTS)
        
        # Reward points (10-50 based on rating)
        reward_points = rating * 10
        
        # Review date: 0-3 hari setelah transaksi
        review_date = trans['tanggal'] + timedelta(days=random.randint(0, 3))
        review_time = f"{random.randint(8, 20):02d}:{random.randint(0, 59):02d}"
        
        c.execute("""
            INSERT INTO customer_reviews (secret_code, trans_id, trans_type, nopol, no_telp,
                                         nama_customer, rating, review_text, review_date, 
                                         review_time, reward_points)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (trans['secret_code'], trans['id'], "kasir", trans['nopol'], trans['no_telp'],
              trans['nama'], rating, review_text, format_date(review_date), 
              review_time, reward_points))
        
        reviews.append({
            'trans_id': trans['id'],
            'rating': rating,
            'points': reward_points
        })
        
        # Update customer_points
        c.execute("""
            INSERT INTO customer_points (nopol, no_telp, nama_customer, total_points, last_updated)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(nopol, no_telp) DO UPDATE SET 
                total_points = total_points + ?,
                last_updated = ?
        """, (trans['nopol'], trans['no_telp'], trans['nama'], reward_points,
              format_datetime(review_date), reward_points, format_datetime(review_date)))
    
    conn.commit()
    print(f"✓ {len(reviews)} review pelanggan berhasil ditambahkan")
    return reviews

def populate_audit_trail(conn):
    """Populate audit_trail dengan beberapa entry dummy"""
    print("Membuat audit trail...")
    c = conn.cursor()
    
    now = datetime.now(WIB)
    
    audit_entries = [
        (now - timedelta(days=30), "admin", "Login", "Admin login ke sistem"),
        (now - timedelta(days=30), "admin", "Create Employee", "Menambahkan karyawan baru"),
        (now - timedelta(days=25), "supervisor", "Login", "Supervisor login ke sistem"),
        (now - timedelta(days=20), "kasir", "Login", "Kasir login ke sistem"),
        (now - timedelta(days=15), "admin", "Update Settings", "Mengubah pengaturan paket cuci"),
        (now - timedelta(days=10), "admin", "Create Payroll", "Membuat slip gaji bulanan"),
        (now - timedelta(days=5), "supervisor", "Approve Payroll", "Menyetujui pembayaran gaji"),
        (now - timedelta(days=1), "admin", "Login", "Admin login ke sistem"),
    ]
    
    for timestamp, user, action, detail in audit_entries:
        c.execute("""
            INSERT INTO audit_trail (timestamp, user, action, detail)
            VALUES (?, ?, ?, ?)
        """, (format_datetime(timestamp), user, action, detail))
    
    conn.commit()
    print(f"✓ {len(audit_entries)} audit trail berhasil ditambahkan")

def generate_summary_report(customers, employees, wash_transactions, 
                          coffee_sales, kasir_transactions, payroll_records, reviews):
    """Generate ringkasan data yang telah dibuat"""
    print("\n" + "="*60)
    print("RINGKASAN DATA DUMMY YANG TELAH DIBUAT")
    print("="*60)
    
    print(f"\n📊 PELANGGAN:")
    print(f"   Total Pelanggan: {len(customers)}")
    mobil_count = sum(1 for c in customers if c['jenis_kendaraan'] == 'Mobil')
    motor_count = len(customers) - mobil_count
    print(f"   - Mobil: {mobil_count}")
    print(f"   - Motor: {motor_count}")
    
    print(f"\n👥 KARYAWAN:")
    print(f"   Total Karyawan: {len(employees)}")
    for role in ["Washer", "QC Inspector", "Kasir", "Supervisor"]:
        count = sum(1 for e in employees if e['role'] == role)
        if count > 0:
            print(f"   - {role}: {count}")
    
    print(f"\n🚗 TRANSAKSI CUCI MOBIL:")
    print(f"   Total Transaksi: {len(wash_transactions)}")
    selesai = sum(1 for t in wash_transactions if t['status'] == 'Selesai')
    proses = len(wash_transactions) - selesai
    print(f"   - Selesai: {selesai}")
    print(f"   - Dalam Proses: {proses}")
    total_pendapatan_cuci = sum(t['harga'] for t in wash_transactions if t['status'] == 'Selesai')
    print(f"   Total Pendapatan: Rp {total_pendapatan_cuci:,}")
    
    print(f"\n☕ PENJUALAN COFFEE/SNACK:")
    print(f"   Total Transaksi: {len(coffee_sales)}")
    total_pendapatan_coffee = sum(s['total'] for s in coffee_sales)
    print(f"   Total Pendapatan: Rp {total_pendapatan_coffee:,}")
    
    print(f"\n💰 TRANSAKSI KASIR:")
    print(f"   Total Transaksi: {len(kasir_transactions)}")
    total_pendapatan_kasir = sum(t['total_bayar'] for t in kasir_transactions)
    print(f"   Total Pendapatan: Rp {total_pendapatan_kasir:,}")
    
    print(f"\n💵 GAJI KARYAWAN:")
    print(f"   Total Record Gaji: {len(payroll_records)}")
    total_gaji_dibayar = sum(p['gaji_bersih'] for p in payroll_records)
    print(f"   Total Gaji Dibayarkan: Rp {total_gaji_dibayar:,}")
    
    print(f"\n⭐ REVIEW PELANGGAN:")
    print(f"   Total Review: {len(reviews)}")
    if reviews:
        avg_rating = sum(r['rating'] for r in reviews) / len(reviews)
        print(f"   Rating Rata-rata: {avg_rating:.2f} / 5.0")
        total_points_given = sum(r['points'] for r in reviews)
        print(f"   Total Poin Reward Diberikan: {total_points_given}")
    
    print(f"\n📈 RINGKASAN KEUANGAN:")
    total_pendapatan = total_pendapatan_kasir + total_pendapatan_coffee
    total_pengeluaran = total_gaji_dibayar
    laba_bersih = total_pendapatan - total_pengeluaran
    print(f"   Total Pendapatan: Rp {total_pendapatan:,}")
    print(f"   Total Pengeluaran (Gaji): Rp {total_pengeluaran:,}")
    print(f"   Laba Bersih: Rp {laba_bersih:,}")
    
    print("\n" + "="*60)
    print("✓ SEMUA DATA DUMMY BERHASIL DIBUAT!")
    print("="*60 + "\n")

def main():
    """Main function untuk populate semua data dummy"""
    print("\n🚀 MEMULAI POPULATE DATA DUMMY...")
    print("="*60)
    
    # Connect to database
    conn = sqlite3.connect(DB_NAME)
    
    try:
        # 1. Populate Customers
        customers = populate_customers(conn, num_customers=50)
        
        # 2. Populate Employees
        employees = populate_employees(conn, num_employees=8)
        
        # 3. Populate Attendance (60 hari terakhir)
        attendance_records = populate_attendance(conn, employees, days=60)
        
        # 4. Populate Payroll (3 bulan terakhir)
        payroll_records = populate_payroll(conn, employees, attendance_records)
        
        # 5. Populate Wash Transactions
        wash_transactions = populate_wash_transactions(conn, customers, num_transactions=200)
        
        # 6. Populate Coffee Sales
        coffee_sales = populate_coffee_sales(conn, num_sales=150)
        
        # 7. Populate Kasir Transactions
        kasir_transactions = populate_kasir_transactions(conn, wash_transactions, len(coffee_sales))
        
        # 8. Populate Customer Reviews
        reviews = populate_customer_reviews(conn, kasir_transactions)
        
        # 9. Populate Audit Trail
        populate_audit_trail(conn)
        
        # 10. Generate Summary Report
        generate_summary_report(customers, employees, wash_transactions, 
                               coffee_sales, kasir_transactions, payroll_records, reviews)
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    main()
