import { useState } from 'react'
import { makeFeedback } from '../api'

function renderContextWrite(w) {
  return (
    <>
      <strong>{w.headline}</strong>
      <ul>
        {w.body.map((line, i) => (
          <li key={i}>{line}</li>
        ))}
      </ul>
      {w.placeholders.length > 0 && (
        <p className="muted">You must supply: {w.placeholders.join('; ')}</p>
      )}
      {w.unverified_numbers?.length > 0 && (
        <p className="warn-text">
          Numbers not found elsewhere in the deck: {w.unverified_numbers.join(', ')}.
          Check them.
        </p>
      )}
      <p className="muted">{w.changes}</p>
      <button
        onClick={() => navigator.clipboard.writeText([w.headline, ...w.body].join('\n'))}
      >
        Copy text
      </button>
    </>
  )
}

function renderThemeWrite(w) {
  return (
    <>
      <p>{w.summary}</p>
      {w.palette.length > 0 && (
        <ul className="palette">
          {w.palette.map((c, i) => (
            <li key={i}>
              <span className="swatch" style={{ background: c.hex }} /> {c.role}:{' '}
              {c.hex} <span className="muted">{c.why}</span>
            </li>
          ))}
        </ul>
      )}
      <ol>
        {w.changes.map((t, i) => (
          <li key={i}>{t}</li>
        ))}
      </ol>
      <p className="muted">Colours are the model's suggestion, not measured from the slide.</p>
    </>
  )
}

function Section({ title, data, loading, error, onGenerate, write, renderWrite }) {
  return (
    <div className="fb-section">
      <div className="fb-head">
        <strong>{title}</strong>
        <button onClick={onGenerate} disabled={loading}>
          {loading ? 'Checking…' : data ? 'Check again' : 'Check this slide'}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {data && (
        <>
          <p>{data.verdict}</p>
          {data.issues.length === 0 ? (
            <p className="muted">No problems found.</p>
          ) : (
            <>
              <ul>
                {data.issues.map((issue, i) => (
                  <li key={i}>
                    <strong>Problem:</strong> {issue.problem}
                    {issue.evidence && <blockquote>{issue.evidence}</blockquote>}
                    <br />
                    <strong>Improve:</strong> {issue.improvement || issue.fix}
                  </li>
                ))}
              </ul>
              <div className="fb-write">
                <button onClick={write.onWrite} disabled={write.loading}>
                  {write.loading ? 'Writing…' : write.data ? 'AI write again' : 'AI write'}
                </button>
                {write.error && <p className="error">{write.error}</p>}
                {write.data && <div className="ai-box">{renderWrite(write.data)}</div>}
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}

export default function SlideCard({ runId, deckId, note, saved }) {
  const [data, setData] = useState({
    context: saved?.context || null,
    theme: saved?.theme || null,
    context_write: saved?.context_write || null,
    theme_write: saved?.theme_write || null,
  })
  const [loading, setLoading] = useState({})
  const [errors, setErrors] = useState({})

  async function generate(kind) {
    setLoading((prev) => ({ ...prev, [kind]: true }))
    setErrors((prev) => ({ ...prev, [kind]: '' }))
    try {
      const result = await makeFeedback(runId, note.slide, kind)
      setData((prev) => ({ ...prev, [kind]: result }))
    } catch (e) {
      setErrors((prev) => ({ ...prev, [kind]: e.message }))
    } finally {
      setLoading((prev) => ({ ...prev, [kind]: false }))
    }
  }

  function writeProps(kind) {
    return {
      data: data[kind],
      loading: !!loading[kind],
      error: errors[kind],
      onWrite: () => generate(kind),
    }
  }

  return (
    <div className="card">
      <div className="slide-top">
        <img
          className="thumb"
          src={`/api/decks/${deckId}/slides/${note.slide}`}
          alt={`Slide ${note.slide}`}
        />
        <h2>
          Slide {note.slide}: {note.title}
        </h2>
      </div>
      <Section
        title="Context (content)"
        data={data.context}
        loading={!!loading.context}
        error={errors.context}
        onGenerate={() => generate('context')}
        write={writeProps('context_write')}
        renderWrite={renderContextWrite}
      />
      <Section
        title="Theme (visual design)"
        data={data.theme}
        loading={!!loading.theme}
        error={errors.theme}
        onGenerate={() => generate('theme')}
        write={writeProps('theme_write')}
        renderWrite={renderThemeWrite}
      />
    </div>
  )
}