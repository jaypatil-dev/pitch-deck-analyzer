import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listFiles, uploadDeck } from '../api'

export default function DataRoom() {
  const [files, setFiles] = useState(null)
  const [file, setFile] = useState(null)
  const [inputKey, setInputKey] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  function refresh() {
    listFiles().then(setFiles).catch((e) => setError(e.message))
  }
  useEffect(() => {
    refresh()
  }, [])

  async function upload() {
    setBusy(true)
    setError('')
    try {
      await uploadDeck(file)
      setFile(null)
      setInputKey((k) => k + 1) // clears the file box
      refresh()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card">
      <h1>Data Room</h1>
      <p className="muted">
        Upload decks, then create a separate tracked link for each person you share them with.
      </p>
      <input
        key={inputKey}
        type="file"
        accept=".pdf,application/pdf"
        disabled={busy}
        onChange={(e) => setFile(e.target.files[0] || null)}
      />
      <button onClick={upload} disabled={!file || busy}>
        {busy ? 'Uploading…' : 'Upload'}
      </button>
      {error && <p className="error">{error}</p>}

      {files && files.length === 0 && <p className="muted">No files yet.</p>}
      {files && files.length > 0 && (
        <table>
          <thead>
            <tr><th>File</th><th>Pages</th><th>Links</th><th>Views</th><th>Uploaded</th><th></th></tr>
          </thead>
          <tbody>
            {files.map((f) => (
              <tr key={f.id}>
                <td>{f.filename}</td>
                <td>{f.slides}</td>
                <td>{f.links}</td>
                <td>{f.views}</td>
                <td>{f.uploaded_at.replace('T', ' ')}</td>
                <td><Link to={`/dataroom/${f.id}`}>Open</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}