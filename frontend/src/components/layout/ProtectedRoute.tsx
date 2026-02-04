import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requireManager?: boolean;
  requireAdmin?: boolean;
}

export function ProtectedRoute({
  children,
  requireManager = false,
  requireAdmin = false,
}: ProtectedRouteProps) {
  const { isAuthenticated, isManager, isAdmin } = useAuthStore();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requireAdmin && !isAdmin()) {
    return <Navigate to="/dashboard" replace />;
  }

  if (requireManager && !isManager()) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}
