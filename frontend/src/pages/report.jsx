import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getRun, getRubric, getFeedback} from '../api'
import SlideCard from '../components/slide_card'

function quoteBadge(value) {
  if (value === true) return <span className="badge ok">quote found</span>
  if (value === false)
    return <span className="badge warn">quote not found: check by eye</span>
  return <span className="badge">no quote given</span>
}
//   const [feedback, setFeedback] = useState({})

export default function Report() {
  const { runId } = useParams()
  const [run, setRun] = useState(null)
  const [rubric, setRubric] = useState(null)
  const [error, setError] = useState('')
  const [feedback, setFeedback] = useState({})
  useEffect(() => {
    Promise.all([getRun(runId), getRubric(), getFeedback(runId)])
      .then(([r, rb, fb]) => {
        setRun(r)
        setRubric(rb)
        setFeedback(fb)
      })
      .catch((e) => setError(e.message))
  }, [runId])

  if (error) {
    return <div className="card"><p className="error">{error}</p></div>
  }
  if (!run || !rubric) {
    return <div className="card"><p className="muted">Loading…</p></div>
  }
  if (run.status !== 'done') {
    return (
      <div className="card">
        <p className="error">This run failed: {run.error}</p>
        <Link to="/reports">← All reports</Link>
      </div>
    )
  }

  const record = run.result
  const results = Object.fromEntries(record.result.criteria.map((c) => [c.id, c]))
  const checks = record.quote_checks
  const totalWeight = rubric.criteria.reduce((sum, c) => sum + c.weight, 0)
//   const [feedback, setFeedback] = useState({})

  // Points this criterion could add if it moved up to 5
  const gain = (def, score) => ((def.weight * (5 - score)) / 4 / totalWeight) * 100

  const toImprove = rubric.criteria
    .filter((def) => results[def.id] && results[def.id].score < 5)
    .map((def) => ({ def, c: results[def.id], gain: gain(def, results[def.id].score) }))
    .sort((a, b) => b.gain - a.gain)
  const potential = toImprove.reduce((sum, item) => sum + item.gain, 0)

  return (
    <>
      <div className="card">
        <Link to="/reports">← All reports</Link>
        <h1>{run.filename}</h1>
        <p className="muted">
          Run {run.id} · {run.model} · {run.saved_at.replace('T', ' ')} ·{' '}
          {run.total_seconds} s
        </p>
        <p className="big">
          {run.percent}% <span className="muted">match</span>
        </p>
        <div className="bar">
          <div className="fill" style={{ width: `${run.percent}%` }} />
        </div>
        <p className="muted">
          How it is computed: each 1–5 score is stretched to 0–100% (1 = 0%,
          5 = 100%), multiplied by the criterion's weight, and averaged. The
          weights are provisional (the author's choice).
        </p>
        <p>
          <strong>Model's summary:</strong> {record.result.summary}
        </p>
      </div>

      <div className="card">
        <h2>Scores by criterion</h2>
        {rubric.criteria.map((def) => {
          const c = results[def.id]
          if (!c) return null
          return (
            <div className="criterion" key={def.id}>
              <div className="criterion-head">
                <strong>{def.name}</strong>
                <span className="score">{c.score}/5</span>
              </div>
              <p className="muted">
                Weight {def.weight} ·{' '}
                {c.slide ? `slide ${c.slide}` : 'no slide cited'}
              </p>
              {c.evidence && <blockquote>{c.evidence}</blockquote>}
              {quoteBadge(checks[def.id])}
              <p>{c.justification}</p>
            </div>
          )
        })}
      </div>
      <h2 className="section-title">Slide by slide</h2>
      {record.notes.map((note) => (
        <SlideCard
          key={note.slide}
          runId={run.id}
          deckId={run.deck_id}
          note={note}
          saved={feedback[String(note.slide)]}
        />
      ))}
      <div className="card">
        <h2>How to raise the match</h2>
        {toImprove.length === 0 ? (
          <p>Every criterion scored 5 in this run, so nothing is suggested.</p>
        ) : (
          <>
            <p className="muted">
              Ranked by the percentage points each fix could add (weight × score
              gap). Together: up to +{potential.toFixed(1)} points.
            </p>
            <ol>
              {toImprove.map(({ def, c, gain: g }) => (
                <li key={def.id}>
                  <strong>{def.name}</strong> (now {c.score}/5, up to +
                  {g.toFixed(1)} pts): {c.fix}
                </li>
              ))}
            </ol>
          </>
        )}
      </div>

      
    </>
  )
}