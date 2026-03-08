import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { timesheetsApi } from '../api/timesheets';
import { formatCurrency, formatDate } from '../lib/utils';
import type { Timesheet } from '../types';

export function PaidTimesheets() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: timesheets = [], isLoading } = useQuery<Timesheet[]>({
    queryKey: ['timesheets', 'paid'],
    queryFn: () => timesheetsApi.listPaid(),
  });

  const markUnpaidMutation = useMutation({
    mutationFn: timesheetsApi.markUnpaid,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timesheets', 'paid'] });
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
          <h1 className="text-2xl font-bold text-gray-900">Paid Timesheets</h1>
        </div>
      </div>

      {isLoading ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">Loading...</div>
      ) : timesheets.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
          No paid timesheets yet.
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr className="text-left text-gray-500 border-b">
                  <th className="px-4 py-3 font-medium">Worker</th>
                  <th className="px-4 py-3 font-medium">Job</th>
                  <th className="px-4 py-3 font-medium">Date</th>
                  <th className="px-4 py-3 font-medium text-right">Hours</th>
                  <th className="px-4 py-3 font-medium text-right">Break</th>
                  <th className="px-4 py-3 font-medium text-right">Pay</th>
                  <th className="px-4 py-3 font-medium text-center">Status</th>
                  <th className="px-4 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {timesheets.map((ts: Timesheet) => (
                  <tr
                    key={ts.id}
                    className="hover:bg-gray-50 cursor-pointer"
                    onClick={() => navigate(`/timesheets/${ts.id}`)}
                  >
                    <td className="px-4 py-3 text-gray-900">{ts.worker?.name || 'Unknown'}</td>
                    <td className="px-4 py-3 text-gray-600">
                      <div>{ts.job?.title}</div>
                      <div className="text-xs text-gray-400">{ts.job?.client_name}</div>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{formatDate(ts.date)}</td>
                    <td className="px-4 py-3 text-right text-gray-600">
                      {parseFloat(ts.hours_worked).toFixed(1)}h
                    </td>
                    <td className="px-4 py-3 text-right text-gray-600">
                      {parseFloat(ts.break_duration) > 0
                        ? `${parseFloat(ts.break_duration).toFixed(1)}h`
                        : '—'}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-900 font-medium">
                      {ts.calculated_pay ? formatCurrency(ts.calculated_pay) : '—'}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className="px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-700">
                        Paid
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (window.confirm('Mark this timesheet as unpaid? It will be included in the next payroll run.')) {
                            markUnpaidMutation.mutate(ts.id);
                          }
                        }}
                        disabled={markUnpaidMutation.isPending}
                        className="text-xs text-orange-600 hover:underline"
                      >
                        Mark Unpaid
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
