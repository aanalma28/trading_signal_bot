# Liquidity Sweep Automated Backtester & Telegram Bot

A full-stack, automated crypto trading platform tailored for analyzing market structure through Liquidity Sweep strategies (Reversal and Trend Continuation). Built with FastAPI (Python) and React (Vite).

## Features

- **Advanced Backtesting Engine**: Test Liquidity Sweep strategies over historical data fetched directly from the Binance Futures API.
- **Role-Based Access Control (RBAC)**: Secure authentication system with JWT. The application is hidden behind a login wall.
  - **Admin Access**: Can run backtests AND control the Telegram bot (`username: admin` | `password: admin123`).
  - **User Access**: Can only run backtests (`username: user` | `password: user123`).
- **DDoS Protection**: Implements SlowAPI rate-limiting on authentication and backtest endpoints.
- **Multi-Timeframe Analysis**: Built-in logic leveraging 1-Hour HTF (Higher Time Frame) trend identification and 15-Minute execution details.
- **Dynamic Checklists & Ratings**: Provides a transparent 8-10 point checklist with a corresponding star rating (⭐⭐⭐⭐⭐) for every generated signal to grade the setup quality.
- **Risk Management Integration**: Automatically calculates suggested Entry, Stop Loss (SL), and Take Profit (TP) targets based on custom risk percentages.
- **Automated Telegram Bot**: Background processor that actively monitors the market and sends real-time entry alerts directly to your Telegram.
- **Web UI Bot Controller**: Start and stop the real-time Telegram bot directly from the web interface. No CLI access required.
- **Production Ready**: Fully dockerized utilizing multi-stage builds and an NGINX reverse proxy for easy VPS deployment.

## Tech Stack

- **Backend**: Python 3.12, FastAPI, Pandas, Pandas-TA (Technical Analysis), Schedule, Uvicorn.
- **Frontend**: React 19, Vite, Vanilla CSS.
- **Deployment**: Docker, Docker Compose, Nginx.

## Prerequisites
- Node.js & npm (for local frontend development)
- Python 3.12+ (for local backend development)
- Docker & Docker Compose (for production deployment)
- A Telegram Bot Token (from `@BotFather`) and your Chat ID

## Environment Variables

Create a `.env` file in the root directory of the project:

```env
TELEGRAM_BOT_TOKEN="your_bot_token_from_botfather"
TELEGRAM_CHAT_ID="your_telegram_chat_id"
```
*(Make sure you have started a chat with your newly created bot on Telegram before running the application so it is authorized to message you).*

---

## Local Development Setup

### 1. Backend Initialization

Open a terminal in the root directory:

```bash
# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install required dependencies
pip install -r requirements.txt

# Start the FastAPI Server
cd backend
uvicorn main:app --reload
```
The backend API will run on `http://localhost:8000`.

### 2. Frontend Initialization

Open a new, separate terminal in the root directory:

```bash
cd frontend

# Install Node modules
npm install

# Start the Vite development server
npm run dev
```
The frontend UI will run on `http://localhost:5173`.

---

## Production Deployment (VPS)

Karena perbedaan spesifikasi dan limitasi keamanan tiap provider VPS (seperti isolasi kernel LXC), kami menyediakan **3 panduan deployment terpisah** agar Anda bisa memilih yang paling cocok dan dijamin berhasil untuk server Anda:

1. **[Native Linux Method](VPS_DEPLOYMENT_GUIDE.md)**: (Rekomendasi) Menjalankan backend dan frontend secara native tanpa Docker menggunakan `Nginx` dan `systemd`/`screen`. Cocok untuk VPS dengan spesifikasi sangat rendah (RAM < 1GB).
2. **[Docker Hub Method](DOCKERHUB_DEPLOYMENT_GUIDE.md)**: Mem-*build* image Docker di laptop lokal dan sekadar melakukan `pull` di VPS. Ini adalah cara teraman jika VPS Anda menolak akses kompilasi root Docker.
3. **Standar Docker Compose**: Jika VPS Anda memiliki akses kernel penuh (KVM/Dedicated), Anda bisa langsung mem-build dan menjalankannya di server dengan perintah:

```bash
docker-compose up -d --build
```

- `-d` runs the containers in detached mode (background).
- `--build` forces a fresh compilation of the React static files and Python packages.

Once completed, the application will be globally accessible via your server's Public IP address or configured domain name on **Port 80**. Nginx will automatically route web traffic to the frontend and `/api/` endpoints to the Python backend.

## Architecture & Bot Lifecycle

- The FastAPI application manages a subprocess tracking the Telegram bot. 
- Using OS-level `pgrep` and `pkill` commands, the backend ensures the bot process remains strictly isolated and cannot be duplicated.
- The bot evaluates market conditions every 15 minutes (at `:00`, `:15`, `:30`, `:45`) to respect candle closure rules, checking Open Interest, Funding Rates, and Market Structure shifts before dispatching an alert.
