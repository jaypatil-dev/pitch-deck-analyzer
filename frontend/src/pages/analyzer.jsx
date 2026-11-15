import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getJob, listDecks, startAnalysis, uploadDeck } from '../api'

const LABELS = {
  queued: 'Starting…',
  reading: 'Reading slides',
  scoring: 'Scoring against the rubric',
  done: 'Done',
  failed: 'Failed',
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

export default function Analyzer() {
  const [file, setFile] = useState(null)
  const [inputKey, setInputKey] = useState(0) // changing it empties the file box
  const [decks, setDecks] = useState([])
  const [deckChoice, setDeckChoice] = useState('')
  const [busy, setBusy] = useState(false)
  const [job, setJob] = useState(null)
  const [error, setError] = useState('')
  const [elapsed, setElapsed] = useState(0)

  function refreshDecks() {
    listDecks().then(setDecks).catch(() => {})
  }
  useEffect(() => {
    refreshDecks()
  }, [])

  function chooseFile(e) {
    setFile(e.target.files[0] || null)
    setDeckChoice('') // a new file replaces the Data Room choice
  }

  function chooseDeck(e) {
    setDeckChoice(e.target.value)
    setFile(null) // a Data Room choice replaces the file
    setInputKey((k) => k + 1) // empties the file box
  }

  const canStart = (file !== null || deckChoice !== '') && !busy

  async function handleAnalyze() {
    setBusy(true)
    setError('')
    setJob(null)
    setElapsed(0)
    const started = Date.now()
    try {
      const deckId = file ? (await uploadDeck(file)).deck_id : deckChoice
      const { job_id } = await startAnalysis(deckId)
      while (true) {
        const current = await getJob(job_id)
        setJob(current)
        setElapsed(Math.round((Date.now() - started) / 1000))
        if (current.status === 'done' || current.status === 'failed') break
        await sleep(1500)
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
      refreshDecks()
    }
  }

  const percentRead =
    job && job.slides_total ? Math.round((job.slides_done / job.slides_total) * 100) : 0

  return (
    <div className="card">
      <h1>Pitch Deck Analyzer</h1>
      <p className="muted">Upload a PDF deck.</p>

      <p>
        Pick from the Data Room:{' '}
        <select value={deckChoice} onChange={chooseDeck} disabled={busy}>
          <option value="">(none)</option>
          {decks.map((d) => (
            <option key={d.id} value={d.id}>
              {d.filename}
            </option>
          ))}
        </select>
      </p>

      <p className="muted">or upload a new PDF:</p>
      <input
        key={inputKey}
        type="file"
        accept=".pdf,application/pdf"
        disabled={busy}
        onChange={chooseFile}
      />
      <button onClick={handleAnalyze} disabled={!canStart}>
        {busy ? 'Working…' : 'Upload and analyze'}
      </button>

      {error && <p className="error">{error}</p>}

      {job && (
        <div className="status">
          <p>
            <strong>{LABELS[job.status] || job.status}</strong> · {elapsed} s
          </p>
          <div className="bar">
            <div className="fill" style={{ width: `${percentRead}%` }} />
          </div>
          <p className="muted">
            {job.slides_done} of {job.slides_total} slides read
          </p>

          {job.status === 'done' && (
            <>
              <p className="result">
                Match: {job.result.percent}%{' '}
                <span className="muted">
                  (run {job.job_id}, {job.result.total_seconds} s)
                </span>
              </p>
              <p>
                <Link to={`/report/${job.job_id}`}>View full report →</Link>
              </p>
              <p className="muted">
                Prototype: this score comes from a language model and can differ
                between runs.
              </p>
            </>
          )}
          {job.status === 'failed' && (
            <p className="error">Analysis failed: {job.error}</p>
          )}
        </div>
      )}
    </div>
  )
}