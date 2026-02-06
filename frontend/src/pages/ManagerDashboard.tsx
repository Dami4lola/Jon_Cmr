import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { timesheetsApi } from '../api/timesheets';
import { jobsApi } from '../api/jobs';
import { clientsApi } from '../api/clients';
import { workersApi } from '../api/workers';
import { formatCurrency, formatDate } from '../lib/utils';
import type { Timesheet, Job, Client, Worker, JobCreate } from '../types';

export function ManagerDashboard() {
  const queryClient = useQueryClient();
  const [showCreateJob, setShowCreateJob] = useState(false);
  const [formData, setFormData] = useState<JobCreate>({
    client_id: 0,
    description: '',
    scheduled_date: '',
    scheduled_time: '',
    estimated_duration: undefined,
    estimate_amount: undefined,
    address_override: '',
    worker_ids: [],
  });

  // Fetch all recent timesheets
  const { data: timesheets = [], isLoading: loadingTimesheets } = useQuery({
    queryKey: ['timesheets', 'all'],
    queryFn: () => timesheetsApi.list({ limit: 50 }),
  });

  // Fetch all jobs
  const { data: jobs = [], isLoading: loadingJobs } = useQuery({
    queryKey: ['jobs', 'all'],
    queryFn: () => jobsApi.list(),
  });

  // Fetch clients for dropdown
  const { data: clients = [] } = useQuery({
    queryKey: ['clients'],
    queryFn: () => clientsApi.list(),
  });

  // Fetch workers for assignment
  const { data: workers = [] } = useQuery({
    queryKey: ['workers'],
    queryFn: () => workersApi.list(),
  });

  // Create job mutation
  const createJobMutation = useMutation({
    mutationFn: jobsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      setShowCreateJob(false);
      setFormData({
        client_id: 0,
        description: '',
        scheduled_date: '',
        scheduled_time: '',
        estimated_duration: undefined,
        estimate_amount: undefined,
        address_override: '',
        worker_ids: [],
      });
    },
  });

  // Calculate totals
  const totalPayout = timesheets.reduce(
    (sum: number, ts: Timesheet) => sum + (parseFloat(ts.calculated_pay || '0') || 0),
    0
  );

  const totalHours = timesheets.reduce(
    (sum: number, ts: Timesheet) => sum + (parseFloat(ts.hours_worked) || 0),
    0
  );

  const activeJobs = jobs.filter((j: Job) => !j.is_completed);
  const completedJobs = jobs.filter((j: Job) => j.is_completed);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.client_id || !formData.description.trim()) return;

    const submitData: JobCreate = {
      ...formData,
      scheduled_date: formData.scheduled_date || undefined,
      scheduled_time: formData.scheduled_time || undefined,
      address_override: formData.address_override || undefined,
      worker_ids: formData.worker_ids?.length ? formData.worker_ids : undefined,
    };

    createJobMutation.mutate(submitData);
  };

  const handleWorkerToggle = (workerId: number) => {
    setFormData((prev) => {
      const currentWorkers = prev.worker_ids || [];
      if (currentWorkers.includes(workerId)) {
        return { ...prev, worker_ids: currentWorkers.filter((id) => id !== workerId) };
      } else {
        return { ...prev, worker_ids: [...currentWorkers, workerId] };
      }
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Manager Dashboard</h1>
        <button
          onClick={() => setShowCreateJob(!showCreateJob)}
          className="bg-obatek text-white px-4 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors"
        >
          {showCreateJob ? 'Cancel' : 'Create Job'}
        </button>
      </div>

      {/* Create Job Form */}
      {showCreateJob && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Create New Job</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Client *
                </label>
                <select
                  value={formData.client_id}
                  onChange={(e) => setFormData({ ...formData, client_id: parseInt(e.target.value) })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  required
                >
                  <option value={0}>Select a client...</option>
                  {clients.map((client: Client) => (
                    <option key={client.id} value={client.id}>
                      {client.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Description *
                </label>
                <input
                  type="text"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="Job description"
                  required
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Scheduled Date
                </label>
                <input
                  type="date"
                  value={formData.scheduled_date}
                  onChange={(e) => setFormData({ ...formData, scheduled_date: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Scheduled Time
                </label>
                <input
                  type="time"
                  value={formData.scheduled_time}
                  onChange={(e) => setFormData({ ...formData, scheduled_time: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Estimated Duration (hours)
                </label>
                <input
                  type="number"
                  step="0.5"
                  min="0"
                  value={formData.estimated_duration || ''}
                  onChange={(e) => setFormData({ ...formData, estimated_duration: parseFloat(e.target.value) || undefined })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="e.g. 4"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Estimate Amount ($)
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={formData.estimate_amount || ''}
                  onChange={(e) => setFormData({ ...formData, estimate_amount: parseFloat(e.target.value) || undefined })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="e.g. 500.00"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Address Override (optional)
                </label>
                <input
                  type="text"
                  value={formData.address_override}
                  onChange={(e) => setFormData({ ...formData, address_override: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="Leave blank to use client's address"
                />
              </div>
            </div>

            {workers.length > 0 && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Assign Workers
                </label>
                <div className="flex flex-wrap gap-2">
                  {workers.map((worker: Worker) => (
                    <label
                      key={worker.id}
                      className={`flex items-center gap-2 px-3 py-2 border rounded-lg cursor-pointer transition-colors ${
                        formData.worker_ids?.includes(worker.id)
                          ? 'bg-obatek/10 border-obatek text-obatek'
                          : 'border-gray-300 hover:border-gray-400'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={formData.worker_ids?.includes(worker.id) || false}
                        onChange={() => handleWorkerToggle(worker.id)}
                        className="sr-only"
                      />
                      <span className="text-sm">{worker.name}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowCreateJob(false)}
                className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={createJobMutation.isPending || !formData.client_id || !formData.description.trim()}
                className="bg-obatek text-white px-6 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors disabled:opacity-50"
              >
                {createJobMutation.isPending ? 'Creating...' : 'Create Job'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Total Payouts</p>
          <p className="text-2xl font-bold text-obatek">{formatCurrency(totalPayout)}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Total Hours</p>
          <p className="text-2xl font-bold text-gray-900">{totalHours.toFixed(1)}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Active Jobs</p>
          <p className="text-2xl font-bold text-gray-900">{activeJobs.length}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Completed Jobs</p>
          <p className="text-2xl font-bold text-green-600">{completedJobs.length}</p>
        </div>
      </div>

      {/* Recent Timesheets */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-4 border-b">
          <h2 className="text-lg font-semibold">Recent Timesheets</h2>
        </div>
        {loadingTimesheets ? (
          <div className="p-8 text-center text-gray-500">Loading...</div>
        ) : timesheets.length === 0 ? (
          <div className="p-8 text-center text-gray-500">No timesheets found.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Worker
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Job
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Date
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Hours
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    KMs
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Payout
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {timesheets.map((ts: Timesheet) => (
                  <tr key={ts.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">
                      {ts.worker?.name || 'Unknown'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {ts.job?.client?.name} - {ts.job?.description}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {formatDate(ts.date)}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 text-right">
                      {ts.hours_worked}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 text-right">
                      {ts.round_trip_kms}
                    </td>
                    <td className="px-4 py-3 text-sm font-medium text-obatek text-right">
                      {ts.calculated_pay ? formatCurrency(ts.calculated_pay) : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Active Jobs */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-4 border-b">
          <h2 className="text-lg font-semibold">Active Jobs ({activeJobs.length})</h2>
        </div>
        {loadingJobs ? (
          <div className="p-8 text-center text-gray-500">Loading...</div>
        ) : activeJobs.length === 0 ? (
          <div className="p-8 text-center text-gray-500">No active jobs.</div>
        ) : (
          <div className="divide-y">
            {activeJobs.map((job: Job) => (
              <div key={job.id} className="p-4 hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-gray-900">{job.description}</p>
                    <p className="text-sm text-gray-600">
                      {job.client?.name} | {job.job_address}
                    </p>
                  </div>
                  <div className="text-right">
                    {job.scheduled_date && (
                      <p className="text-sm text-obatek">{formatDate(job.scheduled_date)}</p>
                    )}
                    {job.estimate_amount && (
                      <p className="text-sm text-gray-500">
                        Est: {formatCurrency(job.estimate_amount)}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
