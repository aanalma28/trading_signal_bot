import { useState, useEffect } from 'react'
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import Login from './Login'
import './App.css'

function BacktestDashboard() {
  const navigate = useNavigate()
  const token = localStorage.getItem('token')
  const role = localStorage.getItem('role')

  const handleLogout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('role')
    navigate('/login')
  }
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)
  const [expandedTrade, setExpandedTrade] = useState(null)
  
  const [botRunning, setBotRunning] = useState(false)
  const [botLoading, setBotLoading] = useState(false)

  useEffect(() => {
    fetchBotStatus()
  }, [])

  const fetchBotStatus = async () => {
    try {
      const res = await fetch('/api/bot/status', {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (res.status === 401) return handleLogout()
      const data = await res.json()
      setBotRunning(data.running)
    } catch (e) {
      console.error("Gagal mengecek status bot", e)
    }
  }

  const toggleBot = async () => {
    setBotLoading(true)
    try {
      const endpoint = botRunning ? '/api/bot/stop' : '/api/bot/start'
      const res = await fetch(endpoint, { 
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (res.status === 401) return handleLogout()
      await fetchBotStatus()
    } catch (e) {
      alert("Gagal mengubah status bot")
    } finally {
      setBotLoading(false)
    }
  }
  
  const today = new Date().toISOString().split('T')[0];
  const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

  const [formData, setFormData] = useState({
    strategy: 'reversal',
    symbol: 'PENGUUSDT',
    interval: '15m',
    start_date: thirtyDaysAgo,
    end_date: today,
    initial_balance: 10,
    monthly_topup: 0,
    stop_loss_pct: 2.0
  })

  const handleChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: ['strategy', 'symbol', 'interval', 'start_date', 'end_date'].includes(name)
        ? value 
        : parseFloat(value) || 0
    }))
  }

  const runBacktest = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResults(null)
    
    try {
      const response = await fetch('/api/backtest', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(formData)
      })
      if (response.status === 401) return handleLogout()
      
      if (!response.ok) {
        const errData = await response.json()
        throw new Error(errData.detail || 'Terjadi kesalahan saat memproses data')
      }
      
      const data = await response.json()
      setResults(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const toggleTrade = (index) => {
    if (expandedTrade === index) setExpandedTrade(null)
    else setExpandedTrade(index)
  }

  return (
    <div className="container">
      <header className="header" style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
        <div>
          <h1>Liquidity Sweep</h1>
          <p>Bot Trading & Backtester Otomatis</p>
        </div>
        
        <div style={{display: 'flex', alignItems: 'center', gap: '1rem'}}>
          {role === 'admin' && (
            <div className="bot-controller">
              <span style={{marginRight: '1rem', fontWeight: '500'}}>Telegram Bot:</span>
              <button 
                className={`btn ${botRunning ? 'btn-danger' : 'btn-primary'}`}
                onClick={toggleBot}
                disabled={botLoading}
              >
                {botLoading ? 'Memproses...' : (botRunning ? '🔴 Matikan Bot' : '🟢 Aktifkan Bot')}
              </button>
            </div>
          )}
          <button onClick={handleLogout} className="btn" style={{backgroundColor: 'transparent', border: '1px solid var(--danger-color)', color: 'var(--danger-color)'}}>Logout</button>
        </div>
      </header>

      <div className="main-content">
        <aside className="sidebar">
          <form className="glass-panel" onSubmit={runBacktest}>
            <div className="form-group">
              <label>Strategi</label>
              <select className="form-control" name="strategy" value={formData.strategy} onChange={handleChange}>
                <option value="reversal">Liquidity Sweep Reversal</option>
                <option value="continuation">Trend Continuation</option>
              </select>
            </div>
            
            <div className="form-group">
              <label>Pasangan Koin</label>
              <input type="text" className="form-control" name="symbol" value={formData.symbol} onChange={handleChange} placeholder="BTCUSDT" />
            </div>

            <div className="form-group">
              <label>Timeframe</label>
              <select className="form-control" name="interval" value={formData.interval} onChange={handleChange}>
                <option value="5m">5 Menit</option>
                <option value="15m">15 Menit</option>
                <option value="1h">1 Jam</option>
                <option value="4h">4 Jam</option>
              </select>
            </div>

            <div className="form-group">
              <label>Tanggal Mulai</label>
              <input type="date" className="form-control" name="start_date" value={formData.start_date} onChange={handleChange} max={formData.end_date} />
            </div>

            <div className="form-group">
              <label>Tanggal Akhir</label>
              <input type="date" className="form-control" name="end_date" value={formData.end_date} onChange={handleChange} max={today} />
            </div>

            <div className="form-group">
              <label>Saldo Awal ($)</label>
              <input type="number" className="form-control" name="initial_balance" value={formData.initial_balance} onChange={handleChange} step="0.01" />
            </div>

            <div className="form-group">
              <label>Top-Up Bulanan ($)</label>
              <input type="number" className="form-control" name="monthly_topup" value={formData.monthly_topup} onChange={handleChange} step="0.01" />
            </div>

            <div className="form-group">
              <label>Batas Stop Loss (%)</label>
              <input type="number" className="form-control" name="stop_loss_pct" value={formData.stop_loss_pct} onChange={handleChange} step="0.1" />
            </div>

            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? 'Mengambil Data...' : 'Jalankan Backtest'}
            </button>
            
            {loading && <p style={{marginTop: '1rem', fontSize: '0.85rem', color: '#cbd5e1', textAlign: 'center'}}>Data ditarik langsung dari Binance. Untuk 30+ hari, ini mungkin memakan waktu ~10-30 detik.</p>}
          </form>
        </aside>

        <main className="results-panel">
          {error && (
            <div className="glass-panel" style={{borderColor: 'var(--danger-color)', color: 'var(--danger-color)'}}>
              <h3>Error!</h3>
              <p>{error}</p>
            </div>
          )}

          {loading && (
            <div className="glass-panel spinner-container">
              <div className="spinner"></div>
              <h3>Memproses Backtest...</h3>
              <p style={{color: 'var(--text-secondary)'}}>Menghitung jutaan titik data dengan Pandas.</p>
            </div>
          )}

          {results && !loading && (
            <div className="glass-panel">
              <h2 style={{marginBottom: '1.5rem'}}>Ringkasan Performa</h2>
              
              <div className="stats-grid">
                <div className="stat-card">
                  <div className="stat-label">Win Rate (RR 1:2)</div>
                  <div className="stat-value">{results.statistics.win_rate.toFixed(2)}%</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Total Invested</div>
                  <div className="stat-value">${results.statistics.total_invested.toFixed(2)}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Total PnL</div>
                  <div className={`stat-value ${results.statistics.total_pnl >= 0 ? 'success' : 'danger'}`}>
                    {results.statistics.total_pnl >= 0 ? '+' : ''}{results.statistics.total_pnl.toFixed(2)}%
                  </div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Saldo Akhir</div>
                  <div className={`stat-value ${results.statistics.final_balance >= results.statistics.total_invested ? 'success' : 'danger'}`}>
                    ${results.statistics.final_balance.toFixed(2)}
                  </div>
                </div>
              </div>

              <div style={{marginBottom: '2rem', display: 'flex', gap: '1rem', fontSize: '0.9rem', color: 'var(--text-secondary)'}}>
                <span>🎯 Target Tersentuh:</span>
                <span><strong>RR 1:2</strong> = {results.statistics.rr_1_2}</span>
                <span><strong>RR 1:3</strong> = {results.statistics.rr_1_3}</span>
                <span><strong>RR 1:5</strong> = {results.statistics.rr_1_5}</span>
              </div>

              <h3 style={{marginBottom: '1rem'}}>Daftar Transaksi (Klik untuk melihat Checklist)</h3>
              <div className="trades-list">
                {results.trades.length === 0 ? (
                  <p>Tidak ada sinyal yang ditemukan dengan pengaturan ini.</p>
                ) : (
                  results.trades.map((trade, idx) => (
                    <div className="trade-item" key={idx}>
                      <div className="trade-header" onClick={() => toggleTrade(idx)}>
                        <div className="trade-info">
                          <span className={`trade-type ${trade.type.toLowerCase()}`}>{trade.type}</span>
                          <span>{new Date(trade.time).toLocaleString('id-ID')}</span>
                          <span>@ {trade.entry_price.toFixed(5)}</span>
                        </div>
                        <div className="trade-info">
                          <span style={{color: '#fbbf24', fontSize: '0.85rem', marginRight: '0.5rem'}}>{trade.stars || "⭐⭐⭐"}</span>
                          <span style={{color: 'var(--text-secondary)', fontSize: '0.9rem'}}>Max RR: 1:{trade.max_rr.toFixed(1)}</span>
                          <span className={`trade-status ${trade.status.toLowerCase()}`}>
                            {trade.status}
                          </span>
                        </div>
                      </div>
                      
                      {expandedTrade === idx && (
                        <div className="trade-details">
                          <div style={{display: 'flex', gap: '1.5rem', marginBottom: '1rem', padding: '0.8rem', backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '8px', fontSize: '0.9rem', flexWrap: 'wrap'}}>
                            <div><strong>Entry:</strong> {trade.entry_price.toFixed(5)}</div>
                            <div style={{color: 'var(--danger-color)'}}><strong>SL:</strong> {(trade.sl_price || 0).toFixed(5)}</div>
                            <div style={{color: 'var(--success-color)'}}><strong>TP (1:2):</strong> {(trade.tp_price || 0).toFixed(5)}</div>
                          </div>
                          <div style={{marginBottom: '0.5rem', fontWeight: '600', color: 'var(--accent-color)'}}>Checklist Persyaratan:</div>
                          <ul className="checklist">
                            {trade.checklist.map((item, i) => (
                              <li className="checklist-item" key={i}>
                                <span className={`checklist-icon ${item.met ? 'met' : 'unmet'}`}>
                                  {item.met ? '✓' : '✗'}
                                </span>
                                {item.condition}
                              </li>
                            ))}
                          </ul>
                          <div style={{marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--glass-border)'}}>
                            <span style={{color: 'var(--text-secondary)'}}>Saldo setelah transaksi ini: </span>
                            <strong>${trade.balance_after.toFixed(2)}</strong>
                          </div>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}

const ProtectedRoute = ({ children }) => {
  const token = localStorage.getItem('token')
  if (!token) return <Navigate to="/login" replace />
  return children
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={
        <ProtectedRoute>
          <BacktestDashboard />
        </ProtectedRoute>
      } />
    </Routes>
  )
}

export default App
