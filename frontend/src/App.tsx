// frontend/src/App.tsx
import { Routes, Route } from 'react-router-dom'

function App() {
  return (
    <div className="min-h-screen">
      <Routes>
        <Route path="/" element={
          <div className="flex items-center justify-center min-h-screen">
            <div className="text-center">
              <h1 className="text-4xl font-bold text-primary-600">CYROID</h1>
              <p className="mt-2 text-gray-600">Cyber Range Orchestrator In Docker</p>
            </div>
          </div>
        } />
      </Routes>
    </div>
  )
}

export default App
