import { Link } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

export function Welcome() {
  const { isAuthenticated } = useAuthStore();

  return (
    <div className="min-h-screen bg-gradient-to-br from-obatek to-obatek-dark flex flex-col items-center justify-center p-4">
      <div className="text-center text-white mb-8">
        <h1 className="text-5xl font-bold mb-4">OBATEK</h1>
        <p className="text-xl text-white/80">Worker Portal</p>
      </div>

      <div className="bg-white rounded-lg shadow-xl p-8 max-w-md w-full">
        <h2 className="text-2xl font-semibold text-gray-800 mb-6 text-center">
          Welcome
        </h2>

        {isAuthenticated ? (
          <Link
            to="/dashboard"
            className="block w-full bg-obatek text-white text-center py-3 px-4 rounded-lg font-medium hover:bg-obatek-dark transition-colors"
          >
            Go to Dashboard
          </Link>
        ) : (
          <div className="space-y-4">
            <Link
              to="/login"
              className="block w-full bg-obatek text-white text-center py-3 px-4 rounded-lg font-medium hover:bg-obatek-dark transition-colors"
            >
              Sign In
            </Link>
            <Link
              to="/register"
              className="block w-full border-2 border-obatek text-obatek text-center py-3 px-4 rounded-lg font-medium hover:bg-obatek/5 transition-colors"
            >
              Create Account
            </Link>
          </div>
        )}

        <Link
          to="/quote"
          className="block w-full mt-4 text-center py-3 px-4 rounded-lg font-medium text-obatek hover:bg-obatek/5 transition-colors border border-dashed border-obatek/40"
        >
          Get a Free Estimate
        </Link>
      </div>

      <p className="text-white/60 text-sm mt-8">
        Timesheet and Job Management
      </p>
    </div>
  );
}
