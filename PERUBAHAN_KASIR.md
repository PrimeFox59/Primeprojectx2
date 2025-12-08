# Dokumentasi Perubahan: Coffee Shop → Kasir

## 📋 Ringkasan Perubahan

Sistem **Coffee Shop** telah diubah menjadi **KASIR** yang berfungsi sebagai pusat transaksi untuk seluruh pembayaran di TIME AUTOCARE.

## 🎯 Fitur Utama Baru

### 1. **Sistem Kasir Terpusat**
   - Menu "Coffee Shop" diganti menjadi "Kasir" (💰)
   - Kasir menjadi pusat pembayaran untuk:
     - ✅ Transaksi cuci mobil + coffee/snack (gabungan)
     - ✅ Transaksi coffee/snack saja (tanpa cuci mobil)

### 2. **Alur Kerja Baru**

```
┌─────────────────┐
│  SPV/Supervisor │
│ Input Data Cuci │
│     Mobil       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Data Masuk    │
│   ke KASIR      │
│  (Pending List) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  KASIR proses   │
│   pembayaran:   │
│ - Cuci Mobil    │
│ - Coffee/Snack  │
│ - Gabungan      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Generate       │
│  Invoice WA     │
└─────────────────┘
```

### 3. **Database Baru**

**Tabel: `kasir_transactions`**
- Menyimpan transaksi gabungan (cuci mobil + coffee/snack)
- Fields:
  - `nopol`, `nama_customer`, `no_telp`
  - `wash_trans_id` (FK ke wash_transactions)
  - `paket_cuci`, `harga_cuci`
  - `coffee_items` (JSON), `harga_coffee`
  - `total_bayar`, `status_bayar`, `metode_bayar`
  - `created_by`, `catatan`

## 📱 Halaman Kasir - 5 Tab

### Tab 1: 💰 Transaksi Kasir (X Pending)
**Fitur:**
- Menampilkan daftar mobil yang pending pembayaran
- Form pembayaran dengan opsi:
  - Pilih transaksi cuci mobil dari pending list
  - Tambah coffee/snack (opsional)
  - Input data customer (nopol, nama, telp)
  - Pilih metode pembayaran (Tunai/Transfer/QRIS/Kartu)
  - Status pembayaran (Lunas/DP/Belum Bayar)
- Ringkasan pembayaran real-time
- Generate invoice WhatsApp otomatis

### Tab 2: ☕️ Coffee Only
**Fitur:**
- Penjualan coffee/snack tanpa transaksi cuci mobil
- Input data customer (opsional)
- Generate invoice WhatsApp

### Tab 3: 📜 History Kasir (X)
**Fitur:**
- Riwayat transaksi gabungan yang diproses di kasir
- Filter berdasarkan tanggal dan nopol
- Detail lengkap setiap transaksi:
  - Data customer
  - Detail cuci mobil (jika ada)
  - Detail coffee/snack (jika ada)
  - Total pembayaran dan metode
- Statistik ringkas

### Tab 4: 📜 History Coffee (X)
**Fitur:**
- Riwayat penjualan coffee only
- Filter berdasarkan tanggal dan kasir
- Statistik penjualan

### Tab 5: ⚙️ Setting Menu
**Fitur:**
- Kelola menu coffee/snack (Admin & Supervisor only)
- Tambah, edit, hapus item menu
- Update harga

## 🔧 Fungsi-Fungsi Baru

### Helper Functions
```python
get_pending_wash_transactions()
# Mengambil transaksi cuci mobil yang belum dibayar

save_kasir_transaction(data)
# Menyimpan transaksi kasir (gabungan atau coffee only)

get_all_kasir_transactions()
# Mengambil semua transaksi kasir

generate_kasir_invoice(trans_data, toko_info)
# Generate invoice WhatsApp untuk transaksi kasir
```

## 📊 Dashboard Update

**Kartu Statistik Baru:**
1. 💰 Total Pendapatan (Kasir + Coffee Only)
2. 💳 Transaksi Kasir (gabungan)
3. ☕ Coffee Only
4. 🚗 Cuci Mobil (dari Kasir)
5. ⏳ Pending Pembayaran
6. 👥 Total Customer

**Business Summary:**
- Rata-rata Transaksi Kasir
- Rata-rata Coffee Only
- Kontribusi Kasir (%)
- Kontribusi Coffee (%)

## 🎨 UI/UX Improvements

1. **Warna Tema Kasir:** Gradient hijau (`#11998e` → `#38ef7d`)
2. **Badge Counter:** Jumlah pending, history kasir, history coffee
3. **Auto-fill:** Data customer dari transaksi cuci mobil
4. **Real-time Summary:** Perhitungan total pembayaran otomatis
5. **Pending List:** Visual card untuk setiap mobil yang menunggu pembayaran

## 📝 Invoice WhatsApp

**Format Invoice Kasir:**
```
═══════════════════════════════
        INVOICE KASIR
═══════════════════════════════

TIME AUTOCARE
Detailing & Ceramic Coating

Customer: [Nama]
No. Polisi: [Nopol]
Tanggal: [dd-mm-yyyy]

═══════════════════════════════
      CUCI MOBIL
═══════════════════════════════
Paket: [Nama Paket]
Harga: Rp [X]

═══════════════════════════════
      COFFEE SHOP
═══════════════════════════════
[Qty]x [Item] @ Rp [X]
...
Subtotal Coffee: Rp [X]

═══════════════════════════════

TOTAL PEMBAYARAN:
Rp [TOTAL]

Metode: [Tunai/Transfer/QRIS/Kartu]
Status: Lunas

═══════════════════════════════
```

## 🚀 Cara Penggunaan

### Alur Normal (Cuci Mobil + Coffee):
1. **SPV** input data cuci mobil di halaman "Cuci Mobil"
2. Data otomatis masuk ke daftar pending di **Kasir**
3. **Kasir** buka tab "Transaksi Kasir"
4. Pilih transaksi cuci mobil dari pending list
5. Tambah coffee/snack jika customer pesan
6. Pilih metode pembayaran
7. Simpan transaksi
8. Kirim invoice via WhatsApp

### Alur Coffee Only:
1. **Kasir** buka tab "Coffee Only"
2. Input data customer (opsional)
3. Pilih menu coffee/snack dan qty
4. Simpan transaksi
5. Kirim invoice via WhatsApp

## ⚠️ Catatan Penting

1. **Transaksi cuci mobil** yang sudah dibayar di kasir tidak akan muncul lagi di pending list
2. **Data statistik** di dashboard sudah memisahkan:
   - Pendapatan dari transaksi kasir gabungan
   - Pendapatan dari coffee only
3. **Invoice WhatsApp** akan di-generate otomatis jika nomor telepon diisi
4. **Setting menu coffee** hanya bisa diakses oleh Admin dan Supervisor

## 🔄 Migrasi Data

Database akan otomatis membuat tabel baru `kasir_transactions` saat aplikasi pertama kali dijalankan setelah update. Data lama di tabel `coffee_sales` dan `wash_transactions` tetap tersimpan dan tidak terpengaruh.

---

✅ **Sistem siap digunakan!**

Jika ada pertanyaan atau perlu penyesuaian lebih lanjut, silakan hubungi developer.
