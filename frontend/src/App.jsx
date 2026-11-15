import { BrowserRouter, Routes, Route } from 'react-router-dom'
import AdminLayout from './components/admin_layout'
import Analyzer from './pages/analyzer'
import DataRoom from './pages/data_room'
import DataRoomFile from './pages/data_room_file'
import Reports from './pages/reports'
import Report from './pages/report'
import Evaluation from './pages/evaluation'
import ScoreDeck from './pages/score_deck'
import Viewer from './pages/viewer'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/v/:token" element={<Viewer />} />
        <Route element={<AdminLayout />}>
          <Route path="/" element={<Analyzer />} />
          <Route path="/dataroom" element={<DataRoom />} />
          <Route path="/dataroom/:deckId" element={<DataRoomFile />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/report/:runId" element={<Report />} />
          <Route path="/evaluation" element={<Evaluation />} />
          <Route path="/evaluation/score/:deckId" element={<ScoreDeck />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}