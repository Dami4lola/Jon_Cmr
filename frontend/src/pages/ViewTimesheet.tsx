import { useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { timesheetsApi } from '../api/timesheets';
import { formatCurrency, formatDate, roundToQuarter } from '../lib/utils';

export function ViewTimesheet() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

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

  const receiptSubtotal = receipts.reduce((sum, r) =>
    r.amount != null ? sum + parseFloat(String(r.amount)) : sum, 0);
  const anyReceiptAmounts = receipts.some((r) => r.amount != null);
  const receiptHstTotal = receiptSubtotal * 1.13;

  // Edit state
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState({
    hours_worked: '',
    break_duration: '',
    used_company_truck: false,
    worked_at_hq: false,
    company_materials: '',
    personal_materials: '',
    notes: '',
  });

  const updateMutation = useMutation({
    mutationFn: (data: typeof editData) =>
      timesheetsApi.update(Number(id), {
        hours_worked: data.hours_worked ? Number(data.hours_worked) : undefined,
        break_duration: data.break_duration ? Number(data.break_duration) : undefined,
        used_company_truck: data.used_company_truck,
        worked_at_hq: data.worked_at_hq,
        company_materials: data.company_materials ? Number(data.company_materials) : undefined,
        personal_materials: data.personal_materials ? Number(data.personal_materials) : undefined,
        notes: data.notes || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timesheets', id] });
      setIsEditing(false);
    },
  });

  const handleEditStart = () => {
    setEditData({
      hours_worked: String(timesheet!.hours_worked),
      break_duration: String(timesheet!.break_duration),
      used_company_truck: timesheet!.used_company_truck,
      worked_at_hq: timesheet!.worked_at_hq,
      company_materials: String(timesheet!.company_materials),
      personal_materials: String(timesheet!.personal_materials),
      notes: timesheet!.notes ?? '',
    });
    setIsEditing(true);
  };

  // Receipt upload state
  const fileInputRef = useRef<HTMLInputElement>(null);

  const uploadMutation = useMutation({
    mutationFn: (files: File[]) =>
      timesheetsApi.uploadReceipts(Number(id), files),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timesheets', id, 'receipts'] });
      queryClient.invalidateQueries({ queryKey: ['timesheets', id] });
      if (fileInputRef.current) fileInputRef.current.value = '';
    },
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (files.length > 0) uploadMutation.mutate(files);
  };

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
        <div className="flex items-center gap-2 print:hidden">
          {!timesheet.is_paid && !isEditing && (
            <button
              onClick={handleEditStart}
              className="bg-gray-100 text-gray-700 px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-200 transition-colors"
            >
              Edit
            </button>
          )}
          {isEditing && (
            <>
              <button
                onClick={() => setIsEditing(false)}
                className="bg-gray-100 text-gray-700 px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-200 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => updateMutation.mutate(editData)}
                disabled={updateMutation.isPending}
                className="bg-obatek text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-obatek-dark transition-colors disabled:opacity-50"
              >
                {updateMutation.isPending ? 'Saving...' : 'Save'}
              </button>
            </>
          )}
          <button
            onClick={() => window.print()}
            className="bg-obatek text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-obatek-dark transition-colors"
          >
            Print / Save PDF
          </button>
        </div>
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
              {timesheet.is_paid && (
                <span className="inline-block mt-1 bg-green-500 text-white text-xs font-semibold px-2 py-0.5 rounded-full">
                  Paid
                </span>
              )}
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
            {isEditing ? (
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-gray-500 block mb-1">Hours Worked</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="24"
                    value={editData.hours_worked}
                    onChange={(e) => setEditData((d) => ({ ...d, hours_worked: e.target.value }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-obatek"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 block mb-1">Break Duration (hrs)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="24"
                    value={editData.break_duration}
                    onChange={(e) => setEditData((d) => ({ ...d, break_duration: e.target.value }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-obatek"
                  />
                </div>
              </div>
            ) : (
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
            )}
          </div>

          {/* Flags */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Work Details</h3>
            {isEditing ? (
              <div className="grid grid-cols-2 gap-4">
                <label className="flex items-center gap-3 border border-gray-200 rounded-lg p-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={editData.used_company_truck}
                    onChange={(e) => setEditData((d) => ({ ...d, used_company_truck: e.target.checked }))}
                    className="w-4 h-4 accent-obatek"
                  />
                  <span className="text-sm font-medium text-gray-900">Company Truck</span>
                </label>
                <label className="flex items-center gap-3 border border-gray-200 rounded-lg p-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={editData.worked_at_hq}
                    onChange={(e) => setEditData((d) => ({ ...d, worked_at_hq: e.target.checked }))}
                    className="w-4 h-4 accent-obatek"
                  />
                  <span className="text-sm font-medium text-gray-900">Worked at HQ</span>
                </label>
              </div>
            ) : (
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
            )}
          </div>

          {/* Notes */}
          {(isEditing || timesheet.notes) && (
            <div>
              <h3 className="text-sm font-semibold text-gray-900 mb-3">Notes</h3>
              {isEditing ? (
                <textarea
                  value={editData.notes}
                  onChange={(e) => setEditData((d) => ({ ...d, notes: e.target.value }))}
                  rows={3}
                  placeholder="Add notes..."
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-obatek resize-none"
                />
              ) : (
                <div className="bg-gray-50 rounded-lg p-4">
                  <p className="text-sm text-gray-700 whitespace-pre-wrap">{timesheet.notes}</p>
                </div>
              )}
            </div>
          )}

          {/* Divider */}
          <hr className="border-gray-200" />

          {/* Expenses Section */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Expenses & Materials</h3>
            {isEditing ? (
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-gray-500 block mb-1">Company Materials ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={editData.company_materials}
                    onChange={(e) => setEditData((d) => ({ ...d, company_materials: e.target.value }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-obatek"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 block mb-1">Personal Materials ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={editData.personal_materials}
                    onChange={(e) => setEditData((d) => ({ ...d, personal_materials: e.target.value }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-obatek"
                  />
                </div>
              </div>
            ) : (
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
            )}
          </div>

          {/* Receipt Images */}
          {(receipts.length > 0 || !timesheet.is_paid) && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-gray-900">
                  Receipt Images ({receipts.length})
                </h3>
                {!timesheet.is_paid && (
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploadMutation.isPending}
                    className="text-sm text-obatek hover:text-obatek-dark font-medium disabled:opacity-50 print:hidden"
                  >
                    {uploadMutation.isPending ? 'Uploading...' : '+ Add Receipts'}
                  </button>
                )}
              </div>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept="image/*"
                className="hidden"
                onChange={handleFileChange}
              />
              {receipts.length > 0 && (
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
                      {receipt.amount != null && (
                        <p className="text-xs font-medium text-gray-700 px-2 pb-2">{formatCurrency(receipt.amount)}</p>
                      )}
                    </a>
                  ))}
                </div>
              )}
              {anyReceiptAmounts && (
                <div className="mt-3 pt-3 border-t border-gray-200 space-y-1">
                  <div className="flex justify-between text-sm text-gray-600">
                    <span>Receipt Subtotal</span>
                    <span className="font-medium text-gray-900">{formatCurrency(receiptSubtotal.toFixed(2))}</span>
                  </div>
                  <div className="flex justify-between text-sm text-gray-600">
                    <span>Receipt Total (incl. HST 13%)</span>
                    <span className="font-medium text-gray-900">{formatCurrency(receiptHstTotal.toFixed(2))}</span>
                  </div>
                </div>
              )}
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
