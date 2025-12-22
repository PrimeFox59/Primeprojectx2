# 🗄️ Database Management - Panduan

## 📋 Fitur Otomatis Data Dummy

### ✨ Auto-Populate saat Deploy
Ketika aplikasi di-deploy pertama kali di Streamlit Cloud dan database masih kosong, sistem akan **otomatis** membuat data dummy lengkap. Tidak perlu menjalankan script manual!

**Proses:**
1. Aplikasi check apakah database kosong
2. Jika kosong, otomatis populate data dummy
3. User langsung bisa login dan melihat dashboard dengan data

### 🔄 Reset & Populate Manual (via UI)

Admin dapat reset database dan membuat data dummy baru melalui menu:

**📍 Lokasi Menu:**
```
Login sebagai Admin → Setting Toko → Tab "Database Management"
```

**📊 Fitur yang Tersedia:**

#### 1. Status Database Saat Ini
Menampilkan jumlah:
- 👥 Pelanggan
- 🚗 Transaksi Cuci
- 💰 Transaksi Kasir
- 👨‍💼 Karyawan
- ⭐ Review

#### 2. Reset & Populate Data Dummy
**Fungsi:**
- Menghapus SEMUA data transaksi yang ada
- Membuat data dummy baru yang lengkap

**Data Dummy yang Dibuat:**
- ✅ 30 pelanggan dengan berbagai jenis kendaraan
- ✅ 6 karyawan (Washer, QC Inspector, Kasir, Supervisor)
- ✅ 100 transaksi cuci mobil (60 hari terakhir)
- ✅ 50 transaksi coffee/snack standalone
- ✅ ~60 transaksi kasir gabungan (cuci + coffee)
- ✅ ~60 review pelanggan dengan rating 3-5
- ✅ 180 record presensi karyawan (30 hari x 6 karyawan)
- ✅ Data keuangan & gaji lengkap

**Cara Menggunakan:**
1. Centang checkbox konfirmasi
2. Klik tombol "Reset & Populate Data Dummy"
3. Tunggu proses selesai (~5-10 detik)
4. Database siap dengan data dummy baru!

#### 3. Backup Database
**Fungsi:**
- Membuat backup file database saat ini
- File disimpan dengan timestamp
- Bisa di-download

**Cara Menggunakan:**
1. Klik tombol "Backup Database"
2. Klik "Download Backup" untuk menyimpan file

## 🚀 Deploy ke Streamlit Cloud

### Langkah-langkah Deploy:

1. **Push ke GitHub**
   ```bash
   git add .
   git commit -m "Add auto populate dummy data"
   git push origin main
   ```

2. **Deploy di Streamlit Cloud**
   - Login ke https://share.streamlit.io
   - Klik "New app"
   - Pilih repository dan branch
   - File: `app.py`
   - Deploy!

3. **First Run**
   - Aplikasi akan otomatis detect database kosong
   - Data dummy otomatis dibuat
   - Login dengan:
     - Username: `admin` / Password: `admin123`
     - Username: `kasir` / Password: `kasir123`
     - Username: `supervisor` / Password: `super123`

## 📝 Catatan Penting

### ⚠️ Keamanan
- Fitur reset hanya tersedia untuk role **Admin**
- Ada konfirmasi sebelum reset untuk mencegah kesalahan
- Semua aktivitas tercatat di Audit Trail

### 💾 Database File
- File database: `car_wash.db`
- Otomatis dibuat jika belum ada
- Di Streamlit Cloud, database bersifat ephemeral (reset saat restart)
- Untuk production, pertimbangkan gunakan database eksternal (PostgreSQL, MySQL, dll)

### 🔄 Reset vs Backup
- **Reset**: Menghapus semua data dan populate ulang dummy
- **Backup**: Menyimpan copy database tanpa menghapus apapun

## 🛠️ Troubleshooting

### Database tidak otomatis populate?
Pastikan fungsi `check_database_empty()` return `True` saat database kosong.

### Error saat reset?
- Check permissions file database
- Pastikan tidak ada koneksi database yang masih open
- Restart aplikasi

### Data dummy tidak sesuai?
Edit fungsi `populate_dummy_data()` di `app.py` sesuai kebutuhan:
- Ubah jumlah customers (default: 30)
- Ubah jumlah employees (default: 6)
- Ubah jumlah transaksi (default: 100)
- Sesuaikan range tanggal (default: 60 hari)

## 📚 Referensi

### User Credentials Default:
```
Admin:
  - Username: admin
  - Password: admin123
  - Akses: Full access

Kasir:
  - Username: kasir
  - Password: kasir123
  - Akses: Dashboard, Kasir, Payroll

Supervisor:
  - Username: supervisor
  - Password: super123
  - Akses: Dashboard, Cuci Mobil
```

### Database Schema:
- `customers`: Data pelanggan
- `employees`: Data karyawan
- `wash_transactions`: Transaksi cuci mobil
- `kasir_transactions`: Transaksi kasir
- `coffee_sales`: Penjualan coffee/snack
- `customer_reviews`: Review pelanggan
- `customer_points`: Poin reward pelanggan
- `attendance`: Presensi karyawan
- `payroll`: Data gaji karyawan
- `audit_trail`: Log aktivitas
- `users`: User accounts
- `settings`: Konfigurasi aplikasi
- `shift_settings`: Setting shift dan persentase gaji

---

**📅 Last Updated:** December 2025
**👨‍💻 Version:** 2.0
