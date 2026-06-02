import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import Login from '@/pages/Login'
import Dashboard from '@/pages/Dashboard'
import Servers from '@/pages/Servers'
import Jobs from '@/pages/Jobs'
import Storage from '@/pages/Storage'
import Logs from '@/pages/Logs'
import Users from '@/pages/Users'
import Settings from '@/pages/Settings'
import AuditPage from '@/pages/Audit'
import RestoreHubPage from '@/pages/RestoreHub'
import LockedPage from '@/pages/Locked'
import AppLayout from '@/components/layout/AppLayout'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()
  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    )
  }
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/locked"
          element={
            <ProtectedRoute>
              <LockedPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="restore-hub" element={<RestoreHubPage />} />
          <Route path="servers" element={<Servers />} />
          <Route path="jobs" element={<Jobs />} />
          <Route path="storage" element={<Storage />} />
          <Route path="logs" element={<Logs />} />
          <Route path="users" element={<Users />} />
          <Route path="settings" element={<Settings />} />
          <Route path="audit" element={<AuditPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
