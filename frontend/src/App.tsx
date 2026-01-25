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
import StudentPortal from './pages/StudentPortal'
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
                {/* Dashboard - accessible to admin, engineer, evaluator */}
                <Route path="/" element={
                  <ProtectedRoute requiredRoles={['admin', 'engineer', 'evaluator']}>
                    <Dashboard />
                  </ProtectedRoute>
                } />

                {/* Student Portal - accessible to students */}
                <Route path="/student-portal" element={
                  <ProtectedRoute requiredRoles={['student']}>
                    <StudentPortal />
                  </ProtectedRoute>
                } />

                {/* Range Engineering - admin and engineer only */}
                <Route path="/vm-library" element={
                  <ProtectedRoute requiredRoles={['admin', 'engineer']}>
                    <VMLibrary />
                  </ProtectedRoute>
                } />
                <Route path="/cache" element={
                  <ProtectedRoute requiredRoles={['admin', 'engineer']}>
                    <ImageCache />
                  </ProtectedRoute>
                } />
                <Route path="/blueprints" element={
                  <ProtectedRoute requiredRoles={['admin', 'engineer']}>
                    <Blueprints />
                  </ProtectedRoute>
                } />
                <Route path="/blueprints/:id" element={
                  <ProtectedRoute requiredRoles={['admin', 'engineer']}>
                    <BlueprintDetail />
                  </ProtectedRoute>
                } />
                <Route path="/scenarios" element={
                  <ProtectedRoute requiredRoles={['admin', 'engineer']}>
                    <TrainingScenarios />
                  </ProtectedRoute>
                } />
                <Route path="/ranges/new" element={
                  <ProtectedRoute requiredRoles={['admin', 'engineer']}>
                    <RangeWizardPage />
                  </ProtectedRoute>
                } />
                <Route path="/artifacts" element={
                  <ProtectedRoute requiredRoles={['admin', 'engineer']}>
                    <div>Artifacts - Coming Soon</div>
                  </ProtectedRoute>
                } />

                {/* Ranges - accessible to admin, engineer, evaluator */}
                <Route path="/ranges" element={
                  <ProtectedRoute requiredRoles={['admin', 'engineer', 'evaluator']}>
                    <Ranges />
                  </ProtectedRoute>
                } />
                <Route path="/ranges/:id" element={
                  <ProtectedRoute requiredRoles={['admin', 'engineer', 'evaluator']}>
                    <RangeDetail />
                  </ProtectedRoute>
                } />
                <Route path="/execution/:rangeId" element={
                  <ProtectedRoute requiredRoles={['admin', 'engineer', 'evaluator']}>
                    <ExecutionConsole />
                  </ProtectedRoute>
                } />

                {/* Content - accessible to admin, engineer, evaluator */}
                <Route path="/content" element={
                  <ProtectedRoute requiredRoles={['admin', 'engineer', 'evaluator']}>
                    <ContentLibrary />
                  </ProtectedRoute>
                } />
                <Route path="/content/:id" element={
                  <ProtectedRoute requiredRoles={['admin', 'engineer', 'evaluator']}>
                    <ContentEditor />
                  </ProtectedRoute>
                } />

                {/* Training Events - accessible to all authenticated users */}
                <Route path="/events" element={<TrainingEvents />} />
                <Route path="/events/:id" element={<TrainingEventDetail />} />

                {/* Admin only */}
                <Route path="/users" element={
                  <ProtectedRoute requiredRoles={['admin']}>
                    <UserManagement />
                  </ProtectedRoute>
                } />
                <Route path="/admin" element={
                  <ProtectedRoute requiredRoles={['admin']}>
                    <Admin />
                  </ProtectedRoute>
                } />
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
