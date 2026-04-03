import { useEffect, useState } from 'react';
import { useAuthStore } from '../store/authStore';
import { authApi } from '../api/auth';

interface AuthInitializerProps {
  children: React.ReactNode;
}

export function AuthInitializer({ children }: AuthInitializerProps) {
  const { isAuthenticated, token, logout, login } = useAuthStore();
  const [isChecking, setIsChecking] = useState(true);

  useEffect(() => {
    const validateAuth = async () => {
      // If there's a persisted auth state, validate the token
      if (isAuthenticated && token) {
        try {
          // Verify token is still valid by fetching current user
          const user = await authApi.me();
          // Token is valid, update user data
          login(token, user);
        } catch (error) {
          // Token is invalid or expired, clear auth state
          if (import.meta.env.DEV) {
            console.log('Token validation failed, logging out');
          }
          logout();
        }
      }
      setIsChecking(false);
    };

    validateAuth();
  }, []); // Only run once on mount

  // Show loading screen while checking auth
  if (isChecking) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-obatek to-obatek-dark flex items-center justify-center">
        <div className="text-white text-xl">Loading...</div>
      </div>
    );
  }

  return <>{children}</>;
}
