import { useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { timesheetsApi } from '../api/timesheets';
import { formatCurrency, formatDate, roundToQuarter } from '../lib/utils';
import type { InventoryItem } from '../types';

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

  const { data: inventoryItems = [] } = useQuery({
    queryKey: ['timesheets', id, 'inventory-items'],
    queryFn: () => timesheetsApi.getInventoryItems(Number(id)),
    enabled: !!id,
  });

  // Receipt totals
  const receiptBeforeTaxTotal = receipts.reduce(
    (sum, r) => (r.amount != null ? sum + parseFloat(String(r.amount)) : sum), 0
  );
  const receiptAfterTaxTotal = receipts.reduce(
    (sum, r) => (r.amount_after_tax != null ? sum + parseFloat(String(r.amount_after_tax)) : sum), 0
  );
  const anyReceiptAmounts = receipts.some((r) => r.amount != null || r.amount_after_tax != null);

  // Edit state
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState({
    hours_worked: '',
    break_duration: '',
    used_company_truck: false,
    worked_at_hq: false,
    personal_materials: '',
    company_materials: '',
    notes: '',
  });

  const updateMutation = useMutation({
    mutationFn: (data: typeof editData) =>
      timesheetsApi.update(Number(id), {
        hours_worked: data.hours_worked ? Number(data.hours_worked) : undefined,
        break_duration: data.break_duration ? Number(data.break_duration) : undefined,
        used_company_truck: data.used_company_truck,
        worked_at_hq: data.worked_at_hq,
        personal_materials: data.personal_materials ? Number(data.personal_materials) : undefined,
        company_materials: data.company_materials ? Number(data.company_materials) : undefined,
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
      personal_materials: String(timesheet!.personal_materials),
      company_materials: String(timesheet!.company_materials),
      notes: timesheet!.notes ?? '',
    });
    setIsEditing(true);
  };

  // Receipt upload — shows modal before uploading
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [receiptMeta, setReceiptMeta] = useState({
    description: '',
    amountBeforeTax: '',
    amountAfterTax: '',
  });

  const uploadMutation = useMutation({
    mutationFn: ({ file, meta }: { file: File; meta: typeof receiptMeta }) =>
      timesheetsApi.uploadReceipt(Number(id), file, {
        description: meta.description || undefined,
        amountBeforeTax: meta.amountBeforeTax || undefined,
        amountAfterTax: meta.amountAfterTax || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timesheets', id, 'receipts'] });
      queryClient.invalidateQueries({ queryKey: ['timesheets', id] });
      setPendingFile(null);
      setReceiptMeta({ description: '', amountBeforeTax: '', amountAfterTax: '' });
      if (fileInputRef.current) fileInputRef.current.value = '';
    },
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setPendingFile(file);
      setReceiptMeta({ description: '', amountBeforeTax: '', amountAfterTax: '' });
    }
  };

  const handleReceiptSubmit = () => {
    if (pendingFile) uploadMutation.mutate({ file: pendingFile, meta: receiptMeta });
  };

  const deleteReceiptMutation = useMutation({
    mutationFn: (receiptId: number) => timesheetsApi.deleteReceipt(receiptId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timesheets', id, 'receipts'] });
      queryClient.invalidateQueries({ queryKey: ['timesheets', id] });
    },
  });

  // Inventory items
  const [showAddItem, setShowAddItem] = useState(false);
  const [newItemDesc, setNewItemDesc] = useState('');
  const [newItemQty, setNewItemQty] = useState('');

  const addItemMutation = useMutation({
    mutationFn: () =>
      timesheetsApi.addInventoryItem(Number(id), {
        description: newItemDesc.trim(),
        quantity: newItemQty.trim(),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timesheets', id, 'inventory-items'] });
      setNewItemDesc('');
      setNewItemQty('');
      setShowAddItem(false);
    },
  });

  const deleteItemMutation = useMutation({
    mutationFn: (itemId: number) => timesheetsApi.deleteInventoryItem(itemId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timesheets', id, 'inventory-items'] });
    },
  });

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">Loading...</div>
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
  const canEdit = !timesheet.is_paid;

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
          {canEdit && !isEditing && (
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

      {/* Document */}
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
              <p className="text-white/80 text-sm">Submitted {formatDate(timesheet.created_at)}</p>
              {timesheet.is_paid && (
                <span className="inline-block mt-1 bg-green-500 text-white text-xs font-semibold px-2 py-0.5 rounded-full">
                  Paid
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="p-6 space-y-6">
          {/* Worker & Job */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-gray-50 rounded-lg p-4">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Worker</h3>
              <p className="text-lg font-semibold text-gray-900">{timesheet.worker?.name || 'Unknown'}</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-4">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Job</h3>
              <p className="text-lg font-semibold text-gray-900">{timesheet.job?.title}</p>
              <p className="text-sm text-gray-600">{timesheet.job?.client_name}</p>
            </div>
          </div>

          <hr className="border-gray-200" />

          {/* Hours */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Hours</h3>
            {isEditing ? (
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-gray-500 block mb-1">Hours Worked</label>
                  <input type="number" step="0.01" min="0" max="24"
                    value={editData.hours_worked}
                    onChange={(e) => setEditData((d) => ({ ...d, hours_worked: e.target.value }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-obatek"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 block mb-1">Break Duration (hrs)</label>
                  <input type="number" step="0.01" min="0" max="24"
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

          {/* Work Details */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Work Details</h3>
            {isEditing ? (
              <div className="grid grid-cols-2 gap-4">
                <label className="flex items-center gap-3 border border-gray-200 rounded-lg p-3 cursor-pointer">
                  <input type="checkbox" checked={editData.used_company_truck}
                    onChange={(e) => setEditData((d) => ({ ...d, used_company_truck: e.target.checked }))}
                    className="w-4 h-4 accent-obatek"
                  />
                  <span className="text-sm font-medium text-gray-900">Company Truck</span>
                </label>
                <label className="flex items-center gap-3 border border-gray-200 rounded-lg p-3 cursor-pointer">
                  <input type="checkbox" checked={editData.worked_at_hq}
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
                    <p className="text-xs text-gray-500">{timesheet.used_company_truck ? 'Yes' : 'No'}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 border border-gray-200 rounded-lg p-3">
                  <div className={`w-3 h-3 rounded-full ${timesheet.worked_at_hq ? 'bg-green-500' : 'bg-gray-300'}`} />
                  <div>
                    <p className="text-sm font-medium text-gray-900">Worked at HQ</p>
                    <p className="text-xs text-gray-500">{timesheet.worked_at_hq ? 'Yes' : 'No'}</p>
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
                <textarea value={editData.notes}
                  onChange={(e) => setEditData((d) => ({ ...d, notes: e.target.value }))}
                  rows={3} placeholder="Add notes..."
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-obatek resize-none"
                />
              ) : (
                <div className="bg-gray-50 rounded-lg p-4">
                  <p className="text-sm text-gray-700 whitespace-pre-wrap">{timesheet.notes}</p>
                </div>
              )}
            </div>
          )}

          <hr className="border-gray-200" />

          {/* ===== EXPENSES & MATERIALS ===== */}
          <div className="space-y-5">
            <h3 className="text-sm font-semibold text-gray-900">Expenses & Materials</h3>

            {/* Section 1: Personal Materials */}
            <div className="border border-gray-200 rounded-lg p-4">
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
                1. Personal Materials (before tax)
              </h4>
              <p className="text-xs text-gray-400 mb-3">Amount you personally spent — to be reimbursed</p>
              {isEditing ? (
                <input type="number" step="0.01" min="0"
                  value={editData.personal_materials}
                  onChange={(e) => setEditData((d) => ({ ...d, personal_materials: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-obatek"
                  placeholder="0.00"
                />
              ) : (
                <p className="text-xl font-bold text-gray-900">
                  {formatCurrency(timesheet.personal_materials)}
                </p>
              )}
            </div>

            {/* Section 2: Business Receipts */}
            <div className="border border-gray-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-1">
                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  2. Business Purchased Materials
                </h4>
                {canEdit && (
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploadMutation.isPending}
                    className="text-xs text-obatek hover:text-obatek-dark font-medium disabled:opacity-50 print:hidden"
                  >
                    {uploadMutation.isPending ? 'Uploading...' : '+ Add Receipt'}
                  </button>
                )}
              </div>
              <p className="text-xs text-gray-400 mb-3">Company purchases — attach receipt photos with prices</p>
              <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handleFileChange} />

              {receipts.length === 0 ? (
                <p className="text-sm text-gray-400 italic">No receipts uploaded yet</p>
              ) : (
                <div className="space-y-3">
                  {receipts.map((receipt) => (
                    <div key={receipt.id} className="flex gap-3 items-start border border-gray-100 rounded-lg p-3 bg-gray-50">
                      <a href={receipt.image_url} target="_blank" rel="noopener noreferrer" className="shrink-0">
                        <img src={receipt.image_url} alt={receipt.description || 'Receipt'} className="w-16 h-16 object-cover rounded border border-gray-200" />
                      </a>
                      <div className="flex-1 min-w-0">
                        {receipt.description && (
                          <p className="text-sm font-medium text-gray-800 truncate">{receipt.description}</p>
                        )}
                        <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-gray-600">
                          {receipt.amount != null && (
                            <span>Before tax: <span className="font-semibold text-gray-800">{formatCurrency(receipt.amount)}</span></span>
                          )}
                          {receipt.amount_after_tax != null && (
                            <span>After tax: <span className="font-semibold text-gray-800">{formatCurrency(receipt.amount_after_tax)}</span></span>
                          )}
                        </div>
                      </div>
                      {canEdit && (
                        <button
                          onClick={() => deleteReceiptMutation.mutate(receipt.id)}
                          className="text-red-400 hover:text-red-600 shrink-0 print:hidden"
                          title="Delete receipt"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {anyReceiptAmounts && (
                <div className="mt-3 pt-3 border-t border-gray-200 space-y-1">
                  {receiptBeforeTaxTotal > 0 && (
                    <div className="flex justify-between text-sm text-gray-600">
                      <span>Receipts total (before tax)</span>
                      <span className="font-medium text-gray-900">{formatCurrency(receiptBeforeTaxTotal.toFixed(2))}</span>
                    </div>
                  )}
                  {receiptAfterTaxTotal > 0 && (
                    <div className="flex justify-between text-sm text-gray-600">
                      <span>Receipts total (after tax)</span>
                      <span className="font-medium text-gray-900">{formatCurrency(receiptAfterTaxTotal.toFixed(2))}</span>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Section 3: Inventory Items */}
            <div className="border border-gray-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-1">
                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  3. Business Inventory Used
                </h4>
                {canEdit && !showAddItem && (
                  <button
                    onClick={() => setShowAddItem(true)}
                    className="text-xs text-obatek hover:text-obatek-dark font-medium print:hidden"
                  >
                    + Add Item
                  </button>
                )}
              </div>
              <p className="text-xs text-gray-400 mb-3">Company stock consumed — description and quantity</p>

              {inventoryItems.length === 0 && !showAddItem && (
                <p className="text-sm text-gray-400 italic">No inventory items recorded</p>
              )}

              {inventoryItems.length > 0 && (
                <div className="space-y-2 mb-3">
                  {inventoryItems.map((item: InventoryItem) => (
                    <div key={item.id} className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2 border border-gray-100">
                      <div className="flex-1 min-w-0">
                        <span className="text-sm font-medium text-gray-800">{item.description}</span>
                        {item.quantity && (
                          <span className="text-xs text-gray-500 ml-2">— {item.quantity}</span>
                        )}
                      </div>
                      {canEdit && (
                        <button
                          onClick={() => deleteItemMutation.mutate(item.id)}
                          className="text-red-400 hover:text-red-600 ml-3 print:hidden"
                          title="Remove item"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {showAddItem && (
                <div className="bg-gray-50 rounded-lg p-3 border border-gray-200 space-y-2">
                  <input
                    type="text"
                    placeholder="Description (e.g. 2×4 lumber, PVC pipe)"
                    value={newItemDesc}
                    onChange={(e) => setNewItemDesc(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-obatek"
                  />
                  <input
                    type="text"
                    placeholder="Quantity (e.g. 6 pieces, 2 bags)"
                    value={newItemQty}
                    onChange={(e) => setNewItemQty(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-obatek"
                  />
                  <div className="flex gap-2 justify-end">
                    <button
                      onClick={() => { setShowAddItem(false); setNewItemDesc(''); setNewItemQty(''); }}
                      className="text-xs text-gray-500 hover:text-gray-700 px-3 py-1"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => addItemMutation.mutate()}
                      disabled={!newItemDesc.trim() || addItemMutation.isPending}
                      className="text-xs bg-obatek text-white px-3 py-1 rounded-lg disabled:opacity-50 hover:bg-obatek-dark"
                    >
                      {addItemMutation.isPending ? 'Adding...' : 'Add'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>

          <hr className="border-gray-200" />

          {/* Total Calculated Pay */}
          <div className="bg-obatek/5 border border-obatek/20 rounded-lg p-4">
            <div className="flex justify-between items-center">
              <span className="text-lg font-semibold text-gray-900">Total Calculated Pay</span>
              <span className="text-2xl font-bold text-obatek">
                {timesheet.calculated_pay ? formatCurrency(timesheet.calculated_pay) : 'Not calculated'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Receipt Upload Modal */}
      {pendingFile && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-sm w-full p-6">
            <h3 className="text-base font-semibold text-gray-900 mb-1">Upload Receipt</h3>
            <p className="text-sm text-gray-500 mb-4 truncate">{pendingFile.name}</p>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Description (optional)</label>
                <input
                  type="text"
                  placeholder="e.g. Lumber from Home Depot"
                  value={receiptMeta.description}
                  onChange={(e) => setReceiptMeta((m) => ({ ...m, description: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-obatek"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Price before tax ($)</label>
                  <input
                    type="number" step="0.01" min="0"
                    placeholder="0.00"
                    value={receiptMeta.amountBeforeTax}
                    onChange={(e) => setReceiptMeta((m) => ({ ...m, amountBeforeTax: e.target.value }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-obatek"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Price after tax ($)</label>
                  <input
                    type="number" step="0.01" min="0"
                    placeholder="0.00"
                    value={receiptMeta.amountAfterTax}
                    onChange={(e) => setReceiptMeta((m) => ({ ...m, amountAfterTax: e.target.value }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-obatek"
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-5">
              <button
                onClick={() => { setPendingFile(null); if (fileInputRef.current) fileInputRef.current.value = ''; }}
                className="px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleReceiptSubmit}
                disabled={uploadMutation.isPending}
                className="bg-obatek text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-obatek-dark disabled:opacity-50"
              >
                {uploadMutation.isPending ? 'Uploading...' : 'Upload'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
