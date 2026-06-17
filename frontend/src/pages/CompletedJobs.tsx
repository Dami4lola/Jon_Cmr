import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { jobsApi } from '../api/jobs';
import { timesheetsApi } from '../api/timesheets';
import { formatCurrency, formatDate } from '../lib/utils';
import type { Job, Timesheet } from '../types';

export function CompletedJobs() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [expandedJobId, setExpandedJobId] = useState<number | null>(null);

  const { data: jobs = [], isLoading } = useQuery<Job[]>({
    queryKey: ['jobs', { completed: true }],
    queryFn: () => jobsApi.list({ is_completed: true }),
  });

  const { data: timesheets = [], isLoading: loadingTimesheets } = useQuery<Timesheet[]>({
    queryKey: ['timesheets-by-job', expandedJobId],
    queryFn: () => timesheetsApi.listByJob(expandedJobId!),
    enabled: !!expandedJobId,
  });

  const reactivateMutation = useMutation({
    mutationFn: jobsApi.markActive,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });

  const deleteJobMutation = useMutation({
    mutationFn: jobsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      if (expandedJobId) setExpandedJobId(null);
    },
    onError: (error: any) => {
      alert(error?.response?.data?.detail || 'Failed to delete job. Please try again.');
    },
  });

  const markUnpaidMutation = useMutation({
    mutationFn: timesheetsApi.markUnpaid,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timesheets-by-job', expandedJobId] });
      queryClient.invalidateQueries({ queryKey: ['timesheets'] });
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/manager')}
            className="text-gray-500 hover:text-gray-700 transition-colors"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <h1 className="text-2xl font-bold text-gray-900">Completed Jobs</h1>
        </div>
      </div>

      {isLoading ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">Loading...</div>
      ) : jobs.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
          No completed jobs yet.
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow divide-y">
          {jobs.map((job: Job) => (
            <div key={job.id}>
              {/* Job Row */}
              <div
                className="p-4 hover:bg-gray-50 cursor-pointer"
                onClick={() => setExpandedJobId(expandedJobId === job.id ? null : job.id)}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <svg
                        className={`w-4 h-4 text-gray-400 transition-transform ${expandedJobId === job.id ? 'rotate-90' : ''}`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                      <p className="font-medium text-gray-900">{job.title}</p>
                    </div>
                    <p className="text-sm text-gray-600 ml-6">
                      {job.client?.name} | {job.job_address}
                    </p>
                    {job.workers && job.workers.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1 ml-6">
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
                      <p className="text-sm text-gray-500">
                        {formatDate(job.start_date)}
                        {job.end_date && job.end_date !== job.start_date && ` – ${formatDate(job.end_date)}`}
                      </p>
                    )}
                    {job.estimate_amount && (
                      <p className="text-sm text-gray-500">
                        Est: {formatCurrency(job.estimate_amount)}
                      </p>
                    )}
                    <div className="flex gap-3 mt-2 justify-end">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (window.confirm('Reactivate this job? It will appear in active jobs again.')) {
                            reactivateMutation.mutate(job.id);
                          }
                        }}
                        disabled={reactivateMutation.isPending}
                        className="text-sm text-obatek hover:underline"
                      >
                        Reactivate
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (window.confirm('Permanently delete this job and all its timesheets? This cannot be undone.')) {
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

              {/* Expanded Timesheets */}
              {expandedJobId === job.id && (
                <div className="bg-gray-50 border-t px-4 py-3">
                  <h3 className="text-sm font-semibold text-gray-700 mb-2">Timesheets</h3>
                  {loadingTimesheets ? (
                    <p className="text-sm text-gray-500">Loading timesheets...</p>
                  ) : timesheets.length === 0 ? (
                    <p className="text-sm text-gray-500">No timesheets for this job.</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-left text-gray-500 border-b">
                            <th className="pb-2 font-medium">Worker</th>
                            <th className="pb-2 font-medium">Date</th>
                            <th className="pb-2 font-medium">Hours</th>
                            <th className="pb-2 font-medium text-right">Pay</th>
                            <th className="pb-2 font-medium text-center">Status</th>
                            <th className="pb-2 font-medium text-right">Actions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y">
                          {timesheets.map((ts: Timesheet) => (
                            <tr key={ts.id} className="hover:bg-white">
                              <td className="py-2">{ts.worker?.name || 'Unknown'}</td>
                              <td className="py-2">{formatDate(ts.date)}</td>
                              <td className="py-2">{parseFloat(ts.hours_worked).toFixed(1)}h</td>
                              <td className="py-2 text-right">
                                {ts.calculated_pay ? formatCurrency(ts.calculated_pay) : '—'}
                              </td>
                              <td className="py-2 text-center">
                                <span
                                  className={`px-2 py-0.5 text-xs rounded-full ${
                                    ts.is_paid
                                      ? 'bg-green-100 text-green-700'
                                      : 'bg-yellow-100 text-yellow-700'
                                  }`}
                                >
                                  {ts.is_paid ? 'Paid' : 'Unpaid'}
                                </span>
                              </td>
                              <td className="py-2 text-right">
                                {ts.is_paid && (
                                  <button
                                    onClick={() => {
                                      if (window.confirm('Mark this timesheet as unpaid? It will be included in the next payroll run.')) {
                                        markUnpaidMutation.mutate(ts.id);
                                      }
                                    }}
                                    disabled={markUnpaidMutation.isPending}
                                    className="text-xs text-orange-600 hover:underline"
                                  >
                                    Mark Unpaid
                                  </button>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
