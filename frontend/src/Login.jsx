import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import './App.css'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleLogin = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    
    try {
      const response = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      })
      
      const data = await response.json()
      
      if (!response.ok) {
        throw new Error(data.detail || 'Login gagal')
      }
      
      localStorage.setItem('token', data.access_token)
      localStorage.setItem('role', data.role)
      
      navigate('/')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="container" style={{maxWidth: '400px', marginTop: '10vh'}}>
      <div style={{textAlign: 'center', marginBottom: '2rem'}}>
        <h1 style={{fontSize: '2rem', marginBottom: '0.5rem', background: 'var(--primary-gradient)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'}}>
          Liquidity Sweep
        </h1>
        <p style={{color: 'var(--text-secondary)'}}>Sistem Backtest & Bot Trading</p>
      </div>

      <div className="card">
        <h2 style={{marginBottom: '1.5rem', textAlign: 'center'}}>Sign In</h2>
        
        {error && (
          <div style={{padding: '10px', backgroundColor: 'rgba(239, 68, 68, 0.1)', color: 'var(--danger-color)', borderRadius: '6px', marginBottom: '1rem', textAlign: 'center', fontSize: '0.9rem'}}>
            {error}
          </div>
        )}

        <form onSubmit={handleLogin}>
          <div className="form-group">
            <label className="form-label">Username</label>
            <input 
              type="text" 
              className="form-input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>
          
          <div className="form-group">
            <label className="form-label">Password</label>
            <input 
              type="password" 
              className="form-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          
          <button type="submit" className="btn btn-primary" style={{width: '100%', marginTop: '1rem'}} disabled={loading}>
            {loading ? 'Authenticating...' : 'Login'}
          </button>
        </form>
      </div>
    </div>
  )
}
