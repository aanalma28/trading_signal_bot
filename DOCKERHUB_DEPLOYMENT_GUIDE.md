# Panduan Deployment Jitu (Docker Hub Method)

Cara ini adalah **metode paling aman dan anti-gagal** untuk VPS dengan spesifikasi rendah atau batasan keamanan ketat (LXC/OpenVZ). Daripada menyiksa VPS Anda dengan proses kompilasi (*build*) yang berat, kita akan mem-*build* semuanya di komputer/laptop lokal Anda, mengunggahnya ke Docker Hub, lalu sekadar men-*download* versi matangnya di VPS.

---

## TAHAP 1: Di Laptop / Komputer Lokal Anda

### 1. Buat Akun Docker Hub
Jika Anda belum punya akun, daftar gratis di [hub.docker.com](https://hub.docker.com/).
Setelah mendaftar, catat **Username** Docker Anda (misal: `aanalma`).

### 2. Login Docker di Laptop Anda
Buka terminal laptop Anda, lalu ketik:
```bash
docker login
```
*Masukkan Username dan Password Docker Hub Anda.*

### 3. Build Image di Laptop
Arahkan terminal ke dalam folder project Anda (`projek_backtest_trading`), lalu jalankan perintah ini satu per satu (ganti `USERNAME_ANDA` dengan username Docker Hub Anda):

**A. Build Backend:**
```bash
docker build -t USERNAME_ANDA/liquidity_backend:latest -f backend/Dockerfile .
```

**B. Build Frontend:**
```bash
cd frontend
docker build -t USERNAME_ANDA/liquidity_frontend:latest -f Dockerfile .
cd ..
```

### 4. Push Image ke Docker Hub
Setelah proses build selesai, unggah (*upload*) aplikasi Anda ke Docker Hub:
```bash
docker push USERNAME_ANDA/liquidity_backend:latest
docker push USERNAME_ANDA/liquidity_frontend:latest
```
*(Proses ini membutuhkan waktu sesuai kecepatan internet upload Anda).*

---

## TAHAP 2: Di VPS Anda

Kini saatnya beralih ke server VPS Anda. VPS Anda hanya perlu men-*download* dan menjalankannya!

### 1. Masuk ke VPS & Setup
Masuk ke VPS via SSH, lalu pindah ke folder project Anda.
```bash
cd ~/trading_signal_bot
```

### 2. Tambahkan Username Docker Anda ke .env
Buka file kredensial Anda dengan `nano .env` dan tambahkan baris ini di paling bawah:
```env
DOCKER_USERNAME="USERNAME_ANDA"
```

### 3. Jalankan Aplikasi menggunakan versi Prod
Kita akan menggunakan file `docker-compose.prod.yml` yang sudah saya sediakan khusus untuk men-*download* (*pull*) dari Docker Hub tanpa mem-*build* ulang.

```bash
docker-compose -f docker-compose.prod.yml up -d
```

### 🎉 Selesai!
VPS Anda hanya butuh waktu beberapa detik untuk men-*download* *image* matang tersebut dan langsung menyalakannya. Buka IP VPS Anda di browser, dan Anda akan langsung disambut oleh halaman Login!

---
> **Catatan Pembaruan (Update Code):** 
> Apabila di masa depan Anda mengubah kode (misal mengedit warna frontend atau strategi backend), Anda cukup mengulangi **Tahap 1 (Langkah 3 dan 4)** di laptop Anda, lalu menjalankan perintah ini di VPS: 
> `docker-compose -f docker-compose.prod.yml pull && docker-compose -f docker-compose.prod.yml up -d`
