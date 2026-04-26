import { Outlet } from 'react-router-dom';
import { Navbar } from './Navbar';
import { OfflineBanner } from '../shared/OfflineBanner';

export function AppShell() {
  return (
    <div className="min-h-screen bg-background">
      <OfflineBanner />
      <Navbar />
      <main className="max-w-7xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
