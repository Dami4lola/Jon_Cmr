import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { jobsApi } from '../api/jobs';
import { timesheetsApi } from '../api/timesheets';
import { authApi } from '../api/auth';
import { useAuthStore } from '../store/authStore';
import { formatCurrency, formatDate } from '../lib/utils';
import type { TimesheetCreate, Timesheet } from '../types';

export function Dashboard() {
  const { user } = useAuthStore();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [showForm, setShowForm] = useState(false);
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [pwForm, setPwForm] = useState({ currentPassword: '', newPassword: '', confirmPassword: '' });
  const [pwError, setPwError] = useState('');
  const [pwSuccess, setPwSuccess] = useState('');
  const [pwSubmitting, setPwSubmitting] = useState(false);

  // Fetch assigned jobs
  const { data: jobs = [], isLoading: loadingJobs } = useQuery({
    queryKey: ['jobs', 'assigned'],
    queryFn: () => jobsApi.list({ is_completed: false }),
  });

  // Fetch recent timesheets
  const { data: timesheets = [], isLoading: loadingTimesheets } = useQuery({
    queryKey: ['timesheets', 'recent'],
    queryFn: () => timesheetsApi.list({ limit: 10 }),
  });

  // Timesheet form state
  const [formData, setFormData] = useState<TimesheetCreate>({
    job_id: 0,
    date: new Date().toLocaleDateString('en-CA'),
    hours_worked: 0,
    break_duration: 0,
    used_company_truck: false,
    worked_at_hq: false,
    company_materials: 0,
    personal_materials: 0,
    notes: '',
  });

  // Receipt file upload state
  const [receiptFiles, setReceiptFiles] = useState<File[]>([]);
  const receiptFilesRef = useRef<File[]>([]);
  const [uploadingReceipts, setUploadingReceipts] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Payout preview state
  const [payoutPreview, setPayoutPreview] = useState<{ calculated_pay: number } | null>(null);

  // Create timesheet mutation
  const createMutation = useMutation({
    mutationFn: async (data: typeof formData) => {
      const newTimesheet = await timesheetsApi.create(data);
      const filesToUpload = receiptFilesRef.current;
      if (filesToUpload.length > 0) {
        setUploadingReceipts(true);
        try {
          await timesheetsApi.uploadReceipts(newTimesheet.id, filesToUpload);
        } catch (err) {
          console.error('Receipt upload failed', err);
          alert('Timesheet saved but receipt upload failed. Please try uploading receipts again.');
        } finally {
          setUploadingReceipts(false);
        }
      }
      return newTimesheet;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timesheets'] });
      setShowForm(false);
      resetForm();
    },
  });

  // Delete timesheet mutation
  const deleteTimesheetMutation = useMutation({
    mutationFn: timesheetsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timesheets'] });
    },
  });

  const resetForm = () => {
    setFormData({
      job_id: 0,
      date: new Date().toLocaleDateString('en-CA'),
      hours_worked: 0,
      break_duration: 0,
      used_company_truck: false,
      worked_at_hq: false,
      company_materials: 0,
      personal_materials: 0,
      notes: '',
    });
    setReceiptFiles([]);
    receiptFilesRef.current = [];
    setPayoutPreview(null);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (formData.job_id === 0) return;
    createMutation.mutate(formData);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const selectedFiles = Array.from(e.target.files);
      setReceiptFiles((prev) => {
        const updated = [...prev, ...selectedFiles];
        receiptFilesRef.current = updated;
        return updated;
      });
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const removeFile = (index: number) => {
    setReceiptFiles((prev) => {
      const updated = prev.filter((_, i) => i !== index);
      receiptFilesRef.current = updated;
      return updated;
    });
  };

  const handlePreviewPayout = async () => {
    if (formData.job_id === 0 || formData.hours_worked <= 0) return;
    try {
      const preview = await timesheetsApi.calculatePayout(formData);
      setPayoutPreview(preview);
    } catch {
      setPayoutPreview(null);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPwError('');
    setPwSuccess('');

    if (pwForm.newPassword.length < 6) {
      setPwError('New password must be at least 6 characters');
      return;
    }
    if (pwForm.newPassword !== pwForm.confirmPassword) {
      setPwError('New passwords do not match');
      return;
    }

    setPwSubmitting(true);
    try {
      await authApi.changePassword(pwForm.currentPassword, pwForm.newPassword);
      setPwSuccess('Password changed successfully.');
      setPwForm({ currentPassword: '', newPassword: '', confirmPassword: '' });
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setPwError(detail || 'Failed to change password. Please try again.');
    } finally {
      setPwSubmitting(false);
    }
  };

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>

  ) => {
    const { name, value, type } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]:
        type === 'checkbox'
          ? (e.target as HTMLInputElement).checked
          : type === 'number'
          ? parseFloat(value) || 0
          : value,
    }));
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-600">Welcome back, {user?.username}</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => setShowChangePassword(!showChangePassword)}
            className="border border-gray-300 text-gray-700 px-4 py-2 rounded-lg font-medium hover:bg-gray-50 transition-colors"
          >
            Change Password
          </button>
          <button
            onClick={() => setShowForm(!showForm)}
            className="bg-obatek text-white px-4 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors"
          >
            {showForm ? 'Cancel' : 'Submit Timesheet'}
          </button>
        </div>
      </div>

      {/* Change Password Modal */}
      {showChangePassword && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-sm w-full">
            <h2 className="text-lg font-semibold mb-4">Change Password</h2>
            <form onSubmit={handleChangePassword} className="space-y-4">
              {pwError && (
                <div className="bg-red-50 text-red-600 p-3 rounded-lg text-sm">{pwError}</div>
              )}
              {pwSuccess && (
                <div className="bg-green-50 text-green-700 p-3 rounded-lg text-sm">{pwSuccess}</div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Current Password</label>
                <input
                  type="password"
                  value={pwForm.currentPassword}
                  onChange={(e) => setPwForm((prev) => ({ ...prev, currentPassword: e.target.value }))}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">New Password</label>
                <input
                  type="password"
                  value={pwForm.newPassword}
                  onChange={(e) => setPwForm((prev) => ({ ...prev, newPassword: e.target.value }))}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  required
                  minLength={6}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Confirm New Password</label>
                <input
                  type="password"
                  value={pwForm.confirmPassword}
                  onChange={(e) => setPwForm((prev) => ({ ...prev, confirmPassword: e.target.value }))}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  required
                  minLength={6}
                />
              </div>

              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setShowChangePassword(false);
                    setPwError('');
                    setPwSuccess('');
                    setPwForm({ currentPassword: '', newPassword: '', confirmPassword: '' });
                  }}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Close
                </button>
                <button
                  type="submit"
                  disabled={pwSubmitting}
                  className="bg-obatek text-white px-6 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors disabled:opacity-50"
                >
                  {pwSubmitting ? 'Changing...' : 'Change Password'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Timesheet Form */}
      {showForm && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Submit Timesheet</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            {createMutation.isError && (
              <div className="bg-red-50 text-red-600 p-3 rounded-lg text-sm">
                Failed to submit timesheet. Please try again.
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Job
                </label>
                <select
                  name="job_id"
                  value={formData.job_id}
                  onChange={handleChange}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  required
                >
                  <option value={0}>Select a job...</option>
                  {jobs.map((job) => (
                    <option key={job.id} value={job.id}>
                      {job.client?.name} - {job.title}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Date
                </label>
                <input
                  type="date"
                  name="date"
                  value={formData.date}
                  onChange={handleChange}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Hours Worked
                </label>
                <input
                  type="number"
                  name="hours_worked"
                  value={formData.hours_worked || ''}
                  onChange={handleChange}
                  step="0.25"
                  min="0"
                  max="24"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="0"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Break Duration (hours)
                </label>
                <input
                  type="number"
                  name="break_duration"
                  value={formData.break_duration || ''}
                  onChange={handleChange}
                  step="0.25"
                  min="0"
                  max="24"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="0"
                />
                <p className="text-xs text-gray-400 mt-1">Tracked for records only.</p>
              </div>
            </div>

            <div className="flex flex-wrap gap-6">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  name="used_company_truck"
                  checked={formData.used_company_truck}
                  onChange={handleChange}
                  className="w-4 h-4 text-obatek rounded border-gray-300 focus:ring-obatek"
                />
                <span className="text-sm text-gray-700">Used Company Truck</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  name="worked_at_hq"
                  checked={formData.worked_at_hq}
                  onChange={handleChange}
                  className="w-4 h-4 text-obatek rounded border-gray-300 focus:ring-obatek"
                />
                <span className="text-sm text-gray-700">Worked at HQ</span>
              </label>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Company Materials ($)
                </label>
                <input
                  type="number"
                  name="company_materials"
                  value={formData.company_materials || ''}
                  onChange={handleChange}
                  step="0.01"
                  min="0"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="0.00"
                />
                <p className="text-xs text-gray-400 mt-1">Paid by company. Not added to your pay.</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Personal Materials ($)
                </label>
                <input
                  type="number"
                  name="personal_materials"
                  value={formData.personal_materials || ''}
                  onChange={handleChange}
                  step="0.01"
                  min="0"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="0.00"
                />
                <p className="text-xs text-green-600 mt-1">Paid by you. Will be reimbursed.</p>
              </div>
            </div>

            {/* Receipt Image Upload */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Attach Receipt Photos
              </label>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                multiple
                onChange={handleFileSelect}
                className="hidden"
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="px-4 py-2 border-2 border-dashed border-gray-300 rounded-lg text-sm text-gray-600 hover:border-obatek hover:text-obatek transition-colors w-full"
              >
                + Add Receipt Photos
              </button>
              {receiptFiles.length > 0 && (
                <div className="mt-2 grid grid-cols-3 gap-2">
                  {receiptFiles.map((file, index) => (
                    <div key={index} className="relative group">
                      <img
                        src={URL.createObjectURL(file)}
                        alt={file.name}
                        className="w-full h-24 object-cover rounded-lg border border-gray-200"
                      />
                      <button
                        type="button"
                        onClick={() => removeFile(index)}
                        className="absolute top-1 right-1 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        X
                      </button>
                      <p className="text-xs text-gray-500 mt-1 truncate">{file.name}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Notes */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Notes
              </label>
              <textarea
                name="notes"
                value={formData.notes || ''}
                onChange={handleChange}
                rows={3}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none resize-vertical"
                placeholder="Describe what you did during this time period..."
              />
            </div>

            {/* Payout Preview */}
            <div className="border-t pt-4">
              <button
                type="button"
                onClick={handlePreviewPayout}
                disabled={formData.job_id === 0 || formData.hours_worked <= 0}
                className="text-sm text-obatek hover:underline disabled:text-gray-400 disabled:no-underline"
              >
                Preview estimated pay
              </button>
              {payoutPreview && (
                <div className="mt-2 bg-green-50 border border-green-200 rounded-lg p-3">
                  <p className="text-sm font-semibold text-green-800">
                    Estimated Pay: {formatCurrency(payoutPreview.calculated_pay)}
                  </p>
                  <p className="text-xs text-green-600 mt-1">
                    Company materials are not included in your pay.
                  </p>
                </div>
              )}
            </div>

            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={createMutation.isPending || uploadingReceipts}
                className="bg-obatek text-white px-6 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors disabled:opacity-50"
              >
                {uploadingReceipts ? 'Uploading Receipts...' : createMutation.isPending ? 'Submitting...' : 'Submit'}
              </button>
            </div>
          </form>
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
          <div className="p-8 text-center text-gray-500">
            No timesheets yet. Submit your first timesheet above!
          </div>
        ) : (
          <div className="divide-y">
            {timesheets.map((ts: Timesheet) => (
              <div key={ts.id} className="p-4 hover:bg-gray-50 cursor-pointer" onClick={() => navigate(`/timesheets/${ts.id}`)}>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-gray-900">
                      {ts.job?.client_name} - {ts.job?.title}
                    </p>
                    <p className="text-sm text-gray-600">
                      {formatDate(ts.date)} | {ts.hours_worked} hours{parseFloat(ts.break_duration) > 0 ? ` | ${ts.break_duration}h break` : ''}
                      {ts.receipt_count > 0 && ` | ${ts.receipt_count} receipt${ts.receipt_count > 1 ? 's' : ''}`}
                    </p>
                    {ts.notes && (
                      <p className="text-sm text-gray-500 mt-1 truncate max-w-md">
                        {ts.notes}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    <p className="font-semibold text-obatek">
                      {ts.calculated_pay ? formatCurrency(ts.calculated_pay) : '-'}
                    </p>
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
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Assigned Jobs */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-4 border-b">
          <h2 className="text-lg font-semibold">Assigned Jobs</h2>
        </div>
        {loadingJobs ? (
          <div className="p-8 text-center text-gray-500">Loading...</div>
        ) : jobs.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            No active jobs assigned to you.
          </div>
        ) : (
          <div className="divide-y">
            {jobs.map((job) => (
              <div key={job.id} className="p-4 hover:bg-gray-50">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <p className="font-medium text-gray-900">{job.title}</p>
                    <p className="text-sm text-gray-600 mt-1">
                      {job.client?.name} | {job.job_address}
                    </p>
                    {job.my_scheduled_dates && job.my_scheduled_dates.length > 0 ? (
                      <p className="text-sm font-medium text-obatek mt-1">
                        Your days: {job.my_scheduled_dates.map(d => formatDate(d)).join(', ')}
                        {job.scheduled_time && ` at ${job.scheduled_time}`}
                      </p>
                    ) : job.start_date ? (
                      <p className="text-sm font-medium text-obatek mt-1">
                        {formatDate(job.start_date)}
                        {job.end_date && job.end_date !== job.start_date && ` – ${formatDate(job.end_date)}`}
                        {job.scheduled_time && ` at ${job.scheduled_time}`}
                      </p>
                    ) : null}
                    {job.client?.phone_number && (
                      <p className="text-sm text-gray-600 mt-1">
                        <span className="font-medium">Contact:</span>{' '}
                        <a
                          href={`tel:${job.client.phone_number}`}
                          className="text-obatek hover:underline"
                        >
                          {job.client.phone_number}
                        </a>
                      </p>
                    )}
                  </div>
                  {job.calculated_distance_km && (
                    <div className="text-sm text-gray-500 ml-4">
                      {job.calculated_distance_km} km
                    </div>
                  )}
                </div>
                {job.photos && job.photos.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {job.photos.map((photo) => (
                      <a key={photo.id} href={photo.public_url} target="_blank" rel="noopener noreferrer">
                        <img
                          src={photo.public_url}
                          alt={photo.caption || 'Job photo'}
                          className="w-20 h-20 object-cover rounded-lg border border-gray-200 hover:opacity-80 transition-opacity"
                        />
                      </a>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
