import { Routes, Route, Navigate } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import { ProtectedRoute } from './components/layout/ProtectedRoute';

// Pages
import { Welcome } from './pages/Welcome';
import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { ForgotPassword } from './pages/ForgotPassword';
import { ResetPassword } from './pages/ResetPassword';
import { GetEstimate } from './pages/GetEstimate';
import { Dashboard } from './pages/Dashboard';
import { ManagerDashboard } from './pages/ManagerDashboard';
import { Calendar } from './pages/Calendar';
import { PurchaseList } from './pages/PurchaseList';
import { Inspections } from './pages/Inspections';
import { CreateInspection } from './pages/CreateInspection';
import { ViewInspection } from './pages/ViewInspection';
import { Invoices } from './pages/Invoices';
import { AdminDashboard } from './pages/AdminDashboard';
import { AdminEstimate } from './pages/AdminEstimate';
import { ViewTimesheet } from './pages/ViewTimesheet';
import { CompletedJobs } from './pages/CompletedJobs';
import { PaidTimesheets } from './pages/PaidTimesheets';

function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/" element={<Welcome />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/quote" element={<GetEstimate />} />

      {/* Protected routes */}
      <Route
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/calendar" element={<Calendar />} />
        <Route path="/purchases" element={<PurchaseList />} />
        <Route path="/inspections" element={<Inspections />} />
        <Route path="/inspections/create/:jobId/:type" element={<CreateInspection />} />
        <Route path="/inspections/:id" element={<ViewInspection />} />

        {/* Manager-only routes */}
        <Route
          path="/manager"
          element={
            <ProtectedRoute requireManager>
              <ManagerDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/completed-jobs"
          element={
            <ProtectedRoute requireManager>
              <CompletedJobs />
            </ProtectedRoute>
          }
        />
        <Route
          path="/paid-timesheets"
          element={
            <ProtectedRoute requireManager>
              <PaidTimesheets />
            </ProtectedRoute>
          }
        />
        <Route path="/timesheets/:id" element={<ViewTimesheet />} />
        <Route
          path="/invoices"
          element={
            <ProtectedRoute requireManager>
              <Invoices />
            </ProtectedRoute>
          }
        />

        {/* Admin-only routes */}
        <Route
          path="/admin"
          element={
            <ProtectedRoute requireAdmin>
              <AdminDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/estimate"
          element={
            <ProtectedRoute requireAdmin>
              <AdminEstimate />
            </ProtectedRoute>
          }
        />
      </Route>

      {/* Catch all */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
