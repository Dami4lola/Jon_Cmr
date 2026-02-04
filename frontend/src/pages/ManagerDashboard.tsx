import { useQuery } from '@tanstack/react-query';
import { timesheetsApi } from '../api/timesheets';
import { jobsApi } from '../api/jobs';
import { formatCurrency, formatDate } from '../lib/utils';
import type { Timesheet, Job } from '../types';

export function ManagerDashboard() {
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

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Manager Dashboard</h1>

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
