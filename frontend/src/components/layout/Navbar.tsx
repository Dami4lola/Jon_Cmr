import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';
import { cn } from '../../lib/utils';

export function Navbar() {
  const { user, isManager, isAdmin, logout } = useAuthStore();
  const location = useLocation();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navItems = [
    { href: '/dashboard', label: 'Dashboard' },
    { href: '/calendar', label: 'Calendar' },
    { href: '/purchases', label: 'Purchases' },
    { href: '/inspections', label: 'Inspections' },
  ];

  // Add manager-only items
  if (isManager()) {
    navItems.push({ href: '/manager', label: 'Manager' });
    navItems.push({ href: '/invoices', label: 'Invoices' });
  }

  // Add admin-only items
  if (isAdmin()) {
    navItems.push({ href: '/admin', label: 'Admin' });
    navItems.push({ href: '/admin/estimate', label: 'Estimate Calculator' });
  }

  return (
    <nav className="bg-obatek text-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/dashboard" className="flex items-center space-x-2">
            <span className="text-xl font-bold">OBATEK</span>
          </Link>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center space-x-1">
            {navItems.map((item) => (
              <Link
                key={item.href}
                to={item.href}
                className={cn(
                  'px-3 py-2 rounded-md text-sm font-medium transition-colors',
                  location.pathname === item.href
                    ? 'bg-obatek-dark text-white'
                    : 'text-white/80 hover:bg-obatek-light hover:text-white'
                )}
              >
                {item.label}
              </Link>
            ))}
          </div>

          {/* User Menu */}
          <div className="flex items-center space-x-4">
            <span className="text-sm text-white/80 hidden md:block">
              {user?.username}
            </span>
            <button
              onClick={handleLogout}
              className="px-3 py-2 rounded-md text-sm font-medium bg-obatek-dark hover:bg-obatek-dark/80 transition-colors"
            >
              Logout
            </button>
          </div>
        </div>

        {/* Mobile Navigation */}
        <div className="md:hidden pb-3 flex flex-wrap gap-2">
          {navItems.map((item) => (
            <Link
              key={item.href}
              to={item.href}
              className={cn(
                'px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
                location.pathname === item.href
                  ? 'bg-obatek-dark text-white'
                  : 'text-white/80 hover:bg-obatek-light hover:text-white'
              )}
            >
              {item.label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
}
