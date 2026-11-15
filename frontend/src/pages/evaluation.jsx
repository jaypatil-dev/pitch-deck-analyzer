import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getEvaluation, getJob, listDecks, startAnalysis } from '../api'

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

export default function Evaluation() {
  const [decks, setDecks] = useState([])
  const [results, setResults] = useState(null)
  const [busy, setBusy] = useState(null)
  const [message, setMessage] = useState('')

  function refresh() {
    Promise.all([listDecks(), getEvaluation()])
      .then(([d, r]) => {
        setDecks(d)
        setResults(r)
      })
      .catch((e) => setMessage(e.message))
  }
  useEffect(() => {
    refresh()
  }, [])

  async function runMore(deckId, times) {
    setBusy(deckId)
    try {
      for (let i = 1; i <= times; i++) {
        setMessage(`Run ${i} of ${times}…`)
        const { job_id } = await startAnalysis(deckId)
        while (true) {
          const job = await getJob(job_id)
          if (job.status === 'failed') throw new Error(`Run failed: ${job.error}`)
          if (job.status === 'done') break
          await sleep(1500)
        }
      }
      setMessage('Done')
    } catch (e) {
      setMessage(e.message)
    } finally {
      setBusy(null)
      refresh()
    }
  }

  const o = results?.overall
  return (
    <>
      <div className="card">
        <h1>Evaluation</h1>
        <p className="muted">
          Score each deck in your PDF viewer first, then upload it on the Analyzer
          page and enter your scores here before opening its report.
        </p>
        {message && <p className="muted">{message}</p>}
        <table>
          <thead>
            <tr><th>Deck</th><th>Slides</th><th>Runs</th><th>Your scores</th><th></th></tr>
          </thead>
          <tbody>
            {decks.map((d) => (
              <tr key={d.id}>
                <td>{d.filename}</td>
                <td>{d.slides}</td>
                <td>{d.runs}</td>
                <td>
                  <Link to={`/evaluation/score/${d.id}`}>
                    {d.human_scored ? 'Re-score' : 'Score'}
                  </Link>
                </td>
                <td>
                  <button onClick={() => runMore(d.id, 2)} disabled={busy !== null}>
                    {busy === d.id ? 'Running…' : 'Run 2 more times'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {results && results.n_decks > 0 && (
        <>
          <div className="card">
            <h2>Agreement with your scores ({results.n_decks} decks, {o.n} score pairs)</h2>
            <table>
              <thead>
                <tr><th></th><th>Exact</th><th>Within ±1</th><th>MAE</th><th>Bias</th></tr>
              </thead>
              <tbody>
                <tr>
                  <td>Model</td><td>{o.exact_pct}%</td><td>{o.within1_pct}%</td>
                  <td>{o.mae}</td><td>{o.bias}</td>
                </tr>
                <tr>
                  <td>Baseline (always {results.baseline.constant})</td>
                  <td></td><td></td><td>{results.baseline.mae}</td><td></td>
                </tr>
              </tbody>
            </table>
            <p className="muted">
              MAE = average gap in score points. Bias above 0 means the model scores higher than you.
            </p>
            <p>
              Consistency across runs ({results.consistency.criteria_compared} criterion
              comparisons): identical score in {results.consistency.identical_pct ?? '–'}%,
              average spread {results.consistency.mean_score_range ?? '–'} points.
            </p>
          </div>

          <div className="card">
            <h2>By deck</h2>
            <table>
              <thead>
                <tr><th>Deck</th><th>Runs</th><th>You</th><th>Model (mean)</th><th>Model range</th></tr>
              </thead>
              <tbody>
                {results.decks.map((d) => (
                  <tr key={d.deck_id}>
                    <td>{d.filename}</td><td>{d.runs}</td>
                    <td>{d.human_percent}%</td>
                    <td>{d.mean_model_percent ?? '–'}%</td>
                    <td>{d.percent_range ?? '–'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card">
            <h2>By criterion</h2>
            <table>
              <thead>
                <tr><th>Criterion</th><th>Exact</th><th>MAE</th><th>Bias</th></tr>
              </thead>
              <tbody>
                {results.per_criterion.map((c) => (
                  <tr key={c.id}>
                    <td>{c.name}</td><td>{c.exact_pct}%</td><td>{c.mae}</td><td>{c.bias}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  )
}