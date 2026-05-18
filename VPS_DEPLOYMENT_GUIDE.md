# Panduan Lengkap Deployment ke VPS (Ubuntu / Debian)

Panduan ini berasumsi Anda baru saja membeli VPS dengan OS Linux (Ubuntu atau Debian direkomendasikan). Ikuti langkah-langkah ini secara berurutan.

## 1. Masuk ke VPS (SSH)
Buka terminal/CMD di komputer Anda dan masuk ke VPS menggunakan alamat IP publik yang diberikan oleh provider Anda.

```bash
ssh root@IP_VPS_ANDA
# (Tekan enter, lalu masukkan password VPS Anda)
```

---

## 2. Setup SWAP Memory (Pengaman RAM)
Langkah wajib untuk VPS dengan RAM di bawah 2GB agar tidak *crash* saat melakukan *build*.

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```
*(Untuk memastikan swap berhasil dibuat, Anda bisa mengetik `free -h` dan pastikan baris `Swap:` memiliki angka sekitar 2.0G).*

---

## 3. Install Git & Docker
Perbarui sistem operasi Anda dan instal perangkat lunak yang dibutuhkan untuk menarik kode dan menjalankannya.

```bash
# Update repository
sudo apt update -y

# Install Git, Docker, dan Docker Compose
sudo apt install git docker.io docker-compose -y

# Pastikan Docker berjalan otomatis setiap kali VPS restart
sudo systemctl enable docker
sudo systemctl start docker
```

---

## 4. Download / Clone Projek dari GitHub
Tarik kode sumber yang sudah Anda *push* ke GitHub sebelumnya.

```bash
# Ganti URL di bawah ini dengan URL repositori GitHub Anda
git clone https://github.com/USERNAME_ANDA/projek_backtest_trading.git

# Masuk ke folder projek
cd projek_backtest_trading
```

---

## 5. Pembuatan File Kredensial (.env)

Karena file `.env` bersifat rahasia dan sudah kita masukkan ke dalam `.gitignore`, file tersebut **tidak ikut ter-upload** ke GitHub. Anda harus membuatnya secara manual di dalam VPS.

```bash
# Membuat dan membuka file .env dengan text editor bawaan (Nano)
nano .env
```

Setelah layar Nano terbuka, ketik/paste isi kredensial Telegram Anda:

```env
TELEGRAM_BOT_TOKEN="ISI_TOKEN_BOT_ANDA_DI_SINI"
TELEGRAM_CHAT_ID="ISI_CHAT_ID_ANDA_DI_SINI"
```

**Cara Save & Keluar dari Nano:**
1. Tekan `Ctrl + X`
2. Tekan huruf `Y` (untuk konfirmasi Yes)
3. Tekan `Enter` (untuk mengonfirmasi nama file)

---

## 6. Build & Jalankan Aplikasi (Docker Compose)
Ini adalah langkah terakhir. Kita akan memerintahkan Docker untuk mengkompilasi React dan membungkus Python API sesuai konfigurasi yang sudah kita buat.

```bash
docker-compose up -d --build
```
> **Catatan:** Proses ini akan memakan waktu sekitar 3 - 8 menit tergantung kecepatan CPU VPS Anda karena ia sedang men-download *image* OS Python, menginstall ratusan megabyte library Numpy & Pandas, dan mengkompilasi file statis React.

---

## 7. Selesai! 🎉

Jika terminal sudah menampilkan status `Started` atau `Done` berwarna hijau, artinya aplikasi Anda sudah mengudara secara global.

Buka web browser di HP atau Laptop Anda, dan ketikkan alamat IP VPS Anda:
👉 `http://IP_VPS_ANDA`

Anda akan melihat tampilan web Liquidity Sweep, dan Anda sudah bisa langsung mengklik tombol **"Aktifkan Bot Telegram"** untuk memulai pemantauan market secara live!

### Perintah Bermanfaat Tambahan (Troubleshooting):
* **Melihat status jalannya aplikasi**: `docker-compose ps`
* **Mematikan server**: `docker-compose down`
* **Melihat log/error dari backend**: `docker logs liquidity_backend`
* **Melihat log/error dari frontend**: `docker logs liquidity_frontend`
