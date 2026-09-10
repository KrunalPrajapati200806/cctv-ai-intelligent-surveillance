import { Routes, Route } from 'react-router-dom'

import Header from './components/Header/Header'

import Dashboard from './pages/Dashboard/Dashboard'
import RecordedVideoPage from './pages/RecordedVideo/RecordedVideo'
import IncidentsPage from './pages/Incidents/IncidentsPage'

function App() {
  return (
    <div className="app">
      <Header />

      <Routes>
        <Route
          path="/"
          element={<Dashboard />}
        />

        <Route
          path="/incidents"
          element={<IncidentsPage />}
        />

        <Route
          path="/recorded-analysis"
          element={<RecordedVideoPage />}
        />
      </Routes>
    </div>
  )
}

export default App
