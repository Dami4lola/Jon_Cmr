import { useEffect, useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { estimatesApi } from '../api/estimates';
import { workersApi } from '../api/workers';
import { formatCurrency } from '../lib/utils';
import { WorkerPicker } from './WorkerPicker';
import { WorkerScheduleGrid } from './WorkerScheduleGrid';
import type {
  ConvertEstimatePayload,
  Estimate,
  Job,
  Worker,
  WorkerScheduleEntry,
} from '../types';

// Job.estimated_duration is Numeric(4,2) on the backend, so longer estimates
// cannot carry their hours onto the job.
const JOB_DURATION_MAX = 99.99;

interface ConvertEstimateDialogProps {
  estimateId: number;
  onClose: () => void;
  onConverted: (job: Job, estimateNumber: string) => void;
}

function addDays(date: string, days: number): string {
  const d = new Date(date + 'T12:00:00');
  d.setDate(d.getDate() + days);
  return d.toLocaleDateString('en-CA');
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
  const [step, setStep] = useState<'details' | 'schedule'>('details');
  const [scheduleWorkers, setScheduleWorkers] = useState<Worker[]>([]);
  const [title, setTitle] = useState('');
  const [details, setDetails] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [scheduledTime, setScheduledTime] = useState('');
  const [workerIds, setWorkerIds] = useState<number[]>([]);
  const [workerSchedule, setWorkerSchedule] = useState<WorkerScheduleEntry[]>([]);
  const [clientName, setClientName] = useState('');
  const [clientAddress, setClientAddress] = useState('');
  const [clientPhone, setClientPhone] = useState('');
  const [clientEmail, setClientEmail] = useState('');

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
    // job_details, not scope_of_work: the written scope, the phased task list and the
    // gear list, which is what the crew reads. Composed server-side so this cannot
    // drift from the fallback the conversion itself uses.
    setDetails(estimate.job_details || '');
    setClientName(estimate.client_name_override || '');
    setClientAddress(estimate.address_override || '');
  }, [estimate]);

  const needsClient = !!estimate && !estimate.client;
  const totalHours = estimate ? parseFloat(estimate.total_hours) : 0;
  const hoursTooLarge = totalHours > JOB_DURATION_MAX;
  const rangeInverted = !!startDate && !!endDate && endDate < startDate;
  const isMultiDay = !!startDate && !!endDate && endDate > startDate;
  // A one-day job has nothing to confirm, and neither has a job with nobody on it.
  const needsSchedule = isMultiDay && workerIds.length > 0;

  // The estimate already priced how many days the work runs, so the manager gets the
  // range - and with it the second screen - off a single date. Typed-over freely.
  const handleStartDate = (value: string) => {
    setStartDate(value);
    if (value && !endDate && estimate?.travel_days) {
      setEndDate(addDays(value, estimate.travel_days - 1));
    }
  };

  const toggleWorker = (workerId: number) => {
    setWorkerIds((current) =>
      current.includes(workerId) ? current.filter((id) => id !== workerId) : [...current, workerId]
    );
  };

  // The rows are frozen on the way in rather than read off workerIds each render: the grid
  // drops a worker from workerIds when their last day is unticked, and a live row set would
  // make that worker vanish mid-edit with no way to tick them back.
  const goToSchedule = () => {
    setScheduleWorkers(workers.filter((worker) => workerIds.includes(worker.id)));
    setStep('schedule');
  };

  // Going Back and changing the dates or the crew leaves entries the grid no longer draws,
  // and those would schedule someone outside their own job or off it entirely.
  const scheduleToSubmit = workerSchedule.filter(
    (ws) =>
      workerIds.includes(ws.worker_id) &&
      (!startDate || ws.date >= startDate) &&
      (!endDate || ws.date <= endDate)
  );

  // A single-day job skips the second screen, but it still needs its one row per worker -
  // without them the crew's dashboard shows a bare date instead of "Your days:" and the
  // calendar emits a span instead of a day.
  const resolvedSchedule =
    scheduleToSubmit.length === 0 && startDate && startDate === endDate
      ? workerIds.map((worker_id) => ({ worker_id, date: startDate }))
      : scheduleToSubmit;

  const convertMutation = useMutation({
    mutationFn: () => {
      const payload: ConvertEstimatePayload = {
        title: title.trim(),
        details: details.trim() || null,
        start_date: startDate || null,
        end_date: endDate || null,
        scheduled_time: scheduledTime ? `${scheduledTime}:00` : null,
        assigned_worker_ids: workerIds,
        worker_schedule: resolvedSchedule,
      };
      if (needsClient) {
        payload.new_client = {
          name: clientName.trim(),
          address: clientAddress.trim(),
          phone_number: clientPhone.trim() || undefined,
          email: clientEmail.trim() || undefined,
        };
      }
      return estimatesApi.convertToJob(estimateId, payload);
    },
    onSuccess: (job) => onConverted(job, estimate?.estimate_number ?? ''),
  });

  const errorDetail =
    (convertMutation.error as any)?.response?.data?.detail ||
    (convertMutation.error ? 'Failed to convert this estimate. Please try again.' : null);

  const canSubmit =
    !!title.trim() &&
    !convertMutation.isPending &&
    !rangeInverted &&
    (!needsClient
      || (!!clientName.trim()
        && !!clientAddress.trim()
        && (!!clientPhone.trim() || !!clientEmail.trim())));

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-2xl mx-4 max-h-[90vh] flex flex-col">
        <h2 className="text-lg font-semibold mb-4">
          {step === 'details'
            ? 'Convert Estimate to Job'
            : "Convert Estimate to Job — Confirm the crew's days"}
        </h2>

        {isLoading || !estimate ? (
          <p className="text-sm text-gray-500">Loading estimate...</p>
        ) : (
          <>
            {/* Step 1: the job */}
            {step === 'details' && (
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
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
                      <input
                        type="tel"
                        value={clientPhone}
                        onChange={(e) => setClientPhone(e.target.value)}
                        maxLength={20}
                        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        The crew calls this from the job card if they need the client on site.
                      </p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                      <input
                        type="email"
                        value={clientEmail}
                        onChange={(e) => setClientEmail(e.target.value)}
                        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        A phone number or an email - either one.
                      </p>
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
                  rows={12}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Prefilled with the scope of work and the gear list off this estimate. The
                  crew sees this on their dashboard and on their calendar - edit it here.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label htmlFor="convert-start-date" className="block text-sm font-medium text-gray-700 mb-1">
                    Start date
                  </label>
                  <input
                    id="convert-start-date"
                    type="date"
                    value={startDate}
                    onChange={(e) => handleStartDate(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label htmlFor="convert-end-date" className="block text-sm font-medium text-gray-700 mb-1">
                    End date
                  </label>
                  <input
                    id="convert-end-date"
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label htmlFor="convert-start-time" className="block text-sm font-medium text-gray-700 mb-1">
                    Start time
                  </label>
                  <input
                    id="convert-start-time"
                    type="time"
                    value={scheduledTime}
                    onChange={(e) => setScheduledTime(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
              </div>

              {rangeInverted && (
                <p className="text-sm text-red-600">End date cannot be before start date.</p>
              )}

              {workers.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Assign workers</label>
                  <WorkerPicker
                    workers={workers}
                    assignedWorkerIds={workerIds}
                    onToggle={toggleWorker}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    {needsSchedule
                      ? 'The next screen asks which days each of them is on site.'
                      : 'Who is on this job. A job running more than one day asks for the days next.'}
                  </p>
                </div>
              )}

              <p className="text-xs text-gray-500">
                The estimate stays editable and stays linked to this job. Deleting the job later will
                also delete the estimate.
              </p>
            </div>
            )}

            {/* Step 2: who works which day */}
            {step === 'schedule' && (
            <div className="space-y-4 overflow-y-auto flex-1 min-h-0 pr-2">
              <p className="text-sm text-gray-600">
                Tick each worker onto the days they are on site. Days they are on approved time
                off are blocked out.
              </p>

              <WorkerScheduleGrid
                workers={scheduleWorkers}
                startDate={startDate}
                endDate={endDate}
                schedule={workerSchedule}
                assignedWorkerIds={workerIds}
                onChange={(schedule, ids) => {
                  setWorkerSchedule(schedule);
                  setWorkerIds(ids);
                }}
              />

              <p className="text-xs text-gray-500">
                {scheduleToSubmit.length === 0
                  ? 'No days ticked yet - the crew will see the date range instead of their own days.'
                  : `${scheduleToSubmit.length} day${scheduleToSubmit.length === 1 ? '' : 's'} across ${
                      new Set(scheduleToSubmit.map((ws) => ws.worker_id)).size
                    } worker${new Set(scheduleToSubmit.map((ws) => ws.worker_id)).size === 1 ? '' : 's'}.`}
              </p>
            </div>
            )}

            {errorDetail && (
              <p className="text-sm text-red-600 mt-3">{errorDetail}</p>
            )}

            {/* Navigation */}
            <div className="flex justify-between items-center gap-3 mt-4 pt-4 border-t">
              {step === 'schedule' ? (
                <button
                  type="button"
                  onClick={() => setStep('details')}
                  disabled={convertMutation.isPending}
                  className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                >
                  Back
                </button>
              ) : (
                <span />
              )}
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={onClose}
                  disabled={convertMutation.isPending}
                  className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
                >
                  Cancel
                </button>
                {step === 'details' && needsSchedule ? (
                  <button
                    type="button"
                    onClick={goToSchedule}
                    disabled={!canSubmit}
                    className="bg-obatek text-white px-4 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors disabled:opacity-50"
                  >
                    Next: confirm days
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => convertMutation.mutate()}
                    disabled={!canSubmit}
                    className="bg-obatek text-white px-4 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors disabled:opacity-50"
                  >
                    {convertMutation.isPending ? 'Converting...' : 'Convert to Job'}
                  </button>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
