import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { viewInfo, viewPing, viewStart } from '../api'

export default function Viewer() {
  const { token } = useParams()
  const [info, setInfo] = useState(null)
  const [error, setError] = useState('')
  const [page, setPage] = useState(1)
  const viewId = useRef(null)
  const started = useRef(false)
  const clock = useRef({ page: 1, last: Date.now() })

  // 1. Load the file info and register this visit (once)
  useEffect(() => {
    if (started.current) return
    started.current = true
    viewInfo(token)
      .then(async (i) => {
        const { view_id } = await viewStart(token)
        viewId.current = view_id
        clock.current = { page: 1, last: Date.now() }
        setInfo(i)
      })
      .catch((e) => setError(e.message))
  }, [token])

  // Send the time spent since the last report, for the page being viewed
  function flush() {
    const now = Date.now()
    const secs = (now - clock.current.last) / 1000
    clock.current.last = now
    if (viewId.current && secs > 0.2) {
      viewPing(token, viewId.current, clock.current.page, Math.min(secs, 30)).catch(() => {})
    }
  }

  // 2. Report regularly while the tab is visible
  useEffect(() => {
    if (!info) return
    const timer = setInterval(() => {
      if (document.visibilityState === 'visible') flush()
    }, 5000)
    function onVisibility() {
      if (document.visibilityState === 'hidden') flush()
      else clock.current.last = Date.now() // do not count the hidden time
    }
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('pagehide', flush)
    return () => {
      clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('pagehide', flush)
    }
  }, [info])

  function go(next) {
    if (!info || next < 1 || next > info.pages) return
    flush() // credit the time to the page we are leaving
    clock.current.page = next
    setPage(next)
  }

  if (error) return <div className="viewer"><p className="error">{error}</p></div>
  if (!info) return <div className="viewer"><p className="muted">Loading…</p></div>

  return (
    <div className="viewer">
      <h1>{info.filename}</h1>
      <img src={`/api/view/${token}/page/${page}`} alt={`Page ${page}`} />
      <div className="viewer-nav">
        <button onClick={() => go(page - 1)} disabled={page === 1}>← Previous</button>
        <span>Page {page} of {info.pages}</span>
        <button onClick={() => go(page + 1)} disabled={page === info.pages}>Next →</button>
      </div>
      <p className="muted">
        This link records your browser type, device type and how long you view each page.
      </p>
    </div>
  )
}