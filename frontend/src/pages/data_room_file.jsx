import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { createLink, listFiles, listLinks, listViews, setLinkActive } from '../api'

export default function DataRoomFile() {
  const { deckId } = useParams()
  const [file, setFile] = useState(null)
  const [links, setLinks] = useState([])
  const [views, setViews] = useState([])
  const [label, setLabel] = useState('')
  const [error, setError] = useState('')

  function refresh() {
    Promise.all([listFiles(), listLinks(deckId), listViews(deckId)])
      .then(([files, l, v]) => {
        setFile(files.find((f) => f.id === deckId) || null)
        setLinks(l)
        setViews(v)
      })
      .catch((e) => setError(e.message))
  }
  useEffect(() => {
    refresh()
  }, [deckId])

  const urlFor = (token) => `${window.location.origin}/v/${token}`

  async function addLink() {
    setError('')
    try {
      await createLink(deckId, label)
      setLabel('')
      refresh()
    } catch (e) {
      setError(e.message)
    }
  }

  async function toggle(token, active) {
    setError('')
    try {
      await setLinkActive(token, active)
      refresh()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <>
      <div className="card">
        <Link to="/dataroom">← Data Room</Link>
        <h1>{file ? file.filename : 'File'}</h1>
        {error && <p className="error">{error}</p>}
        <button onClick={refresh}>Refresh</button>
      </div>

      <div className="card">
        <h2>Links</h2>
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="Label, e.g. Investor A"
        />
        <button onClick={addLink} disabled={!label.trim()}>Create link</button>
        {links.length === 0 ? (
          <p className="muted">No links yet.</p>
        ) : (
          <table>
            <thead>
              <tr><th>Label</th><th>Link</th><th>Views</th><th>Status</th><th></th></tr>
            </thead>
            <tbody>
              {links.map((l) => (
                <tr key={l.token}>
                  <td>{l.label}</td>
                  <td>
                    <input className="link-input" readOnly value={urlFor(l.token)} />
                  </td>
                  <td>{l.views}</td>
                  <td>{l.active ? 'active' : 'disabled'}</td>
                  <td>
                    <button onClick={() => navigator.clipboard.writeText(urlFor(l.token))}>
                      Copy
                    </button>{' '}
                    <a href={urlFor(l.token)} target="_blank" rel="noreferrer">Open</a>{' '}
                    <button onClick={() => toggle(l.token, !l.active)}>
                      {l.active ? 'Disable' : 'Enable'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h2>Views</h2>
        {views.length === 0 ? (
          <p className="muted">No views yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>When (server time)</th><th>Link</th><th>Browser</th><th>OS</th>
                <th>Device</th><th>Total</th><th>Seconds per page</th>
              </tr>
            </thead>
            <tbody>
              {views.map((v, i) => (
                <tr key={i}>
                  <td>{v.started_at.replace('T', ' ')}</td>
                  <td>{v.label}</td>
                  <td>{v.browser}</td>
                  <td>{v.os}</td>
                  <td>{v.device}</td>
                  <td>{v.total_seconds} s</td>
                  <td>{v.pages.map((p) => `p${p.page}: ${p.seconds}s`).join(' · ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="muted">Times are approximate (about ±5 s per page).</p>
      </div>
    </>
  )
}