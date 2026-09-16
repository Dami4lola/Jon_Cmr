import { useEffect, useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { estimatesApi } from '../api/estimates';
import { workersApi } from '../api/workers';
import { formatCurrency } from '../lib/utils';
import type { ConvertEstimatePayload, Estimate, Job, Worker } from '../types';

// Job.estimated_duration is Numeric(4,2) on the backend, so longer estimates
// cannot carry their hours onto the job.
const JOB_DURATION_MAX = 99.99;

interface ConvertEstimateDialogProps {
  estimateId: number;
  onClose: () => void;
  onConverted: (job: Job, estimateNumber: string) => void;
}

function defaultJobTitle(estimate: Estimate): string {
  const firstScopeLine = (estimate.scope_of_work || '')
    .split('\n')
    .map((line) => line.trim())
    .find((line) => line.length > 0);

  const fallback = [estimate.client?.name || estimate.client_name_override, estimate.estimate_number]
    .filter(Boolean)
    .join(' — ');

  return (firstScopeLine || fallback || estimate.estimate_number).slice(0, 100);
}

export function ConvertEstimateDialog({ estimateId, onClose, onConverted }: ConvertEstimateDialogProps) {
  const [title, setTitle] = useState('');
  const [details, setDetails] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [scheduledTime, setScheduledTime] = useState('');
  const [workerIds, setWorkerIds] = useState<number[]>([]);
  const [clientName, setClientName] = useState('');
  const [clientAddress, setClientAddress] = useState('');

  const { data: estimate, isLoading } = useQuery<Estimate>({
    queryKey: ['estimate', estimateId],
    queryFn: () => estimatesApi.get(estimateId),
  });

  const { data: workers = [] } = useQuery<Worker[]>({
    queryKey: ['workers'],
    queryFn: () => workersApi.list(),
  });

  useEffect(() => {
    if (!estimate) return;
    setTitle(defaultJobTitle(estimate));
    setDetails(estimate.scope_of_work || '');
    setClientName(estimate.client_name_override || '');
    setClientAddress(estimate.address_override || '');
  }, [estimate]);

  const needsClient = !!estimate && !estimate.client;
  const totalHours = estimate ? parseFloat(estimate.total_hours) : 0;
  const hoursTooLarge = totalHours > JOB_DURATION_MAX;

  const convertMutation = useMutation({
    mutationFn: () => {
      const payload: ConvertEstimatePayload = {
        title: title.trim(),
        details: details.trim() || null,
        start_date: startDate || null,
        end_date: endDate || null,
        scheduled_time: scheduledTime ? `${scheduledTime}:00` : null,
        assigned_worker_ids: workerIds,
      };
      if (needsClient) {
        payload.new_client = { name: clientName.trim(), address: clientAddress.trim() };
      }
      return estimatesApi.convertToJob(estimateId, payload);
    },
    onSuccess: (job) => onConverted(job, estimate?.estimate_number ?? ''),
  });

  const errorDetail =
    (convertMutation.error as any)?.response?.data?.detail ||
    (convertMutation.error ? 'Failed to convert this estimate. Please try again.' : null);

  const toggleWorker = (workerId: number) => {
    setWorkerIds((current) =>
      current.includes(workerId) ? current.filter((id) => id !== workerId) : [...current, workerId]
    );
  };

  const canSubmit =
    !!title.trim() &&
    !convertMutation.isPending &&
    (!needsClient || (!!clientName.trim() && !!clientAddress.trim()));

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-2xl mx-4 max-h-[90vh] flex flex-col">
        <h2 className="text-lg font-semibold mb-4">Convert Estimate to Job</h2>

        {isLoading || !estimate ? (
          <p className="text-sm text-gray-500">Loading estimate...</p>
        ) : (
          <>
            <div className="space-y-4 overflow-y-auto flex-1 min-h-0 pr-2">
              <div className="bg-gray-50 rounded-lg p-4 grid grid-cols-2 md:grid-cols-4 gap-3">
                <div>
                  <p className="text-xs text-gray-500">Estimate</p>
                  <p className="text-sm font-semibold text-gray-900">{estimate.estimate_number}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Client</p>
                  <p className="text-sm font-semibold text-gray-900">
                    {estimate.client?.name || estimate.client_name_override || '—'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Job value (incl. HST)</p>
                  <p className="text-sm font-semibold text-gray-900">{formatCurrency(estimate.total)}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Estimated hours</p>
                  <p className="text-sm font-semibold text-gray-900">{totalHours.toFixed(2)}h</p>
                </div>
              </div>

              {hoursTooLarge && (
                <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-3">
                  {totalHours.toFixed(2)} hours is larger than a job's duration field can hold, so it
                  will be left blank. The full figure stays on this estimate.
                </p>
              )}

              {needsClient && (
                <div className="border border-gray-200 rounded-lg p-3 space-y-3">
                  <p className="text-sm font-medium text-gray-700">
                    This estimate has no client record yet — one will be created.
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Client name *</label>
                      <input
                        type="text"
                        value={clientName}
                        onChange={(e) => setClientName(e.target.value)}
                        maxLength={100}
                        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Address *</label>
                      <input
                        type="text"
                        value={clientAddress}
                        onChange={(e) => setClientAddress(e.target.value)}
                        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                      />
                    </div>
                  </div>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Job title *</label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  maxLength={100}
                  required
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Job details</label>
                <textarea
                  value={details}
                  onChange={(e) => setDetails(e.target.value)}
                  rows={4}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                />
                <p className="text-xs text-gray-500 mt-1">Prefilled from the scope of work. Workers see this.</p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Start date</label>
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">End date</label>
                  <input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Start time</label>
                  <input
                    type="time"
                    value={scheduledTime}
                    onChange={(e) => setScheduledTime(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
              </div>

              {workers.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Assign workers</label>
                  <div className="border border-gray-200 rounded-lg p-3 flex flex-wrap gap-3">
                    {workers.map((worker) => (
                      <label key={worker.id} className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={workerIds.includes(worker.id)}
                          onChange={() => toggleWorker(worker.id)}
                        />
                        {worker.name}
                      </label>
                    ))}
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    Day-by-day scheduling can be set afterwards from the Manager Dashboard.
                  </p>
                </div>
              )}

              <p className="text-xs text-gray-500">
                The estimate stays editable and stays linked to this job. Deleting the job later will
                also delete the estimate.
              </p>
            </div>

            {errorDetail && (
              <p className="text-sm text-red-600 mt-3">{errorDetail}</p>
            )}

            <div className="flex justify-end gap-3 mt-4 pt-4 border-t">
              <button
                type="button"
                onClick={onClose}
                disabled={convertMutation.isPending}
                className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => convertMutation.mutate()}
                disabled={!canSubmit}
                className="bg-obatek text-white px-4 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors disabled:opacity-50"
              >
                {convertMutation.isPending ? 'Converting...' : 'Convert to Job'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
