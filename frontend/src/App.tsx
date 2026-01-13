// frontend/src/App.tsx
import { Routes, Route } from 'react-router-dom'
import { useEffect } from 'react'
import { useAuthStore } from './stores/authStore'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import Templates from './pages/Templates'
import Ranges from './pages/Ranges'
import RangeDetail from './pages/RangeDetail'
import ExecutionConsole from './pages/ExecutionConsole'
import ImageCache from './pages/ImageCache'
import UserManagement from './pages/UserManagement'
import ProtectedRoute from './components/common/ProtectedRoute'
import Layout from './components/layout/Layout'

function App() {
  const { checkAuth, token } = useAuthStore()

  useEffect(() => {
    if (token) {
      checkAuth()
    }
  }, [])

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <Layout>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/templates" element={<Templates />} />
                <Route path="/ranges" element={<Ranges />} />
                <Route path="/ranges/:id" element={<RangeDetail />} />
                <Route path="/execution/:rangeId" element={<ExecutionConsole />} />
                <Route path="/cache" element={<ImageCache />} />
                <Route path="/users" element={<UserManagement />} />
                <Route path="/artifacts" element={<div>Artifacts - Coming Soon</div>} />
              </Routes>
            </Layout>
          </ProtectedRoute>
        }
      />
    </Routes>
  )
}

export default App
