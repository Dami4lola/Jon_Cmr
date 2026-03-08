import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { timesheetsApi } from '../api/timesheets';
import { formatCurrency, formatDate, roundToQuarter } from '../lib/utils';

export function ViewTimesheet() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: timesheet, isLoading } = useQuery({
    queryKey: ['timesheets', id],
    queryFn: () => timesheetsApi.get(Number(id)),
    enabled: !!id,
  });

  const { data: receipts = [] } = useQuery({
    queryKey: ['timesheets', id, 'receipts'],
    queryFn: () => timesheetsApi.getReceipts(Number(id)),
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
        Loading...
      </div>
    );
  }

  if (!timesheet) {
    return (
      <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
        Timesheet not found.
      </div>
    );
  }

  const hoursWorked = parseFloat(timesheet.hours_worked);
  const roundedHours = roundToQuarter(hoursWorked);

  return (
    <div className="space-y-4 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => navigate(-1)}
          className="text-sm text-gray-600 hover:text-gray-900 flex items-center gap-1"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back
        </button>
        <button
          onClick={() => window.print()}
          className="bg-obatek text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-obatek-dark transition-colors print:hidden"
        >
          Print / Save PDF
        </button>
      </div>

      {/* PDF-like Document */}
      <div className="bg-white rounded-lg shadow-lg print:shadow-none">
        {/* Document Header */}
        <div className="bg-gradient-to-r from-obatek to-obatek-dark p-6 rounded-t-lg print:bg-obatek">
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-2xl font-bold text-white">Timesheet</h1>
              <p className="text-white/80 text-sm mt-1">#{timesheet.id}</p>
            </div>
            <div className="text-right text-white">
              <p className="text-lg font-semibold">{formatDate(timesheet.date)}</p>
              <p className="text-white/80 text-sm">
                Submitted {formatDate(timesheet.created_at)}
              </p>
            </div>
          </div>
        </div>

        <div className="p-6 space-y-6">
          {/* Worker & Job Info */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-gray-50 rounded-lg p-4">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                Worker
              </h3>
              <p className="text-lg font-semibold text-gray-900">
                {timesheet.worker?.name || 'Unknown'}
              </p>
            </div>
            <div className="bg-gray-50 rounded-lg p-4">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                Job
              </h3>
              <p className="text-lg font-semibold text-gray-900">
                {timesheet.job?.title}
              </p>
              <p className="text-sm text-gray-600">
                {timesheet.job?.client_name}
              </p>
            </div>
          </div>

          {/* Divider */}
          <hr className="border-gray-200" />

          {/* Hours Section */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Hours</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div className="border border-gray-200 rounded-lg p-3">
                <p className="text-xs text-gray-500">Hours Worked</p>
                <p className="text-xl font-bold text-gray-900">{hoursWorked}</p>
              </div>
              <div className="border border-gray-200 rounded-lg p-3">
                <p className="text-xs text-gray-500">Rounded Hours</p>
                <p className="text-xl font-bold text-gray-900">{roundedHours}</p>
              </div>
              {parseFloat(timesheet.break_duration) > 0 && (
                <div className="border border-gray-200 rounded-lg p-3">
                  <p className="text-xs text-gray-500">Break Duration</p>
                  <p className="text-xl font-bold text-gray-900">
                    {parseFloat(timesheet.break_duration).toFixed(2)}h
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Flags */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Work Details</h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="flex items-center gap-3 border border-gray-200 rounded-lg p-3">
                <div className={`w-3 h-3 rounded-full ${timesheet.used_company_truck ? 'bg-green-500' : 'bg-gray-300'}`} />
                <div>
                  <p className="text-sm font-medium text-gray-900">Company Truck</p>
                  <p className="text-xs text-gray-500">
                    {timesheet.used_company_truck ? 'Yes' : 'No'}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3 border border-gray-200 rounded-lg p-3">
                <div className={`w-3 h-3 rounded-full ${timesheet.worked_at_hq ? 'bg-green-500' : 'bg-gray-300'}`} />
                <div>
                  <p className="text-sm font-medium text-gray-900">Worked at HQ</p>
                  <p className="text-xs text-gray-500">
                    {timesheet.worked_at_hq ? 'Yes' : 'No'}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Divider */}
          <hr className="border-gray-200" />

          {/* Expenses Section */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Expenses & Materials</h3>
            <div className="space-y-2">
              <div className="flex justify-between items-center py-2 border-b border-gray-100">
                <span className="text-sm text-gray-600">Company Materials</span>
                <span className="text-sm font-medium text-gray-900">
                  {formatCurrency(timesheet.company_materials)}
                </span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-gray-100">
                <span className="text-sm text-gray-600">Personal Materials</span>
                <span className="text-sm font-medium text-gray-900">
                  {formatCurrency(timesheet.personal_materials)}
                </span>
              </div>
            </div>
          </div>

          {/* Receipt Images */}
          {receipts.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-900 mb-3">
                Receipt Images ({receipts.length})
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {receipts.map((receipt) => (
                  <a
                    key={receipt.id}
                    href={receipt.image_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block border border-gray-200 rounded-lg overflow-hidden hover:border-obatek transition-colors"
                  >
                    <img
                      src={receipt.image_url}
                      alt={receipt.description || `Receipt ${receipt.id}`}
                      className="w-full h-32 object-cover"
                    />
                    {receipt.description && (
                      <p className="text-xs text-gray-600 p-2 truncate">{receipt.description}</p>
                    )}
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* Divider */}
          <hr className="border-gray-200" />

          {/* Total Payout */}
          <div className="bg-obatek/5 border border-obatek/20 rounded-lg p-4">
            <div className="flex justify-between items-center">
              <span className="text-lg font-semibold text-gray-900">Total Calculated Pay</span>
              <span className="text-2xl font-bold text-obatek">
                {timesheet.calculated_pay
                  ? formatCurrency(timesheet.calculated_pay)
                  : 'Not calculated'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
