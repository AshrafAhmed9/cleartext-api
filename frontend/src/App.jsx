import { useState } from 'react'
import axios from 'axios'
import './index.css'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('token') || '')

  if (!token) return <Login setToken={setToken} />

  return (
    <>
      <nav>
        <div className="logo">ClearText</div>
        <button className="logout-btn" onClick={() => {
          localStorage.removeItem('token')
          setToken('')
        }}>Logout</button>
      </nav>
      <div className="container">
        <CommentPanel token={token} />
      </div>
    </>
  )
}

function Login({ setToken }) {
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('secret')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function login() {
    setLoading(true)
    setError('')
    try {
      const form = new URLSearchParams()
      form.append('username', username)
      form.append('password', password)
      const res = await axios.post(`${API}/token`, form)
      localStorage.setItem('token', res.data.access_token)
      setToken(res.data.access_token)
    } catch {
      setError('Wrong credentials. Try again.')
    }
    setLoading(false)
  }

  return (
    <div className="auth-wrap">
      <div className="card auth-card">
        <h2>Sign in</h2>
        <p>ClearText — Toxic Comment Detection</p>
        <label>Username</label>
        <input value={username} onChange={e => setUsername(e.target.value)} />
        <label>Password</label>
        <input type="password" value={password} onChange={e => setPassword(e.target.value)} />
        <button className="btn" onClick={login} disabled={loading}>
          {loading ? <><span className="spinner" />Signing in...</> : 'Sign in'}
        </button>
        {error && <div className="error">{error}</div>}
      </div>
    </div>
  )
}

function CommentPanel({ token }) {
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  async function analyze() {
    if (!text.trim()) return
    setLoading(true)
    setError('')
    setResult(null)

    try {
      const headers = { Authorization: `Bearer ${token}` }
      const { data } = await axios.post(`${API}/predict`, { text }, { headers })

      for (let i = 0; i < 30; i++) {
        await new Promise(r => setTimeout(r, 1000))
        const { data: r } = await axios.get(`${API}/result/${data.task_id}`, { headers })
        if (r.status === 'completed') { setResult(r); break }
        if (r.status === 'failed') { setError('Analysis failed.'); break }
      }
    } catch {
      setError('Something went wrong.')
    }
    setLoading(false)
  }

  return (
    <div className="card">
      <h3>Analyze a Comment</h3>
      <p>Submit any text to detect toxicity using BERT.</p>
      <label>Comment Text</label>
      <textarea
        value={text}
        onChange={e => setText(e.target.value)}
        placeholder="Type a comment here..."
      />
      <button className="btn" onClick={analyze} disabled={loading}>
        {loading ? <><span className="spinner" />Analyzing...</> : 'Analyze'}
      </button>
      {error && <div className="error">{error}</div>}

      {result && (
        <div className="result-box">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.8rem' }}>
            <strong>Result</strong>
            <span className={`badge ${result.prediction}`}>{result.prediction}</span>
          </div>
          <div className="stat-row">
            <div className="stat">
              <div className="value">{(result.confidence * 100).toFixed(1)}%</div>
              <div className="label">Confidence</div>
            </div>
            <div className="stat">
              <div className="value">{result.processing_time_ms?.toFixed(0)}ms</div>
              <div className="label">Process Time</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
