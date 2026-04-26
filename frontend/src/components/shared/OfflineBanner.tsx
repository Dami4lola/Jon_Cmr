import { useEffect, useState } from 'react';
import { getMutationQueue, processMutationQueue } from '../../lib/queryClient';

export function OfflineBanner() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [pendingCount, setPendingCount] = useState(0);
  const [isSyncing, setIsSyncing] = useState(false);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Check pending mutations
    const checkPending = () => {
      const queue = getMutationQueue();
      setPendingCount(queue.length);
    };

    checkPending();
    const interval = setInterval(checkPending, 2000);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      clearInterval(interval);
    };
  }, []);

  // Trigger sync when coming back online with pending changes
  useEffect(() => {
    if (isOnline && pendingCount > 0 && !isSyncing) {
      setIsSyncing(true);
      processMutationQueue().finally(() => {
        setIsSyncing(false);
      });
    }
  }, [isOnline, pendingCount, isSyncing]);

  if (isOnline && pendingCount === 0) {
    return null;
  }

  return (
    <div className="fixed top-0 left-0 right-0 z-50 bg-amber-500 text-white px-4 py-2 text-center text-sm font-medium shadow-md">
      {!isOnline ? (
        <span className="flex items-center justify-center gap-2">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 5.636a9 9 0 010 12.728m-3.536-3.536a4 4 0 010-5.656m-7.072 7.072a9 9 0 010-12.728m3.536 3.536a4 4 0 010 5.656" />
          </svg>
          You are offline. {pendingCount > 0 ? `${pendingCount} change${pendingCount > 1 ? 's' : ''} will sync when connection is restored.` : 'Changes will sync when connection is restored.'}
        </span>
      ) : (
        <span className="flex items-center justify-center gap-2">
          <svg className="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Syncing {pendingCount} pending change{pendingCount > 1 ? 's' : ''}...
        </span>
      )}
    </div>
  );
}
