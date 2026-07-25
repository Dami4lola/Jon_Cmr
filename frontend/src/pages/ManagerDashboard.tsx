import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { timesheetsApi } from '../api/timesheets';
import { jobsApi } from '../api/jobs';
import { clientsApi, ClientCreate } from '../api/clients';
import { workersApi } from '../api/workers';
import { payrollApi } from '../api/payroll';
import { timeOffApi } from '../api/timeOff';
import { formatCurrency, formatDate } from '../lib/utils';
import { EstimateCalculator } from '../components/EstimateCalculator';
import type { Timesheet, Job, Client, Worker, JobCreate, PayrollWorkerSummary, TimeOffRequest } from '../types';

function getDateRange(start: string, end: string): string[] {
  const dates: string[] = [];
  const current = new Date(start + 'T00:00:00');
  const last = new Date(end + 'T00:00:00');
  while (current <= last) {
    dates.push(current.toISOString().split('T')[0]);
    current.setDate(current.getDate() + 1);
  }
  return dates;
}

function formatShortDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

export function ManagerDashboard() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showCreateJob, setShowCreateJob] = useState(false);
  const [showCreateClient, setShowCreateClient] = useState(false);
  const [editingClient, setEditingClient] = useState<Client | null>(null);
  const [editClientFormData, setEditClientFormData] = useState<ClientCreate>({
    name: '',
    phone_number: '',
    email: '',
    address: '',
  });
  const [editingJob, setEditingJob] = useState<Job | null>(null);
  const [formData, setFormData] = useState<JobCreate>({
    client_id: 0,
    title: '',
    details: '',
    start_date: '',
    end_date: '',
    scheduled_time: '',
    estimated_duration: undefined,
    estimate_amount: undefined,
    address_override: '',
    is_redseal_trade: false,
    assigned_worker_ids: [],
    worker_schedule: [],
  });
  const [editFormData, setEditFormData] = useState<JobCreate>({
    client_id: 0,
    title: '',
    details: '',
    start_date: '',
    end_date: '',
    scheduled_time: '',
    estimated_duration: undefined,
    estimate_amount: undefined,
    address_override: '',
    is_redseal_trade: false,
    assigned_worker_ids: [],
    worker_schedule: [],
  });
  const [photoFiles, setPhotoFiles] = useState<File[]>([]);
  const [editPhotoFiles, setEditPhotoFiles] = useState<File[]>([]);
  const [showEstimateCalc, setShowEstimateCalc] = useState(false);
  const [showEditEstimateCalc, setShowEditEstimateCalc] = useState(false);
  const [clientFormData, setClientFormData] = useState<ClientCreate>({
    name: '',
    phone_number: '',
    email: '',
    address: '',
  });

  // Payroll state
  const [showPayrollModal, setShowPayrollModal] = useState(false);
  const [payrollStartDate, setPayrollStartDate] = useState('');
  const [payrollEndDate, setPayrollEndDate] = useState('');
  const [payrollProcessing, setPayrollProcessing] = useState(false);
  const [payrollError, setPayrollError] = useState<string | null>(null);
  const [payrollSuccess, setPayrollSuccess] = useState<string | null>(null);
  const [payrollStep, setPayrollStep] = useState<'dates' | 'review' | 'done'>('dates');
  const [payrollPreview, setPayrollPreview] = useState<PayrollWorkerSummary[]>([]);
  const [payrollPreviewLoading, setPayrollPreviewLoading] = useState(false);
  const [currentWorkerIndex, setCurrentWorkerIndex] = useState(0);
  const [selectedPayrollWorkerIds, setSelectedPayrollWorkerIds] = useState<number[]>([]);

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

  // Fetch time-off requests
  const { data: timeOffRequests = [] } = useQuery({
    queryKey: ['time-off', 'all'],
    queryFn: () => timeOffApi.list(),
  });

  const pendingTimeOff = timeOffRequests.filter((r: TimeOffRequest) => r.status === 'pending');
  const approvedTimeOff = timeOffRequests.filter((r: TimeOffRequest) => r.status === 'approved');

  const isWorkerOffOnDate = (workerId: number, date: string): boolean => {
    return approvedTimeOff.some(
      (r: TimeOffRequest) => r.worker_id === workerId && r.dates.includes(date)
    );
  };

  const isWorkerOffAllDates = (workerId: number, dates: string[]): boolean => {
    return dates.length > 0 && dates.every((d) => isWorkerOffOnDate(workerId, d));
  };

  const reviewTimeOffMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: { status: 'approved' | 'denied'; manager_note?: string } }) =>
      timeOffApi.review(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['time-off'] });
    },
  });

  // Create job mutation
  const createJobMutation = useMutation({
    mutationFn: async (data: JobCreate) => {
      const job = await jobsApi.create(data);
      // Upload photos if any were selected
      if (photoFiles.length > 0) {
        await jobsApi.uploadPhotos(job.id, photoFiles);
      }
      return job;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      setShowCreateJob(false);
      setShowEstimateCalc(false);
      setPhotoFiles([]);
      setFormData({
        client_id: 0,
        title: '',
        details: '',
        start_date: '',
        end_date: '',
        scheduled_time: '',
        estimated_duration: undefined,
        estimate_amount: undefined,
        address_override: '',
        is_redseal_trade: false,
        assigned_worker_ids: [],
        worker_schedule: [],
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

  // Update client mutation
  const updateClientMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<ClientCreate> }) =>
      clientsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['clients'] });
      setEditingClient(null);
    },
  });

  // Update job mutation
  const updateJobMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: Partial<JobCreate> }) => {
      const job = await jobsApi.update(id, data);
      if (editPhotoFiles.length > 0) {
        await jobsApi.uploadPhotos(id, editPhotoFiles);
      }
      return job;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      setEditingJob(null);
      setEditPhotoFiles([]);
    },
  });

  // Mark job complete mutation
  const markCompleteMutation = useMutation({
    mutationFn: jobsApi.markCompleted,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });

  // Delete job mutation
  const deleteJobMutation = useMutation({
    mutationFn: jobsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
    onError: (error: any) => {
      alert(error?.response?.data?.detail || 'Failed to delete job. Please try again.');
    },
  });

  // Delete timesheet mutation
  const deleteTimesheetMutation = useMutation({
    mutationFn: timesheetsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timesheets'] });
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
    if (!formData.client_id || !formData.title.trim()) return;

    const submitData: JobCreate = {
      ...formData,
      start_date: formData.start_date || undefined,
      end_date: formData.end_date || undefined,
      scheduled_time: formData.scheduled_time || undefined,
      address_override: formData.address_override || undefined,
      assigned_worker_ids: formData.assigned_worker_ids?.length ? formData.assigned_worker_ids : undefined,
      worker_schedule: formData.worker_schedule?.length ? formData.worker_schedule : undefined,
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

  const handleOpenEditClient = (client: Client) => {
    setEditingClient(client);
    setEditClientFormData({
      name: client.name,
      phone_number: client.phone_number || '',
      email: client.email || '',
      address: client.address,
    });
  };

  const handleUpdateClient = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingClient || !editClientFormData.name.trim() || !editClientFormData.address.trim()) return;
    updateClientMutation.mutate({ id: editingClient.id, data: editClientFormData });
  };

  const handlePreviewPayroll = async () => {
    if (!payrollStartDate || !payrollEndDate) return;
    setPayrollPreviewLoading(true);
    setPayrollError(null);
    try {
      const workerIds = selectedPayrollWorkerIds.length > 0 ? selectedPayrollWorkerIds : undefined;
      const summaries = await payrollApi.previewPayroll(payrollStartDate, payrollEndDate, workerIds);
      setPayrollPreview(summaries);
      setCurrentWorkerIndex(0);
      setPayrollStep('review');
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      setPayrollError(error.response?.data?.detail || 'Failed to load payroll preview');
    } finally {
      setPayrollPreviewLoading(false);
    }
  };

  const handleToggleMinHours = async (timesheetId: number, currentOverride: string | null) => {
    const newValue = currentOverride === null || (currentOverride !== null && parseFloat(currentOverride) > 0) ? 0 : null;
    await timesheetsApi.update(timesheetId, { minimum_hours_override: newValue });
    await handlePreviewPayroll();
  };

  const handleProcessPayroll = async () => {
    if (!payrollStartDate || !payrollEndDate) return;
    setPayrollProcessing(true);
    setPayrollError(null);
    setPayrollSuccess(null);
    try {
      const workerIds = selectedPayrollWorkerIds.length > 0 ? selectedPayrollWorkerIds : undefined;
      const blob = await payrollApi.processPayroll(payrollStartDate, payrollEndDate, workerIds);
      // Trigger browser download
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `Payroll_${payrollStartDate}_${payrollEndDate}.zip`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      setPayrollSuccess('Payroll processed and downloaded successfully. Timesheets have been archived.');
      setPayrollStep('done');
      // Refetch timesheets so archived ones disappear
      queryClient.invalidateQueries({ queryKey: ['timesheets'] });
    } catch (err: unknown) {
      const error = err as { response?: { data?: Blob } };
      if (error.response?.data instanceof Blob) {
        // Parse error from blob response
        const text = await error.response.data.text();
        try {
          const json = JSON.parse(text);
          setPayrollError(json.detail || 'Failed to process payroll');
        } catch {
          setPayrollError('Failed to process payroll');
        }
      } else {
        setPayrollError('Failed to process payroll');
      }
    } finally {
      setPayrollProcessing(false);
    }
  };

  const handleEditJob = (job: Job) => {
    setEditingJob(job);
    setEditFormData({
      client_id: job.client?.id || job.client_id,
      title: job.title,
      details: job.details || '',
      start_date: job.start_date || '',
      end_date: job.end_date || '',
      scheduled_time: job.scheduled_time || '',
      estimated_duration: job.estimated_duration ? parseFloat(job.estimated_duration) : undefined,
      estimate_amount: job.estimate_amount ? parseFloat(job.estimate_amount) : undefined,
      address_override: job.address_override || '',
      is_redseal_trade: job.is_redseal_trade || false,
      assigned_worker_ids: job.assigned_workers?.map((w) => w.id) || job.workers?.map((w) => w.id) || [],
      worker_schedule: job.worker_schedule || [],
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
    if (!editingJob || !editFormData.client_id || !editFormData.title.trim()) return;

    const submitData: Partial<JobCreate> = {
      ...editFormData,
      start_date: editFormData.start_date || undefined,
      end_date: editFormData.end_date || undefined,
      scheduled_time: editFormData.scheduled_time || undefined,
      address_override: editFormData.address_override || undefined,
      assigned_worker_ids: editFormData.assigned_worker_ids?.length ? editFormData.assigned_worker_ids : undefined,
      worker_schedule: editFormData.worker_schedule?.length ? editFormData.worker_schedule : undefined,
    };

    updateJobMutation.mutate({ id: editingJob.id, data: submitData });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Manager Dashboard</h1>
        <div className="flex gap-3">
          <button
            onClick={() => {
              setShowPayrollModal(true);
              setPayrollError(null);
              setPayrollSuccess(null);
              setSelectedPayrollWorkerIds([]);
            }}
            className="bg-green-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-green-700 transition-colors"
          >
            Process Payroll
          </button>
          <button
            onClick={() => setShowCreateJob(!showCreateJob)}
            className="bg-obatek text-white px-4 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors"
          >
            {showCreateJob ? 'Cancel' : 'Create Job'}
          </button>
        </div>
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
                  Job Title *
                </label>
                <input
                  type="text"
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="e.g. Kitchen renovation"
                  maxLength={100}
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Details
              </label>
              <textarea
                value={formData.details || ''}
                onChange={(e) => setFormData({ ...formData, details: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                placeholder="Full job details, notes, scope of work..."
                rows={3}
              />
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
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-sm font-medium text-gray-700">
                    Estimate Amount ($)
                  </label>
                  <button
                    type="button"
                    onClick={() => setShowEstimateCalc(!showEstimateCalc)}
                    className="text-xs text-obatek hover:underline"
                  >
                    {showEstimateCalc ? 'Hide calculator' : 'Calculate'}
                  </button>
                </div>
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

            {showEstimateCalc && (
              <EstimateCalculator
                initialAddress={formData.address_override || clients.find((c) => c.id === formData.client_id)?.address}
                onApply={(total) => {
                  setFormData({ ...formData, estimate_amount: total });
                  setShowEstimateCalc(false);
                }}
                onClose={() => setShowEstimateCalc(false)}
              />
            )}

            <div>
              <label className="flex items-center gap-3 cursor-pointer">
                <button
                  type="button"
                  onClick={() => setFormData({ ...formData, is_redseal_trade: !formData.is_redseal_trade })}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    formData.is_redseal_trade ? 'bg-red-600' : 'bg-gray-300'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      formData.is_redseal_trade ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
                <span className="text-sm font-medium text-gray-700">
                  Red Seal Trade {formData.is_redseal_trade && <span className="text-red-600">(Billed at $100/hr)</span>}
                </span>
              </label>
            </div>

            {workers.length > 0 && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Assign Workers
                </label>
                {formData.start_date && formData.end_date && formData.start_date <= formData.end_date ? (
                  <div className="overflow-x-auto border rounded-lg">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-gray-50">
                          <th className="px-3 py-2 text-left font-medium text-gray-600 sticky left-0 bg-gray-50">Worker</th>
                          {getDateRange(formData.start_date, formData.end_date).map((d) => (
                            <th key={d} className="px-2 py-2 text-center font-medium text-gray-600 whitespace-nowrap">
                              {formatShortDate(d)}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {workers
                          .filter((worker: Worker) => !isWorkerOffAllDates(worker.id, getDateRange(formData.start_date!, formData.end_date!)))
                          .map((worker: Worker) => (
                          <tr key={worker.id} className="hover:bg-gray-50">
                            <td className="px-3 py-2 font-medium sticky left-0 bg-white">{worker.name}</td>
                            {getDateRange(formData.start_date!, formData.end_date!).map((d) => {
                              const offOnDate = isWorkerOffOnDate(worker.id, d);
                              const isChecked = (formData.worker_schedule || []).some(
                                (ws) => ws.worker_id === worker.id && ws.date === d
                              );
                              return (
                                <td key={d} className={`px-2 py-2 text-center ${offOnDate ? 'bg-red-50' : ''}`}>
                                  {offOnDate ? (
                                    <span className="text-xs text-red-400" title="On approved time off">OFF</span>
                                  ) : (
                                    <input
                                      type="checkbox"
                                      checked={isChecked}
                                      onChange={() => {
                                        setFormData((prev) => {
                                          const schedule = [...(prev.worker_schedule || [])];
                                          const idx = schedule.findIndex(
                                            (ws) => ws.worker_id === worker.id && ws.date === d
                                          );
                                          if (idx >= 0) {
                                            schedule.splice(idx, 1);
                                          } else {
                                            schedule.push({ worker_id: worker.id, date: d });
                                          }
                                          const workerIds = [...new Set(schedule.map((ws) => ws.worker_id))];
                                          return { ...prev, worker_schedule: schedule, assigned_worker_ids: workerIds };
                                        });
                                      }}
                                      className="w-4 h-4 text-obatek rounded border-gray-300 focus:ring-obatek"
                                    />
                                  )}
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
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
                )}
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Photos
              </label>
              <input
                type="file"
                accept="image/*"
                multiple
                onChange={(e) => setPhotoFiles(Array.from(e.target.files || []))}
                className="w-full text-sm text-gray-600 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-obatek/10 file:text-obatek hover:file:bg-obatek/20"
              />
              {photoFiles.length > 0 && (
                <p className="text-xs text-gray-500 mt-1">{photoFiles.length} photo(s) selected</p>
              )}
            </div>

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
                disabled={createJobMutation.isPending || !formData.client_id || !formData.title.trim()}
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

      {/* Edit Client Modal */}
      {editingClient && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md mx-4">
            <h2 className="text-lg font-semibold mb-4">Edit Client</h2>
            <form onSubmit={handleUpdateClient} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
                <input
                  type="text"
                  value={editClientFormData.name}
                  onChange={(e) => setEditClientFormData({ ...editClientFormData, name: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="Client name"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Address *</label>
                <input
                  type="text"
                  value={editClientFormData.address}
                  onChange={(e) => setEditClientFormData({ ...editClientFormData, address: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="Full address"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Phone Number</label>
                <input
                  type="tel"
                  value={editClientFormData.phone_number}
                  onChange={(e) => setEditClientFormData({ ...editClientFormData, phone_number: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="Phone number"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                <input
                  type="email"
                  value={editClientFormData.email}
                  onChange={(e) => setEditClientFormData({ ...editClientFormData, email: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="email@example.com"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingClient(null)}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={updateClientMutation.isPending || !editClientFormData.name.trim() || !editClientFormData.address.trim()}
                  className="bg-obatek text-white px-6 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors disabled:opacity-50"
                >
                  {updateClientMutation.isPending ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
              {updateClientMutation.isError && (
                <p className="text-red-500 text-sm">
                  {(updateClientMutation.error as any)?.response?.data?.detail || 'Failed to update client'}
                </p>
              )}
            </form>
          </div>
        </div>
      )}

      {/* Edit Job Modal */}
      {editingJob && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-2xl mx-4 max-h-[90vh] flex flex-col">
            <h2 className="text-lg font-semibold mb-4">Edit Job</h2>
            <form id="edit-job-form" onSubmit={handleUpdateJob} className="space-y-4 overflow-y-auto flex-1 min-h-0 pr-2">
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
                    Job Title *
                  </label>
                  <input
                    type="text"
                    value={editFormData.title}
                    onChange={(e) => setEditFormData({ ...editFormData, title: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                    placeholder="e.g. Kitchen renovation"
                    maxLength={100}
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
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-sm font-medium text-gray-700">
                      Estimate Amount ($)
                    </label>
                    <button
                      type="button"
                      onClick={() => setShowEditEstimateCalc(!showEditEstimateCalc)}
                      className="text-xs text-obatek hover:underline"
                    >
                      {showEditEstimateCalc ? 'Hide calculator' : 'Calculate'}
                    </button>
                  </div>
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

              {showEditEstimateCalc && (
                <EstimateCalculator
                  initialAddress={editFormData.address_override || clients.find((c) => c.id === editFormData.client_id)?.address}
                  onApply={(total) => {
                    setEditFormData({ ...editFormData, estimate_amount: total });
                    setShowEditEstimateCalc(false);
                  }}
                  onClose={() => setShowEditEstimateCalc(false)}
                />
              )}

              <div>
                <label className="flex items-center gap-3 cursor-pointer">
                  <button
                    type="button"
                    onClick={() => setEditFormData({ ...editFormData, is_redseal_trade: !editFormData.is_redseal_trade })}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      editFormData.is_redseal_trade ? 'bg-red-600' : 'bg-gray-300'
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        editFormData.is_redseal_trade ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                  <span className="text-sm font-medium text-gray-700">
                    Red Seal Trade {editFormData.is_redseal_trade && <span className="text-red-600">(Billed at $100/hr)</span>}
                  </span>
                </label>
              </div>

              {workers.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Assign Workers
                  </label>
                  {editFormData.start_date && editFormData.end_date && editFormData.start_date <= editFormData.end_date ? (
                    <div className="overflow-x-auto border rounded-lg">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="bg-gray-50">
                            <th className="px-3 py-2 text-left font-medium text-gray-600 sticky left-0 bg-gray-50">Worker</th>
                            {getDateRange(editFormData.start_date, editFormData.end_date).map((d) => (
                              <th key={d} className="px-2 py-2 text-center font-medium text-gray-600 whitespace-nowrap">
                                {formatShortDate(d)}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y">
                          {workers
                            .filter((worker: Worker) => !isWorkerOffAllDates(worker.id, getDateRange(editFormData.start_date!, editFormData.end_date!)))
                            .map((worker: Worker) => (
                            <tr key={worker.id} className="hover:bg-gray-50">
                              <td className="px-3 py-2 font-medium sticky left-0 bg-white">{worker.name}</td>
                              {getDateRange(editFormData.start_date!, editFormData.end_date!).map((d) => {
                                const offOnDate = isWorkerOffOnDate(worker.id, d);
                                const isChecked = (editFormData.worker_schedule || []).some(
                                  (ws) => ws.worker_id === worker.id && ws.date === d
                                );
                                return (
                                  <td key={d} className={`px-2 py-2 text-center ${offOnDate ? 'bg-red-50' : ''}`}>
                                    {offOnDate ? (
                                      <span className="text-xs text-red-400" title="On approved time off">OFF</span>
                                    ) : (
                                      <input
                                        type="checkbox"
                                        checked={isChecked}
                                        onChange={() => {
                                          setEditFormData((prev) => {
                                            const schedule = [...(prev.worker_schedule || [])];
                                            const idx = schedule.findIndex(
                                              (ws) => ws.worker_id === worker.id && ws.date === d
                                            );
                                            if (idx >= 0) {
                                              schedule.splice(idx, 1);
                                            } else {
                                              schedule.push({ worker_id: worker.id, date: d });
                                            }
                                            const workerStillInSchedule = schedule.some((ws) => ws.worker_id === worker.id);
                                            const currentAssigned = prev.assigned_worker_ids || [];
                                            const newAssigned = workerStillInSchedule
                                              ? currentAssigned.includes(worker.id)
                                                ? currentAssigned
                                                : [...currentAssigned, worker.id]
                                              : currentAssigned.filter((id) => id !== worker.id);
                                            return { ...prev, worker_schedule: schedule, assigned_worker_ids: newAssigned };
                                          });
                                        }}
                                        className="w-4 h-4 text-obatek rounded border-gray-300 focus:ring-obatek"
                                      />
                                    )}
                                  </td>
                                );
                              })}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
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
                  )}
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Details
                </label>
                <textarea
                  value={editFormData.details || ''}
                  onChange={(e) => setEditFormData({ ...editFormData, details: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="Full job details, notes, scope of work..."
                  rows={3}
                />
              </div>

              {/* Existing Photos */}
              {editingJob.photos && editingJob.photos.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Existing Photos
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {editingJob.photos.map((photo) => (
                      <div key={photo.id} className="relative group">
                        <img
                          src={photo.public_url}
                          alt="Job photo"
                          className="w-20 h-20 object-cover rounded-lg border"
                        />
                        <button
                          type="button"
                          onClick={async () => {
                            await jobsApi.deletePhoto(editingJob.id, photo.id);
                            queryClient.invalidateQueries({ queryKey: ['jobs'] });
                            setEditingJob({
                              ...editingJob,
                              photos: editingJob.photos?.filter((p) => p.id !== photo.id),
                            });
                          }}
                          className="absolute -top-1 -right-1 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          X
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Add Photos
                </label>
                <input
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={(e) => setEditPhotoFiles(Array.from(e.target.files || []))}
                  className="w-full text-sm text-gray-600 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-obatek/10 file:text-obatek hover:file:bg-obatek/20"
                />
                {editPhotoFiles.length > 0 && (
                  <p className="text-xs text-gray-500 mt-1">{editPhotoFiles.length} photo(s) selected</p>
                )}
              </div>

            </form>
            <div className="flex justify-end gap-2 pt-4 border-t mt-4">
              <button
                type="button"
                onClick={() => setEditingJob(null)}
                className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={(e) => { e.preventDefault(); (document.querySelector('#edit-job-form') as HTMLFormElement)?.requestSubmit(); }}
                disabled={updateJobMutation.isPending || !editFormData.client_id || !editFormData.title.trim()}
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
          </div>
        </div>
      )}

      {/* Payroll Processing Modal */}
      {showPayrollModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 overflow-y-auto">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-2xl mx-4 my-8">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">
                {payrollStep === 'dates' && 'Process Payroll'}
                {payrollStep === 'review' && `Process Payroll — Review Worker ${currentWorkerIndex + 1} of ${payrollPreview.length}`}
                {payrollStep === 'done' && 'Process Payroll — Complete'}
              </h2>
              <button
                onClick={() => {
                  setShowPayrollModal(false);
                  setPayrollStartDate('');
                  setPayrollEndDate('');
                  setPayrollError(null);
                  setPayrollSuccess(null);
                  setPayrollStep('dates');
                  setPayrollPreview([]);
                  setCurrentWorkerIndex(0);
                  setSelectedPayrollWorkerIds([]);
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Step 1: Date & Worker Selection */}
            {payrollStep === 'dates' && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Start Date</label>
                    <input
                      type="date"
                      value={payrollStartDate}
                      onChange={(e) => setPayrollStartDate(e.target.value)}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">End Date</label>
                    <input
                      type="date"
                      value={payrollEndDate}
                      onChange={(e) => setPayrollEndDate(e.target.value)}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                    />
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-medium text-gray-700">Select Workers</label>
                    <button
                      type="button"
                      onClick={() => {
                        if (selectedPayrollWorkerIds.length === workers.length) {
                          setSelectedPayrollWorkerIds([]);
                        } else {
                          setSelectedPayrollWorkerIds(workers.map((w: Worker) => w.id));
                        }
                      }}
                      className="text-xs text-obatek hover:text-obatek-dark transition-colors"
                    >
                      {selectedPayrollWorkerIds.length === workers.length ? 'Deselect All' : 'Select All'}
                    </button>
                  </div>
                  <div className="border border-gray-200 rounded-lg max-h-48 overflow-y-auto divide-y">
                    {workers.map((w: Worker) => (
                      <label key={w.id} className="flex items-center gap-3 px-3 py-2 hover:bg-gray-50 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={selectedPayrollWorkerIds.includes(w.id)}
                          onChange={() => {
                            setSelectedPayrollWorkerIds((prev) =>
                              prev.includes(w.id) ? prev.filter((id) => id !== w.id) : [...prev, w.id]
                            );
                          }}
                          className="rounded border-gray-300 text-obatek focus:ring-obatek"
                        />
                        <span className="text-sm text-gray-700">{w.name}</span>
                      </label>
                    ))}
                  </div>
                  {selectedPayrollWorkerIds.length > 0 && (
                    <p className="text-xs text-gray-500 mt-1">{selectedPayrollWorkerIds.length} of {workers.length} workers selected</p>
                  )}
                </div>

                {payrollError && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                    <p className="text-red-800 text-sm">{payrollError}</p>
                  </div>
                )}

                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => {
                      setShowPayrollModal(false);
                      setPayrollStartDate('');
                      setPayrollEndDate('');
                      setPayrollError(null);
                      setSelectedPayrollWorkerIds([]);
                    }}
                    className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handlePreviewPayroll}
                    disabled={payrollPreviewLoading || !payrollStartDate || !payrollEndDate || selectedPayrollWorkerIds.length === 0}
                    className="bg-obatek text-white px-6 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors disabled:opacity-50 flex items-center gap-2"
                  >
                    {payrollPreviewLoading ? (
                      <>
                        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                        Loading...
                      </>
                    ) : (
                      'Preview Payroll'
                    )}
                  </button>
                </div>
              </div>
            )}

            {/* Step 2: Worker-by-Worker Review */}
            {payrollStep === 'review' && payrollPreview.length > 0 && (() => {
              const worker = payrollPreview[currentWorkerIndex];
              return (
                <div className="space-y-4">
                  {/* Worker header */}
                  <div className="bg-gray-50 rounded-lg p-4">
                    <h3 className="font-semibold text-gray-900 text-lg">{worker.worker_name}</h3>
                    <div className="grid grid-cols-3 gap-4 mt-3 text-sm">
                      <div>
                        <span className="text-gray-500">Hours</span>
                        <p className="font-semibold">{parseFloat(worker.total_hours).toFixed(2)}</p>
                      </div>
                      <div>
                        <span className="text-gray-500">Labour</span>
                        <p className="font-semibold">{formatCurrency(worker.total_labour)}</p>
                      </div>
                      <div>
                        <span className="text-gray-500">Total Payout</span>
                        <p className="font-bold text-obatek">{formatCurrency(worker.grand_total)}</p>
                      </div>
                    </div>
                  </div>

                  {/* Entries table */}
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Customer</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Hours</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Break</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Billable</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Labour</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">KM</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Materials</th>
                          <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase">4hr Min</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {worker.entries.map((entry, i) => (
                          <tr key={i} className="hover:bg-gray-50">
                            <td className="px-3 py-2 text-gray-600">{entry.date}</td>
                            <td className="px-3 py-2 text-gray-900">{entry.customer_name}</td>
                            <td className="px-3 py-2 text-right text-gray-600">
                              {parseFloat(entry.hours_worked).toFixed(2)}
                            </td>
                            <td className="px-3 py-2 text-right text-gray-600">
                              {parseFloat(entry.break_duration) > 0 ? parseFloat(entry.break_duration).toFixed(2) : '-'}
                            </td>
                            <td className="px-3 py-2 text-right text-gray-600">
                              {parseFloat(entry.billable_hours).toFixed(2)}
                            </td>
                            <td className="px-3 py-2 text-right text-gray-600">{formatCurrency(entry.labour_cost)}</td>
                            <td className="px-3 py-2 text-right text-gray-600">{parseFloat(entry.km_distance).toFixed(0)}</td>
                            <td className="px-3 py-2 text-right text-gray-600">
                              {parseFloat(entry.personal_materials) > 0 ? formatCurrency(entry.personal_materials) : '-'}
                            </td>
                            <td className="px-3 py-2 text-center">
                              <button
                                type="button"
                                onClick={() => handleToggleMinHours(entry.timesheet_id, entry.minimum_hours_override)}
                                className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                                  entry.minimum_hours_override === null || (entry.minimum_hours_override !== null && parseFloat(entry.minimum_hours_override) > 0)
                                    ? 'bg-obatek/10 text-obatek hover:bg-obatek/20'
                                    : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                                }`}
                              >
                                {entry.minimum_hours_override === null || (entry.minimum_hours_override !== null && parseFloat(entry.minimum_hours_override) > 0) ? 'ON' : 'OFF'}
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Totals summary */}
                  <div className="bg-gray-50 rounded-lg p-4">
                    <div className="grid grid-cols-2 gap-1 text-sm">
                      <span className="text-gray-600">Labour</span>
                      <span className="text-right font-medium">{formatCurrency(worker.total_labour)}</span>
                      <span className="text-gray-600">KM ({parseFloat(worker.total_km).toFixed(1)} km)</span>
                      <span className="text-right font-medium">{formatCurrency(worker.total_km_cost)}</span>
                      {parseFloat(worker.total_personal_materials) > 0 && (
                        <>
                          <span className="text-gray-600">Materials</span>
                          <span className="text-right font-medium">{formatCurrency(worker.total_personal_materials)}</span>
                        </>
                      )}
                      {worker.charges_hst && (
                        <>
                          <span className="text-gray-600 pt-1 border-t mt-1">HST (Labour)</span>
                          <span className="text-right font-medium pt-1 border-t mt-1">{formatCurrency(worker.labour_hst)}</span>
                          <span className="text-gray-600">HST (KM)</span>
                          <span className="text-right font-medium">{formatCurrency(worker.km_hst)}</span>
                          {parseFloat(worker.materials_hst) > 0 && (
                            <>
                              <span className="text-gray-600">HST (Materials)</span>
                              <span className="text-right font-medium">{formatCurrency(worker.materials_hst)}</span>
                            </>
                          )}
                        </>
                      )}
                      <span className="font-semibold text-gray-900 pt-1 border-t mt-1">Total Payout</span>
                      <span className="text-right font-bold text-obatek pt-1 border-t mt-1">{formatCurrency(worker.grand_total)}</span>
                    </div>
                  </div>

                  {payrollError && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                      <p className="text-red-800 text-sm">{payrollError}</p>
                    </div>
                  )}

                  {/* Navigation */}
                  <div className="flex justify-between pt-2">
                    <button
                      onClick={() => {
                        if (currentWorkerIndex > 0) {
                          setCurrentWorkerIndex(currentWorkerIndex - 1);
                        } else {
                          setPayrollStep('dates');
                        }
                      }}
                      className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                    >
                      {currentWorkerIndex > 0 ? 'Previous Worker' : 'Back'}
                    </button>
                    <div className="flex gap-2">
                      {currentWorkerIndex < payrollPreview.length - 1 ? (
                        <button
                          onClick={() => setCurrentWorkerIndex(currentWorkerIndex + 1)}
                          className="bg-obatek text-white px-6 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors"
                        >
                          Next Worker
                        </button>
                      ) : (
                        <button
                          onClick={handleProcessPayroll}
                          disabled={payrollProcessing}
                          className="bg-green-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-green-700 transition-colors disabled:opacity-50 flex items-center gap-2"
                        >
                          {payrollProcessing ? (
                            <>
                              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                              </svg>
                              Processing...
                            </>
                          ) : (
                            `Confirm All & Download (${payrollPreview.length} workers)`
                          )}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })()}

            {/* Step 3: Done */}
            {payrollStep === 'done' && (
              <div className="space-y-4">
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <p className="text-green-800 text-sm">{payrollSuccess}</p>
                </div>
                <div className="flex justify-end">
                  <button
                    onClick={() => {
                      setShowPayrollModal(false);
                      setPayrollStartDate('');
                      setPayrollEndDate('');
                      setPayrollSuccess(null);
                      setPayrollStep('dates');
                      setPayrollPreview([]);
                      setCurrentWorkerIndex(0);
                      setSelectedPayrollWorkerIds([]);
                    }}
                    className="px-4 py-2 bg-obatek text-white rounded-lg font-medium hover:bg-obatek-dark transition-colors"
                  >
                    Done
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
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
        <div
          className="bg-white rounded-lg shadow p-4 cursor-pointer hover:ring-2 hover:ring-green-300 transition-all"
          onClick={() => navigate('/completed-jobs')}
        >
          <p className="text-sm text-gray-600">Completed Jobs</p>
          <p className="text-2xl font-bold text-green-600">{completedJobs.length}</p>
          <p className="text-xs text-gray-400 mt-1">Click to view &rarr;</p>
        </div>
        <div
          className="bg-white rounded-lg shadow p-4 cursor-pointer hover:ring-2 hover:ring-blue-300 transition-all"
          onClick={() => navigate('/paid-timesheets')}
        >
          <p className="text-sm text-gray-600">Paid Timesheets</p>
          <p className="text-2xl font-bold text-blue-600">View</p>
          <p className="text-xs text-gray-400 mt-1">Click to view &rarr;</p>
        </div>
      </div>

      {/* Time-Off Requests */}
      {pendingTimeOff.length > 0 && (
        <div className="bg-white rounded-lg shadow">
          <div className="p-4 border-b flex items-center gap-2">
            <h2 className="text-lg font-semibold">Time-Off Requests</h2>
            <span className="bg-yellow-100 text-yellow-700 text-xs font-medium px-2 py-0.5 rounded-full">
              {pendingTimeOff.length} pending
            </span>
          </div>
          <div className="divide-y">
            {pendingTimeOff.map((req: TimeOffRequest) => (
              <div key={req.id} className="p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium text-gray-900">{req.worker?.name}</p>
                    <p className="text-sm text-gray-600 mt-0.5">
                      {req.dates.map((d: string) => formatDate(d)).join(', ')}
                    </p>
                    <p className="text-sm text-gray-500 mt-1">{req.reason}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => reviewTimeOffMutation.mutate({ id: req.id, data: { status: 'approved' } })}
                      disabled={reviewTimeOffMutation.isPending}
                      className="px-3 py-1.5 text-xs font-medium bg-green-100 text-green-700 rounded-lg hover:bg-green-200 transition-colors"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => {
                        const note = window.prompt('Reason for denial (optional):');
                        reviewTimeOffMutation.mutate({
                          id: req.id,
                          data: { status: 'denied', manager_note: note || undefined },
                        });
                      }}
                      disabled={reviewTimeOffMutation.isPending}
                      className="px-3 py-1.5 text-xs font-medium bg-red-100 text-red-700 rounded-lg hover:bg-red-200 transition-colors"
                    >
                      Deny
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

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
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
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
                      {ts.job?.client_name} - {ts.job?.title}
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
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (window.confirm('Are you sure you want to delete this timesheet?')) {
                            deleteTimesheetMutation.mutate(ts.id);
                          }
                        }}
                        className="text-red-400 hover:text-red-600 transition-colors"
                        title="Delete timesheet"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
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
                    <p className="font-medium text-gray-900">{job.title}</p>
                    <p className="text-sm text-gray-600">
                      {job.client?.name} | {job.job_address}
                    </p>
                    {job.assigned_workers && job.assigned_workers.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {job.assigned_workers.map((w) => (
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
                    {job.calculated_distance_km && (
                      <span className="text-xs text-gray-500">
                        {job.calculated_distance_km} km
                      </span>
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
                      <button
                        onClick={() => {
                          if (window.confirm('Are you sure you want to delete this job?')) {
                            deleteJobMutation.mutate(job.id);
                          }
                        }}
                        disabled={deleteJobMutation.isPending}
                        className="text-sm text-red-600 hover:underline"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Clients Section */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-4 border-b flex items-center justify-between">
          <h2 className="text-lg font-semibold">Clients ({clients.length})</h2>
          <button
            onClick={() => setShowCreateClient(true)}
            className="text-sm text-obatek hover:underline"
          >
            + New Client
          </button>
        </div>
        {clients.length === 0 ? (
          <div className="p-8 text-center text-gray-500">No clients yet.</div>
        ) : (
          <div className="divide-y">
            {clients.map((client: Client) => (
              <div key={client.id} className="p-4 flex items-center justify-between gap-4">
                <div>
                  <p className="font-medium text-gray-900">{client.name}</p>
                  <p className="text-sm text-gray-500">{client.address}</p>
                  {client.phone_number && (
                    <p className="text-sm text-gray-500">{client.phone_number}</p>
                  )}
                  {client.email && (
                    <p className="text-sm text-gray-500">{client.email}</p>
                  )}
                </div>
                <button
                  onClick={() => handleOpenEditClient(client)}
                  className="text-sm text-obatek hover:underline shrink-0"
                >
                  Edit
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
