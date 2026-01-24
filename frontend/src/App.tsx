// frontend/src/App.tsx
import { Routes, Route } from 'react-router-dom'
import { useEffect } from 'react'
import { useAuthStore } from './stores/authStore'
import { useSystemStore } from './stores/systemStore'
import { NotificationProvider } from './providers/NotificationProvider'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import VMLibrary from './pages/VMLibrary'
import Ranges from './pages/Ranges'
import RangeDetail from './pages/RangeDetail'
import RangeWizardPage from './pages/RangeWizardPage'
import ExecutionConsole from './pages/ExecutionConsole'
import StandaloneConsole from './pages/StandaloneConsole'
import Blueprints from './pages/Blueprints'
import BlueprintDetail from './pages/BlueprintDetail'
import TrainingScenarios from './pages/TrainingScenarios'
import StudentLab from './pages/StudentLab'
import ImageCache from './pages/ImageCache'
import UserManagement from './pages/UserManagement'
import Admin from './pages/Admin'
import ContentLibrary from './pages/ContentLibrary'
import ContentEditor from './pages/ContentEditor'
import TrainingEvents from './pages/TrainingEvents'
import TrainingEventDetail from './pages/TrainingEventDetail'
import ProtectedRoute from './components/common/ProtectedRoute'
import Layout from './components/layout/Layout'

function App() {
  const { checkAuth, token } = useAuthStore()
  const fetchSystemInfo = useSystemStore((state) => state.fetchSystemInfo)

  useEffect(() => {
    if (token) {
      checkAuth()
    }
  }, [])

  useEffect(() => {
    fetchSystemInfo()
  }, [fetchSystemInfo])

  return (
    <NotificationProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
      {/* Standalone console - protected but no layout (for pop-out windows) */}
      <Route
        path="/console/:vmId"
        element={
          <ProtectedRoute>
            <StandaloneConsole />
          </ProtectedRoute>
        }
      />
      {/* Student Lab - protected but no layout (immersive experience) */}
      <Route
        path="/lab/:rangeId"
        element={
          <ProtectedRoute>
            <StudentLab />
          </ProtectedRoute>
        }
      />
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <Layout>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/vm-library" element={<VMLibrary />} />
                <Route path="/ranges" element={<Ranges />} />
                <Route path="/ranges/new" element={<RangeWizardPage />} />
                <Route path="/ranges/:id" element={<RangeDetail />} />
                <Route path="/blueprints" element={<Blueprints />} />
                <Route path="/blueprints/:id" element={<BlueprintDetail />} />
                <Route path="/scenarios" element={<TrainingScenarios />} />
                <Route path="/execution/:rangeId" element={<ExecutionConsole />} />
                <Route path="/cache" element={<ImageCache />} />
                <Route path="/users" element={<UserManagement />} />
                <Route path="/admin" element={<Admin />} />
                <Route path="/content" element={<ContentLibrary />} />
                <Route path="/content/:id" element={<ContentEditor />} />
                <Route path="/events" element={<TrainingEvents />} />
                <Route path="/events/:id" element={<TrainingEventDetail />} />
                <Route path="/artifacts" element={<div>Artifacts - Coming Soon</div>} />
              </Routes>
            </Layout>
          </ProtectedRoute>
        }
      />
      </Routes>
    </NotificationProvider>
  )
}

export default App
