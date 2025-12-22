# 🚗 TIME AUTOCARE - Car Wash Management System

Sistem manajemen cuci mobil lengkap dengan fitur kasir, keuangan, karyawan, dan review pelanggan.

## ✨ Fitur Utama

### 🎯 Fitur Bisnis
- 📊 **Dashboard Interaktif** - Statistik real-time pendapatan, transaksi, dan performa
- 🚗 **Manajemen Cuci Mobil** - Input transaksi, checklist QC, tracking status
- 💰 **Kasir** - Transaksi cuci + coffee/snack, multiple payment methods
- 👥 **Database Pelanggan** - Riwayat kunjungan, data kendaraan lengkap
- ⭐ **Review & Rating** - Sistem reward points untuk customer loyalty
- 📈 **Laporan Keuangan** - Pendapatan harian/bulanan/tahunan dengan visualisasi
- ☕ **Coffee Shop** - Manajemen menu dan penjualan coffee/snack

### 👨‍💼 Manajemen Karyawan
- 📅 **Presensi** - Input jam masuk/pulang, tracking kehadiran
- 💵 **Payroll** - Sistem gaji otomatis berdasarkan shift dan pendapatan
- 🔄 **Shift Management** - Pagi/Malam dengan persentase berbeda
- 📊 **Laporan Kinerja** - Analisis produktivitas karyawan

### 🔐 Keamanan & Akses
- 👤 **Multi-User** - Admin, Kasir, Supervisor dengan hak akses berbeda
- 📜 **Audit Trail** - Log semua aktivitas pengguna
- 🔒 **Password Protection** - Sistem login aman

### 🗄️ **Database Management** (FITUR BARU!)
- ✅ **Auto-Populate** - Data dummy otomatis saat deploy pertama kali
- 🔄 **Reset & Populate** - Reset database dan buat data dummy baru via UI
- 💾 **Backup Database** - Backup dan download database
- 📊 **Database Stats** - Monitor jumlah data real-time

## 🚀 Quick Start

### 1. Deploy ke Streamlit Cloud

```bash
# Clone repository
git clone <your-repo-url>
cd Primeprojectx2

# Deploy ke Streamlit Cloud
# - Login ke https://share.streamlit.io
# - New app → Pilih repository
# - File: app.py
# - Deploy!
```

### 2. First Run
Saat pertama kali dijalankan, sistem akan:
1. ✅ Otomatis membuat database
2. ✅ Otomatis populate data dummy (30 pelanggan, 100 transaksi, dll)
3. ✅ Siap digunakan!

### 3. Login

**Default Accounts:**
```
Admin:
  Username: admin
  Password: admin123
  
Kasir:
  Username: kasir
  Password: kasir123
  
Supervisor:
  Username: supervisor
  Password: super123
```

## 📦 Requirements

```txt
streamlit
pandas
altair
pytz
```

Install dependencies:
```bash
pip install -r requirements.txt
```

## 🗄️ Database Management

### Auto-Populate Data Dummy
Ketika database kosong (deploy pertama kali), sistem otomatis membuat:
- 👥 30 pelanggan dummy
- 👨‍💼 6 karyawan dummy (Washer, QC Inspector, Kasir, Supervisor)
- 🚗 100 transaksi cuci mobil (60 hari terakhir)
- ☕ 50 transaksi coffee/snack
- 💰 ~60 transaksi kasir gabungan
- ⭐ ~60 review pelanggan (rating 3-5 bintang)
- 📅 180 record presensi (30 hari x 6 karyawan)
- 💵 Data gaji & keuangan lengkap

### Reset & Populate Manual
Admin dapat reset database via UI:
1. Login sebagai **Admin**
2. Menu **Setting Toko** → Tab **Database Management**
3. Centang konfirmasi → Klik **Reset & Populate Data Dummy**
4. Database di-reset dan diisi ulang dengan data dummy baru

### Backup Database
1. Login sebagai **Admin**
2. Menu **Setting Toko** → Tab **Database Management**
3. Klik **Backup Database**
4. Download file backup

📖 **Dokumentasi Lengkap:** Lihat [DATABASE_MANAGEMENT.md](DATABASE_MANAGEMENT.md)

## 📊 Data Dummy Details

### Pelanggan (30 orang)
- Nama lengkap realistis
- Nomor polisi kendaraan (B/D/L/F/N/T/S/H/K/R)
- Jenis: Mobil & Motor
- Merk: Toyota, Honda, Suzuki, BMW, dll
- Ukuran: Kecil, Sedang, Besar, Extra Besar

### Karyawan (6 orang)
- **Washer**: Gaji Rp 3-4 juta
- **QC Inspector**: Gaji Rp 3.5-4.5 juta
- **Kasir**: Gaji Rp 3.5-4.5 juta
- **Supervisor**: Gaji Rp 5-6 juta
- Shift: Pagi (08:00-17:00) & Malam (17:00-08:00)

### Transaksi (100+ transaksi)
- Paket: Cuci Reguler, Premium, Wax, Full Detailing, dll
- Harga dinamis berdasarkan ukuran kendaraan
- Status: Selesai (95%), Dalam Proses (5%)
- Coffee/snack combo (30% chance)

### Review Pelanggan (~60 review)
- Rating: 3-5 bintang (mayoritas 4-5)
- Review text bervariasi
- Reward points: 10-50 poin per review
- 60% dari transaksi dapat review

### Keuangan
- Total Pendapatan: ~Rp 30-50 juta (simulasi 60 hari)
- Total Gaji: ~Rp 75-90 juta (3 bulan)
- Presensi: 90% hadir, 5% izin, 5% alpha
- Perhitungan gaji akurat berdasarkan shift dan hari kerja

## 🎨 Fitur UI/UX

- 🎨 **Modern Design** - Gradient colors, shadows, smooth transitions
- 📱 **Responsive** - Works on desktop, tablet, mobile
- 📊 **Interactive Charts** - Altair visualizations
- 💫 **Smooth Animations** - Hover effects, transitions
- 🎯 **User-Friendly** - Intuitive navigation, clear labels
- ⚡ **Fast Performance** - Optimized database queries

## 📂 Struktur Project

```
Primeprojectx2/
│
├── app.py                      # Main application
├── car_wash.db                 # SQLite database (auto-created)
├── requirements.txt            # Python dependencies
├── DATABASE_MANAGEMENT.md      # Database management guide
├── README.md                   # This file
└── populate_dummy_data.py      # Standalone script (optional)
```

## 🔧 Konfigurasi

### Paket Cucian
Edit melalui menu **Setting Toko** atau langsung di database `settings` table.

Default paket:
- Cuci Reguler: Rp 50,000
- Cuci Premium: Rp 75,000
- Cuci + Wax: Rp 100,000
- Full Detailing: Rp 200,000
- Interior Only: Rp 60,000
- Exterior Only: Rp 40,000

### Multiplier Ukuran
- Kecil: 1.0x
- Sedang: 1.2x
- Besar: 1.5x
- Extra Besar: 2.0x

### Coffee Menu
Edit melalui UI atau database. Default menu:
- Espresso: Rp 15,000
- Americano: Rp 18,000
- Latte: Rp 22,000
- Cappuccino: Rp 22,000
- Mocha: Rp 25,000
- Iced Coffee: Rp 20,000
- Biskuit: Rp 8,000
- Roti Manis: Rp 12,000
- Sandwich: Rp 20,000

### Shift & Persentase Gaji
- **Pagi** (08:00-17:00): 35% dari pendapatan
- **Malam** (17:00-08:00): 45% dari pendapatan

Edit melalui menu **Payroll** → Tab **Setting Shift**.

## 🎯 User Roles & Akses

### Admin (Owner)
- ✅ Full access ke semua fitur
- ✅ Laporan keuangan lengkap
- ✅ User management
- ✅ Settings & configuration
- ✅ Database management
- ✅ Audit trail

### Kasir
- ✅ Dashboard (daily only)
- ✅ Kasir (transaksi)
- ✅ Payroll (input presensi, lihat gaji sendiri)
- ❌ Settings
- ❌ Laporan keuangan
- ❌ User management

### Supervisor
- ✅ Dashboard (monitoring)
- ✅ Cuci Mobil (QC & approval)
- ❌ Kasir
- ❌ Payroll
- ❌ Settings
- ❌ Laporan keuangan

## 📈 Analytics & Reports

### Dashboard
- 💰 Pendapatan hari ini, minggu ini, bulan ini
- 🚗 Jumlah transaksi per periode
- ⭐ Rating rata-rata
- 📊 Chart pendapatan 30 hari terakhir
- 🎯 Top customers
- 📈 Growth metrics

### Laporan
- 📊 Laporan Harian
- 📅 Laporan Bulanan
- 📆 Laporan Tahunan
- 💰 Analisis Keuangan
- 👥 Customer Analysis
- 📈 Trend Analysis

## 🛠️ Development

### Run Locally
```bash
streamlit run app.py
```

### Reset Database (via script)
```bash
python populate_dummy_data.py
```

### Reset Database (via UI)
Menu **Setting Toko** → **Database Management** → **Reset & Populate Data Dummy**

## 📝 Changelog

### Version 2.0 (Latest)
- ✨ **NEW**: Auto-populate data dummy saat deploy
- ✨ **NEW**: Database management UI (reset, backup)
- ✨ **NEW**: Database statistics monitoring
- 🔄 Improved error handling
- 🎨 UI improvements

### Version 1.0
- Initial release
- Core features: Dashboard, Cuci Mobil, Kasir, Payroll
- Customer management & reviews
- Multi-user with role-based access
- Reports & analytics

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is private and proprietary.

## 👨‍💻 Support

Untuk pertanyaan atau bantuan, hubungi administrator.

---

**🎉 Selamat menggunakan TIME AUTOCARE Management System!**

Deploy sekarang dan sistem akan otomatis setup dengan data dummy lengkap! 🚀
