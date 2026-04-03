import { QueryClient } from '@tanstack/react-query';
import { createSyncStoragePersister } from '@tanstack/query-sync-storage-persister';
import api from '../api/client';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      gcTime: 1000 * 60 * 60 * 24, // 24 hours (cache time)
      retry: 1,
      networkMode: 'offlineFirst',
      refetchOnWindowFocus: false,
    },
    mutations: {
      networkMode: 'offlineFirst',
      retry: 1,
    },
  },
});

export const persister = createSyncStoragePersister({
  storage: window.localStorage,
  key: 'obatek-query-cache',
});

// Mutation queue for offline support
const MUTATION_QUEUE_KEY = 'obatek-mutation-queue';

export interface QueuedMutation {
  id: string;
  endpoint: string;
  method: 'POST' | 'PUT' | 'DELETE';
  data?: unknown;
  timestamp: number;
  retryCount?: number;
}

export function addToMutationQueue(mutation: Omit<QueuedMutation, 'id' | 'timestamp'>) {
  const queue = getMutationQueue();
  const newMutation: QueuedMutation = {
    ...mutation,
    id: crypto.randomUUID(),
    timestamp: Date.now(),
    retryCount: 0,
  };
  queue.push(newMutation);
  localStorage.setItem(MUTATION_QUEUE_KEY, JSON.stringify(queue));
  return newMutation;
}

export function getMutationQueue(): QueuedMutation[] {
  try {
    const stored = localStorage.getItem(MUTATION_QUEUE_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

export function removeFromMutationQueue(id: string) {
  const queue = getMutationQueue().filter((m) => m.id !== id);
  localStorage.setItem(MUTATION_QUEUE_KEY, JSON.stringify(queue));
}

export function clearMutationQueue() {
  localStorage.removeItem(MUTATION_QUEUE_KEY);
}

// Process a single mutation
async function processMutation(mutation: QueuedMutation): Promise<boolean> {
  try {
    switch (mutation.method) {
      case 'POST':
        await api.post(mutation.endpoint, mutation.data);
        break;
      case 'PUT':
        await api.put(mutation.endpoint, mutation.data);
        break;
      case 'DELETE':
        await api.delete(mutation.endpoint);
        break;
    }
    return true;
  } catch (error) {
    if (import.meta.env.DEV) {
      console.error(`Failed to process mutation ${mutation.id}:`, error);
    }
    return false;
  }
}

// Process all queued mutations
export async function processMutationQueue(): Promise<{
  processed: number;
  failed: number;
}> {
  const queue = getMutationQueue();
  if (queue.length === 0) {
    return { processed: 0, failed: 0 };
  }

  let processed = 0;
  let failed = 0;
  const MAX_RETRIES = 3;

  for (const mutation of queue) {
    const success = await processMutation(mutation);

    if (success) {
      removeFromMutationQueue(mutation.id);
      processed++;
    } else {
      // Increment retry count
      const retryCount = (mutation.retryCount || 0) + 1;
      if (retryCount >= MAX_RETRIES) {
        // Remove after max retries
        removeFromMutationQueue(mutation.id);
        failed++;
        if (import.meta.env.DEV) {
          console.warn(`Mutation ${mutation.id} failed after ${MAX_RETRIES} retries, removing from queue`);
        }
      } else {
        // Update retry count in queue
        const updatedQueue = getMutationQueue().map((m) =>
          m.id === mutation.id ? { ...m, retryCount } : m
        );
        localStorage.setItem(MUTATION_QUEUE_KEY, JSON.stringify(updatedQueue));
        failed++;
      }
    }
  }

  // Invalidate queries to refresh data after sync
  if (processed > 0) {
    queryClient.invalidateQueries();
  }

  return { processed, failed };
}

// Setup online/offline sync listener
let syncInProgress = false;

export function setupOfflineSync() {
  const handleOnline = async () => {
    if (syncInProgress) return;

    syncInProgress = true;
    if (import.meta.env.DEV) {
      console.log('Back online, processing mutation queue...');
    }

    try {
      const result = await processMutationQueue();
      if (result.processed > 0 || result.failed > 0) {
        if (import.meta.env.DEV) {
          console.log(`Sync complete: ${result.processed} processed, ${result.failed} failed`);
        }
      }
    } catch (error) {
      if (import.meta.env.DEV) {
        console.error('Error processing mutation queue:', error);
      }
    } finally {
      syncInProgress = false;
    }
  };

  window.addEventListener('online', handleOnline);

  // Also process queue on initial load if online
  if (navigator.onLine) {
    handleOnline();
  }

  // Return cleanup function
  return () => {
    window.removeEventListener('online', handleOnline);
  };
}

// Helper to queue a mutation when offline
export function queueMutationIfOffline(
  endpoint: string,
  method: 'POST' | 'PUT' | 'DELETE',
  data?: unknown
): boolean {
  if (!navigator.onLine) {
    addToMutationQueue({ endpoint, method, data });
    return true; // Queued
  }
  return false; // Not queued, proceed with regular API call
}
