import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getRubric, listDecks, saveHumanScores } from '../api'

export default function ScoreDeck() {
  const { deckId } = useParams()
  const navigate = useNavigate()
  const [rubric, setRubric] = useState(null)
  const [deck, setDeck] = useState(null)
  const [scores, setScores] = useState({})
  const [sourceUrl, setSourceUrl] = useState('')
  const [synthetic, setSynthetic] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([getRubric(), listDecks()])
      .then(([rb, decks]) => {
        setRubric(rb)
        setDeck(decks.find((d) => d.id === deckId) || null)
      })
      .catch((e) => setError(e.message))
  }, [deckId])

  async function save() {
    setError('')
    try {
      await saveHumanScores(deckId, { scores, source_url: sourceUrl, synthetic })
      navigate('/evaluation')
    } catch (e) {
      setError(e.message)
    }
  }

  if (!rubric || !deck) {
    return <div className="card"><p className="muted">{error || 'Loading…'}</p></div>
  }
  const complete = rubric.criteria.every((c) => scores[c.id])
  const slideNumbers = Array.from({ length: deck.slides }, (_, i) => i + 1)

  return (
    <div className="card">
      <h1>Score: {deck.filename}</h1>
      <p className="muted">
        Score the deck yourself. No model output is shown on this page. Click a
        slide to open it larger.
      </p>
      <div className="grid">
        {slideNumbers.map((n) => (
          <a key={n} href={`/api/decks/${deckId}/slides/${n}`} target="_blank" rel="noreferrer">
            <img className="thumb" src={`/api/decks/${deckId}/slides/${n}`} alt={`Slide ${n}`} />
          </a>
        ))}
      </div>

      {rubric.criteria.map((c) => (
        <div className="criterion" key={c.id}>
          <strong>{c.name}</strong> <span className="muted">(weight {c.weight})</span>
          <p className="muted">1 = {c.low} · 5 = {c.high}</p>
          {[1, 2, 3, 4, 5].map((n) => (
            <label key={n} className="radio">
              <input
                type="radio"
                name={c.id}
                checked={scores[c.id] === n}
                onChange={() => setScores({ ...scores, [c.id]: n })}
              />{' '}
              {n}
            </label>
          ))}
        </div>
      ))}

      <p>
        <label>
          <input type="checkbox" checked={synthetic} onChange={(e) => setSynthetic(e.target.checked)} />{' '}
          This deck is synthetic (excluded from the results)
        </label>
      </p>
      <p>
        Public URL where this deck was published:{' '}
        <input value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} size={50} />
      </p>
      {error && <p className="error">{error}</p>}
      <button onClick={save} disabled={!complete}>Save my scores</button>
    </div>
  )
}