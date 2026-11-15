import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listRuns } from '../api'

export default function Reports() {
  const [runs, setRuns] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    listRuns()
      .then(setRuns)
      .catch((e) => setError(e.message))
  }, [])

  if (error) {
    return <div className="card"><p className="error">{error}</p></div>
  }
  if (!runs) {
    return <div className="card"><p className="muted">Loading…</p></div>
  }

  return (
    <div className="card">
      <h1>Saved reports</h1>
      {runs.length === 0 && (
        <p className="muted">No runs yet. Analyze a deck first.</p>
      )}
      <table>
        <thead>
          <tr>
            <th>Deck</th>
            <th>When</th>
            <th>Status</th>
            <th>Match</th>
            <th>Time</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr key={r.id}>
              <td>{r.filename}</td>
              <td>{r.saved_at.replace('T', ' ')}</td>
              <td>{r.status}</td>
              <td>{r.percent == null ? '–' : `${r.percent}%`}</td>
              <td>{r.total_seconds} s</td>
              <td>
                {r.status === 'done' ? (
                  <Link to={`/report/${r.id}`}>Open</Link>
                ) : (
                  r.error
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}