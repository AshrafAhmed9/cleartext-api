import { useState } from 'react'
import axios from 'axios'
import './index.css'

const API = 'http://localhost:8000'

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('token') || '')
  const [view, setView] = useState('comment')

  if (!token) return <Login setToken={setToken} />

  return (
    <>
      <nav>
        <div className="logo">ClearText</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
            Status: <span style={{ color: '#22c55e', fontWeight: 600 }}>Online</span>
          </span>
          <button className="logout-btn" onClick={() => {
            localStorage.removeItem('token')
            setToken('')
          }}>Logout</button>
        </div>
      </nav>

      <div className="container">
        <div className="tabs">
          <button className={`tab ${view === 'comment' ? 'active' : ''}`} onClick={() => setView('comment')}>
            Comment Analysis
          </button>
          <button className={`tab ${view === 'youtube' ? 'active' : ''}`} onClick={() => setView('youtube')}>
            YouTube Analysis
          </button>
        </div>

        {view === 'comment' ? <CommentPanel token={token} /> : <YoutubePanel token={token} />}
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
        <p>ClearText API — Toxic Comment Detection</p>
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
      
      // Poll for result
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

function YoutubePanel({ token }) {
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  async function analyze() {
    if (!url.trim()) return
    setLoading(true)
    setError('')
    setResult(null)

    try {
      const headers = { Authorization: `Bearer ${token}` }
      const { data } = await axios.post(`${API}/analyze/youtube`, { url }, { headers })
      setResult(data)
    } catch (e) {
      setError(e.response?.data?.detail || 'Something went wrong.')
    }
    setLoading(false)
  }

  const ins = result?.insights

  return (
    <div className="card">
      <h3>Analyze a YouTube Video</h3>
      <p>Enter a YouTube URL to analyze 100 comments and get AI-powered insights.</p>
      <label>YouTube URL</label>
      <input
        value={url}
        onChange={e => setUrl(e.target.value)}
        placeholder="https://www.youtube.com/watch?v=..."
      />
      <button className="btn" onClick={analyze} disabled={loading}>
        {loading ? <><span className="spinner" />Analyzing 100 comments...</> : 'Analyze Video'}
      </button>
      {error && <div className="error">{error}</div>}

      {result && (
        <div className="result-box">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <strong>Video Report</strong>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <span className={`badge ${result.community_rating}`}>{result.community_rating}</span>
              <span className={`badge ${ins.overall_sentiment}`}>{ins.overall_sentiment}</span>
            </div>
          </div>

          <div className="stat-row">
            <div className="stat">
              <div className="value">{result.comments_analyzed}</div>
              <div className="label">Comments</div>
            </div>
            <div className="stat">
              <div className="value" style={{ color: '#dc2626' }}>{result.toxic_count}</div>
              <div className="label">Toxic</div>
            </div>
            <div className="stat">
              <div className="value" style={{ color: '#16a34a' }}>{result.non_toxic_count}</div>
              <div className="label">Safe</div>
            </div>
            <div className="stat">
              <div className="value">{result.toxicity_rate_percent}%</div>
              <div className="label">Toxicity Rate</div>
            </div>
          </div>

          <div className="section-title">Summary</div>
          <p style={{ fontSize: '0.9rem', lineHeight: 1.6, color: '#334155' }}>{ins.summary}</p>

          <div className="section-title">Positive Themes</div>
          <div className="tag-list">
            {ins.positive_themes?.map((t, i) => <span key={i} className="tag green">{t}</span>)}
          </div>

          {ins.negative_themes?.length > 0 && <>
            <div className="section-title">Negative Themes</div>
            <div className="tag-list">
              {ins.negative_themes.map((t, i) => <span key={i} className="tag red">{t}</span>)}
            </div>
          </>}

          <div className="section-title">Improvements for Creator</div>
          <div className="tag-list">
            {ins.improvements?.map((t, i) => <span key={i} className="tag blue">{t}</span>)}
          </div>
        </div>
      )}
    </div>
  )
}
