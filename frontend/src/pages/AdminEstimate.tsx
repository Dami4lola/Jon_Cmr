import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { EstimateCalculator } from '../components/EstimateCalculator';
import { estimatesApi } from '../api/estimates';
import { clientsApi } from '../api/clients';
import { formatCurrency, formatDate } from '../lib/utils';
import type { Estimate } from '../types';

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700',
  sent: 'bg-blue-100 text-blue-700',
  accepted: 'bg-green-100 text-green-700',
  declined: 'bg-red-100 text-red-700',
};

export function AdminEstimate() {
  const queryClient = useQueryClient();
  const [view, setView] = useState<'list' | 'builder'>('list');
  const [openEstimate, setOpenEstimate] = useState<Estimate | null>(null);
  const [clientMode, setClientMode] = useState<'existing' | 'prospect'>('existing');
  const [selectedClientId, setSelectedClientId] = useState<number | null>(null);
  const [prospectName, setProspectName] = useState('');

  const { data: estimates = [], isLoading } = useQuery({
    queryKey: ['estimates', 'standalone'],
    queryFn: () => estimatesApi.list({ standalone: true }),
  });

  const { data: clients = [] } = useQuery({
    queryKey: ['clients'],
    queryFn: () => clientsApi.list(),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => estimatesApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['estimates', 'standalone'] }),
  });

  const handleDownload = async (estimate: { id: number; estimate_number: string }) => {
    try {
      await estimatesApi.downloadPdfToFile(estimate.id, estimate.estimate_number);
    } catch {
      alert('Failed to download PDF');
    }
  };

  const handleNew = () => {
    setOpenEstimate(null);
    setSelectedClientId(null);
    setProspectName('');
    setClientMode('existing');
    setView('builder');
  };

  const handleOpen = async (id: number) => {
    const full = await estimatesApi.get(id);
    setOpenEstimate(full);
    setView('builder');
  };

  const handleClose = () => {
    setView('list');
    setOpenEstimate(null);
  };

  const handleSaved = () => {
    queryClient.invalidateQueries({ queryKey: ['estimates', 'standalone'] });
  };

  if (view === 'builder') {
    const clientId = openEstimate ? openEstimate.client?.id ?? null : clientMode === 'existing' ? selectedClientId : null;
    const clientNameOverride = openEstimate
      ? openEstimate.client_name_override
      : clientMode === 'prospect'
        ? prospectName
        : null;

    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">
            {openEstimate ? `Estimate — ${openEstimate.estimate_number}` : 'New Estimate'}
          </h1>
          <button onClick={handleClose} className="text-sm text-obatek hover:underline">
            &larr; Back to estimates
          </button>
        </div>

        {!openEstimate && (
          <div className="bg-white rounded-lg shadow p-4 space-y-3">
            <p className="text-sm font-medium text-gray-700">Who is this estimate for?</p>
            <div className="flex gap-4 text-sm">
              <label className="flex items-center gap-1">
                <input
                  type="radio"
                  checked={clientMode === 'existing'}
                  onChange={() => setClientMode('existing')}
                />
                Existing client
              </label>
              <label className="flex items-center gap-1">
                <input
                  type="radio"
                  checked={clientMode === 'prospect'}
                  onChange={() => setClientMode('prospect')}
                />
                New prospect
              </label>
            </div>
            {clientMode === 'existing' ? (
              <select
                value={selectedClientId ?? ''}
                onChange={(e) => setSelectedClientId(Number(e.target.value) || null)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
              >
                <option value="">Choose a client...</option>
                {clients.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                placeholder="Prospect name"
                value={prospectName}
                onChange={(e) => setProspectName(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
              />
            )}
          </div>
        )}

        <div className="bg-white rounded-lg shadow p-6">
          <EstimateCalculator
            key={openEstimate?.id ?? 'new'}
            initialEstimate={openEstimate || undefined}
            clientId={clientId}
            clientNameOverride={clientNameOverride}
            initialAddress={openEstimate?.address_override || (clientMode === 'existing' && selectedClientId ? clients.find((c) => c.id === selectedClientId)?.address : undefined)}
            onSaved={(saved) => {
              setOpenEstimate(saved);
              handleSaved();
            }}
            onClose={handleClose}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Estimates</h1>
          <p className="text-sm text-gray-500 mt-1">
            Build a full estimate — scope of work, phased hours, and cost breakdown — without needing a job first.
          </p>
        </div>
        <button
          onClick={handleNew}
          className="bg-obatek text-white px-4 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors"
        >
          New Estimate
        </button>
      </div>

      <div className="bg-white rounded-lg shadow">
        {isLoading ? (
          <div className="p-8 text-center text-gray-500">Loading...</div>
        ) : estimates.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            No estimates yet.{' '}
            <button onClick={handleNew} className="text-obatek hover:underline">
              Create one
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Estimate #</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Client</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Total</th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Status</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {estimates.map((e) => (
                  <tr key={e.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">
                      <button onClick={() => handleOpen(e.id)} className="hover:underline">
                        {e.estimate_number}
                      </button>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">{e.client_name || '—'}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{formatDate(e.created_date)}</td>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900 text-right">
                      {formatCurrency(e.total)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`text-xs font-medium px-2 py-1 rounded-full ${STATUS_COLORS[e.status] || STATUS_COLORS.draft}`}>
                        {e.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => handleDownload(e)}
                          className="text-obatek hover:text-obatek-dark transition-colors"
                          title="Download PDF"
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                        </button>
                        <button
                          onClick={() => handleOpen(e.id)}
                          className="text-gray-500 hover:text-gray-700 transition-colors"
                          title="Edit estimate"
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                        </button>
                        <button
                          onClick={() => {
                            if (window.confirm('Are you sure you want to delete this estimate?')) {
                              deleteMutation.mutate(e.id);
                            }
                          }}
                          className="text-red-400 hover:text-red-600 transition-colors"
                          title="Delete estimate"
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
