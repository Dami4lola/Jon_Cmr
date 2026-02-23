import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { timesheetsApi } from '../api/timesheets';
import { jobsApi } from '../api/jobs';
import { clientsApi, ClientCreate } from '../api/clients';
import { workersApi } from '../api/workers';
import { formatCurrency, formatDate } from '../lib/utils';
import type { Timesheet, Job, Client, Worker, JobCreate } from '../types';

export function ManagerDashboard() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showCreateJob, setShowCreateJob] = useState(false);
  const [showCreateClient, setShowCreateClient] = useState(false);
  const [editingJob, setEditingJob] = useState<Job | null>(null);
  const [formData, setFormData] = useState<JobCreate>({
    client_id: 0,
    description: '',
    start_date: '',
    end_date: '',
    scheduled_time: '',
    estimated_duration: undefined,
    estimate_amount: undefined,
    address_override: '',
    assigned_worker_ids: [],
  });
  const [editFormData, setEditFormData] = useState<JobCreate>({
    client_id: 0,
    description: '',
    start_date: '',
    end_date: '',
    scheduled_time: '',
    estimated_duration: undefined,
    estimate_amount: undefined,
    address_override: '',
    assigned_worker_ids: [],
  });
  const [clientFormData, setClientFormData] = useState<ClientCreate>({
    name: '',
    phone_number: '',
    email: '',
    address: '',
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
        start_date: '',
        end_date: '',
        scheduled_time: '',
        estimated_duration: undefined,
        estimate_amount: undefined,
        address_override: '',
        assigned_worker_ids: [],
      });
    },
  });

  // Create client mutation
  const createClientMutation = useMutation({
    mutationFn: clientsApi.create,
    onSuccess: (newClient) => {
      queryClient.invalidateQueries({ queryKey: ['clients'] });
      setShowCreateClient(false);
      setFormData((prev) => ({ ...prev, client_id: newClient.id }));
      setClientFormData({
        name: '',
        phone_number: '',
        email: '',
        address: '',
      });
    },
  });

  // Update job mutation
  const updateJobMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<JobCreate> }) =>
      jobsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      setEditingJob(null);
    },
  });

  // Mark job complete mutation
  const markCompleteMutation = useMutation({
    mutationFn: jobsApi.markCompleted,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
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
      start_date: formData.start_date || undefined,
      end_date: formData.end_date || undefined,
      scheduled_time: formData.scheduled_time || undefined,
      address_override: formData.address_override || undefined,
      assigned_worker_ids: formData.assigned_worker_ids?.length ? formData.assigned_worker_ids : undefined,
    };

    createJobMutation.mutate(submitData);
  };

  const handleWorkerToggle = (workerId: number) => {
    setFormData((prev) => {
      const currentWorkers = prev.assigned_worker_ids || [];
      if (currentWorkers.includes(workerId)) {
        return { ...prev, assigned_worker_ids: currentWorkers.filter((id) => id !== workerId) };
      } else {
        return { ...prev, assigned_worker_ids: [...currentWorkers, workerId] };
      }
    });
  };

  const handleClientSelect = (value: string) => {
    if (value === 'create-new') {
      setShowCreateClient(true);
    } else {
      setFormData({ ...formData, client_id: parseInt(value) });
    }
  };

  const handleCreateClient = (e: React.FormEvent) => {
    e.preventDefault();
    if (!clientFormData.name.trim() || !clientFormData.address.trim()) return;
    createClientMutation.mutate(clientFormData);
  };

  const handleEditJob = (job: Job) => {
    setEditingJob(job);
    setEditFormData({
      client_id: job.client_id,
      description: job.description,
      start_date: job.start_date || '',
      end_date: job.end_date || '',
      scheduled_time: job.scheduled_time || '',
      estimated_duration: job.estimated_duration ? parseFloat(job.estimated_duration) : undefined,
      estimate_amount: job.estimate_amount ? parseFloat(job.estimate_amount) : undefined,
      address_override: job.address_override || '',
      assigned_worker_ids: job.workers?.map((w) => w.id) || [],
    });
  };

  const handleEditWorkerToggle = (workerId: number) => {
    setEditFormData((prev) => {
      const currentWorkers = prev.assigned_worker_ids || [];
      if (currentWorkers.includes(workerId)) {
        return { ...prev, assigned_worker_ids: currentWorkers.filter((id) => id !== workerId) };
      } else {
        return { ...prev, assigned_worker_ids: [...currentWorkers, workerId] };
      }
    });
  };

  const handleEditClientSelect = (value: string) => {
    if (value === 'create-new') {
      setShowCreateClient(true);
    } else {
      setEditFormData({ ...editFormData, client_id: parseInt(value) });
    }
  };

  const handleUpdateJob = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingJob || !editFormData.client_id || !editFormData.description.trim()) return;

    const submitData: Partial<JobCreate> = {
      ...editFormData,
      start_date: editFormData.start_date || undefined,
      end_date: editFormData.end_date || undefined,
      scheduled_time: editFormData.scheduled_time || undefined,
      address_override: editFormData.address_override || undefined,
      assigned_worker_ids: editFormData.assigned_worker_ids?.length ? editFormData.assigned_worker_ids : undefined,
    };

    updateJobMutation.mutate({ id: editingJob.id, data: submitData });
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
                  onChange={(e) => handleClientSelect(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  required
                >
                  <option value={0}>Select a client...</option>
                  <option value="create-new" className="font-medium text-obatek">
                    + Create New Client
                  </option>
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

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Start Date
                </label>
                <input
                  type="date"
                  value={formData.start_date}
                  onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  End Date
                </label>
                <input
                  type="date"
                  value={formData.end_date}
                  onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Start Time
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
                        formData.assigned_worker_ids?.includes(worker.id)
                          ? 'bg-obatek/10 border-obatek text-obatek'
                          : 'border-gray-300 hover:border-gray-400'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={formData.assigned_worker_ids?.includes(worker.id) || false}
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

      {/* Create Client Modal */}
      {showCreateClient && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md mx-4">
            <h2 className="text-lg font-semibold mb-4">Create New Client</h2>
            <form onSubmit={handleCreateClient} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Name *
                </label>
                <input
                  type="text"
                  value={clientFormData.name}
                  onChange={(e) => setClientFormData({ ...clientFormData, name: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="Client name"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Address *
                </label>
                <input
                  type="text"
                  value={clientFormData.address}
                  onChange={(e) => setClientFormData({ ...clientFormData, address: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="Full address"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Phone Number
                </label>
                <input
                  type="tel"
                  value={clientFormData.phone_number}
                  onChange={(e) => setClientFormData({ ...clientFormData, phone_number: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="Phone number"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Email
                </label>
                <input
                  type="email"
                  value={clientFormData.email}
                  onChange={(e) => setClientFormData({ ...clientFormData, email: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="email@example.com"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateClient(false);
                    setClientFormData({ name: '', phone_number: '', email: '', address: '' });
                  }}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createClientMutation.isPending || !clientFormData.name.trim() || !clientFormData.address.trim()}
                  className="bg-obatek text-white px-6 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors disabled:opacity-50"
                >
                  {createClientMutation.isPending ? 'Creating...' : 'Create Client'}
                </button>
              </div>
              {createClientMutation.isError && (
                <p className="text-red-500 text-sm">
                  Error: {(createClientMutation.error as Error)?.message || 'Failed to create client'}
                </p>
              )}
            </form>
          </div>
        </div>
      )}

      {/* Edit Job Modal */}
      {editingJob && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 overflow-y-auto py-8">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-2xl mx-4">
            <h2 className="text-lg font-semibold mb-4">Edit Job</h2>
            <form onSubmit={handleUpdateJob} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Client *
                  </label>
                  <select
                    value={editFormData.client_id}
                    onChange={(e) => handleEditClientSelect(e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                    required
                  >
                    <option value={0}>Select a client...</option>
                    <option value="create-new" className="font-medium text-obatek">
                      + Create New Client
                    </option>
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
                    value={editFormData.description}
                    onChange={(e) => setEditFormData({ ...editFormData, description: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                    placeholder="Job description"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Start Date
                  </label>
                  <input
                    type="date"
                    value={editFormData.start_date}
                    onChange={(e) => setEditFormData({ ...editFormData, start_date: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    End Date
                  </label>
                  <input
                    type="date"
                    value={editFormData.end_date}
                    onChange={(e) => setEditFormData({ ...editFormData, end_date: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Start Time
                  </label>
                  <input
                    type="time"
                    value={editFormData.scheduled_time}
                    onChange={(e) => setEditFormData({ ...editFormData, scheduled_time: e.target.value })}
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
                    value={editFormData.estimated_duration || ''}
                    onChange={(e) => setEditFormData({ ...editFormData, estimated_duration: parseFloat(e.target.value) || undefined })}
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
                    value={editFormData.estimate_amount || ''}
                    onChange={(e) => setEditFormData({ ...editFormData, estimate_amount: parseFloat(e.target.value) || undefined })}
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
                    value={editFormData.address_override}
                    onChange={(e) => setEditFormData({ ...editFormData, address_override: e.target.value })}
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
                          editFormData.assigned_worker_ids?.includes(worker.id)
                            ? 'bg-obatek/10 border-obatek text-obatek'
                            : 'border-gray-300 hover:border-gray-400'
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={editFormData.assigned_worker_ids?.includes(worker.id) || false}
                          onChange={() => handleEditWorkerToggle(worker.id)}
                          className="sr-only"
                        />
                        <span className="text-sm">{worker.name}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingJob(null)}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={updateJobMutation.isPending || !editFormData.client_id || !editFormData.description.trim()}
                  className="bg-obatek text-white px-6 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors disabled:opacity-50"
                >
                  {updateJobMutation.isPending ? 'Saving...' : 'Save Changes'}
                </button>
              </div>

              {updateJobMutation.isError && (
                <p className="text-red-500 text-sm">
                  Error: {(updateJobMutation.error as Error)?.message || 'Failed to update job'}
                </p>
              )}
            </form>
          </div>
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
                    Break
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                    Receipts
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Payout
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {timesheets.map((ts: Timesheet) => (
                  <tr key={ts.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => navigate(`/timesheets/${ts.id}`)}>
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
                      {parseFloat(ts.break_duration) > 0 ? `${ts.break_duration}h` : '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-center">
                      {ts.receipt_count > 0 ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
                          {ts.receipt_count}
                        </span>
                      ) : '-'}
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
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <p className="font-medium text-gray-900">{job.description}</p>
                    <p className="text-sm text-gray-600">
                      {job.client?.name} | {job.job_address}
                    </p>
                    {job.workers && job.workers.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {job.workers.map((w) => (
                          <span
                            key={w.id}
                            className="px-2 py-0.5 text-xs bg-gray-100 text-gray-700 rounded-full"
                          >
                            {w.name}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="text-right flex-shrink-0">
                    {job.start_date && (
                      <p className="text-sm text-obatek">
                        {formatDate(job.start_date)}
                        {job.end_date && job.end_date !== job.start_date && ` – ${formatDate(job.end_date)}`}
                      </p>
                    )}
                    {job.estimate_amount && (
                      <p className="text-sm text-gray-500">
                        Est: {formatCurrency(job.estimate_amount)}
                      </p>
                    )}
                    <div className="flex gap-2 mt-2 justify-end">
                      <button
                        onClick={() => handleEditJob(job)}
                        className="text-sm text-obatek hover:underline"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => markCompleteMutation.mutate(job.id)}
                        disabled={markCompleteMutation.isPending}
                        className="text-sm text-green-600 hover:underline"
                      >
                        Complete
                      </button>
                    </div>
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
