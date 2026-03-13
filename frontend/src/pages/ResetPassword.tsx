import { useState } from 'react';
import { Link, useSearchParams, useNavigate } from 'react-router-dom';
import { authApi } from '../api/auth';

export function ResetPassword() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token');

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  if (!token) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-obatek to-obatek-dark flex items-center justify-center p-4">
        <div className="bg-white rounded-lg shadow-xl p-8 max-w-md w-full text-center">
          <h1 className="text-3xl font-bold text-obatek mb-4">OBATEK</h1>
          <div className="bg-red-50 text-red-600 p-4 rounded-lg mb-6">
            Invalid reset link. Please request a new password reset.
          </div>
          <Link to="/forgot-password" className="text-obatek hover:underline font-medium">
            Request New Reset Link
          </Link>
        </div>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setIsSubmitting(true);

    try {
      await authApi.resetPassword(token, password);
      navigate('/login', { state: { passwordReset: true } });
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(detail || 'Invalid or expired reset link. Please request a new one.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-obatek to-obatek-dark flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl p-8 max-w-md w-full">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-obatek">OBATEK</h1>
          <p className="text-gray-600 mt-2">Set your new password</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {error && (
            <div className="bg-red-50 text-red-600 p-3 rounded-lg text-sm">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
              New Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none transition-shadow"
              placeholder="Enter new password"
              required
              minLength={6}
            />
          </div>

          <div>
            <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 mb-1">
              Confirm Password
            </label>
            <input
              id="confirmPassword"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none transition-shadow"
              placeholder="Confirm new password"
              required
              minLength={6}
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-obatek text-white py-3 px-4 rounded-lg font-medium hover:bg-obatek-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting ? 'Resetting...' : 'Reset Password'}
          </button>
        </form>

        <Link
          to="/login"
          className="block text-center text-gray-500 hover:text-gray-700 mt-6 text-sm"
        >
          Back to Sign In
        </Link>
      </div>
    </div>
  );
}
