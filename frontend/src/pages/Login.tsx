import { useState } from 'react';
import { Link, Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useAuthStore } from '../store/authStore';

export function Login() {
  const { isAuthenticated } = useAuthStore();
  const { login, isLoggingIn, loginError } = useAuth();
  const location = useLocation();
  const passwordReset = location.state?.passwordReset;
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login({ username, password });
    } catch {
      // Error handled by mutation
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-obatek to-obatek-dark flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl p-8 max-w-md w-full">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-obatek">OBATEK</h1>
          <p className="text-gray-600 mt-2">Sign in to your account</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {passwordReset && (
            <div className="bg-green-50 text-green-700 p-3 rounded-lg text-sm">
              Your password has been reset successfully. Sign in with your new password.
            </div>
          )}

          {loginError && (
            <div className="bg-red-50 text-red-600 p-3 rounded-lg text-sm">
              Invalid username or password
            </div>
          )}

          <div>
            <label htmlFor="username" className="block text-sm font-medium text-gray-700 mb-1">
              Username
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none transition-shadow"
              placeholder="Enter your username"
              required
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none transition-shadow"
              placeholder="Enter your password"
              required
            />
          </div>

          <div className="flex justify-end">
            <Link to="/forgot-password" className="text-sm text-obatek hover:underline">
              Forgot password?
            </Link>
          </div>

          <button
            type="submit"
            disabled={isLoggingIn}
            className="w-full bg-obatek text-white py-3 px-4 rounded-lg font-medium hover:bg-obatek-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoggingIn ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <p className="text-center text-gray-600 mt-6">
          Don't have an account?{' '}
          <Link to="/register" className="text-obatek hover:underline font-medium">
            Create one
          </Link>
        </p>

        <Link
          to="/"
          className="block text-center text-gray-500 hover:text-gray-700 mt-4 text-sm"
        >
          Back to home
        </Link>
      </div>
    </div>
  );
}
