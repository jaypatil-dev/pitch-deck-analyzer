import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { getSession, login, logout } from '../api'

export default function AdminLayout() {
  const [session, setSession] = useState(null)
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    getSession()
      .then(setSession)
      .catch((e) => setError(e.message))
  }, [])

  async function submit(e) {
    e.preventDefault()
    setError('')
    try {
      await login(password)
      setSession({ required: true, authenticated: true })
    } catch (err) {
      setError(err.message)
    }
  }
  async function handleLogout() {
    await logout()
    setPassword('')
    setSession({ required: true, authenticated: false }) // shows the login form again
  }

  if (!session) {
    return (
      <main>
        <div className="card"><p className="muted">{error || 'Loading…'}</p></div>
      </main>
    )
  }

  if (session.required && !session.authenticated) {
    return (
      <main>
        <form className="card" onSubmit={submit}>
          <h1>Pitch Deck Analyzer</h1>
          <p className="muted">Admin password</p>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <button type="submit">Log in</button>
          {error && <p className="error">{error}</p>}
        </form>
      </main>
    )
  }

  return (
    <>
      <nav className="nav">
        <NavLink to="/" end>Analyzer</NavLink>
        <NavLink to="/dataroom">Data Room</NavLink>
        <NavLink to="/reports">Reports</NavLink>
        <NavLink to="/evaluation">Evaluation</NavLink>
        {session.required && (
          <button onClick={handleLogout}>Log out</button>
        )}
      </nav>
      <main>
        <Outlet />
      </main>
    </>
  )
}