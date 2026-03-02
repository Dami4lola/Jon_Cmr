import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { invoicesApi, settingsApi } from '../api/invoices';
import { jobsApi } from '../api/jobs';
import { formatCurrency, formatDate } from '../lib/utils';
import type { Invoice, InvoicePreview, Job } from '../types';

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700',
  sent: 'bg-blue-100 text-blue-700',
  paid: 'bg-green-100 text-green-700',
  overdue: 'bg-red-100 text-red-700',
};

export function Invoices() {
  const queryClient = useQueryClient();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [step, setStep] = useState<'select' | 'details'>('select');
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);

  // Editable form fields
  const [labourAmount, setLabourAmount] = useState(0);
  const [labourHours, setLabourHours] = useState(0);
  const [travelAmount, setTravelAmount] = useState(0);
  const [travelKm, setTravelKm] = useState(0);
  const [materialsAmount, setMaterialsAmount] = useState(0);
  const [inventoryMaterials, setInventoryMaterials] = useState(0);
  const [dumpFee, setDumpFee] = useState(0);
  const [adminFee, setAdminFee] = useState(0);
  const [includeHst, setIncludeHst] = useState(true);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [invoiceStartNumber, setInvoiceStartNumber] = useState(1);
  const [scopeOfWork, setScopeOfWork] = useState('');
  const [notes, setNotes] = useState('');

  // Fetch invoices
  const { data: invoices = [], isLoading: loadingInvoices } = useQuery({
    queryKey: ['invoices'],
    queryFn: () => invoicesApi.list(),
  });

  // Fetch jobs for creation
  const { data: jobs = [] } = useQuery({
    queryKey: ['jobs', 'all'],
    queryFn: () => jobsApi.list(),
  });

  // Fetch preview when job is selected
  const { data: preview, isFetching: loadingPreview } = useQuery<InvoicePreview>({
    queryKey: ['invoice-preview', selectedJobId],
    queryFn: () => invoicesApi.previewForJob(selectedJobId!),
    enabled: !!selectedJobId && step === 'select',
  });

  // Note: Form values are populated in handleNext() to avoid overwriting user edits

  // Pre-populate scope of work from job description when job is selected
  useEffect(() => {
    if (selectedJobId) {
      const job = jobs.find((j: Job) => j.id === selectedJobId);
      if (job?.details || job?.title) {
        const parts = [job.title, job.details].filter(Boolean);
      setScopeOfWork(parts.join('\n\n'));
      }
    }
  }, [selectedJobId, jobs]);

  const invoicedJobIds = new Set(invoices.map((inv: Invoice) => inv.job_id));
  const uninvoicedJobs = jobs.filter(
    (job: Job) => job.is_completed && !invoicedJobIds.has(job.id)
  );

  // Calculated totals
  const subtotal = labourAmount + travelAmount + materialsAmount + inventoryMaterials + dumpFee + adminFee;
  const hstAmount = includeHst ? subtotal * 0.13 : 0;
  const total = subtotal + hstAmount;

  const createMutation = useMutation({
    mutationFn: () =>
      invoicesApi.createForJob(selectedJobId!, {
        scope_of_work: scopeOfWork || undefined,
        labour_amount: labourAmount,
        travel_amount: travelAmount,
        materials_amount: materialsAmount,
        inventory_materials: inventoryMaterials,
        dump_fee: dumpFee,
        admin_fee: adminFee,
        total_labour_hours: labourHours,
        total_distance_km: travelKm,
        include_hst: includeHst,
        notes: notes || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      handleCloseModal();
    },
  });

  const updateStatusMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: Invoice['status'] }) =>
      invoicesApi.updateStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: invoicesApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
    },
  });

  const saveStartNumberMutation = useMutation({
    mutationFn: (value: number) => settingsApi.setInvoiceStartNumber(value),
    onSuccess: () => {
      setShowSettingsModal(false);
    },
  });

  const handleOpenSettings = async () => {
    try {
      const data = await settingsApi.getInvoiceStartNumber();
      setInvoiceStartNumber(data.value);
    } catch {
      setInvoiceStartNumber(1);
    }
    setShowSettingsModal(true);
  };

  const handleDownload = async (invoice: Invoice) => {
    try {
      await invoicesApi.downloadPdfToFile(invoice.id, invoice.invoice_number);
    } catch (error) {
      alert('Failed to download PDF');
    }
  };

  const handleCloseModal = () => {
    setShowCreateModal(false);
    setStep('select');
    setSelectedJobId(null);
    setLabourAmount(0);
    setLabourHours(0);
    setTravelAmount(0);
    setTravelKm(0);
    setMaterialsAmount(0);
    setInventoryMaterials(0);
    setDumpFee(0);
    setAdminFee(0);
    setIncludeHst(true);
    setScopeOfWork('');
    setNotes('');
  };

  const handleNext = () => {
    if (selectedJobId && preview) {
      setLabourAmount(parseFloat(preview.labour_amount));
      setLabourHours(parseFloat(preview.labour_hours));
      setTravelAmount(parseFloat(preview.travel_amount));
      setTravelKm(parseFloat(preview.travel_km));
      setMaterialsAmount(parseFloat(preview.materials_amount));
      setInventoryMaterials(parseFloat(preview.inventory_materials));
      setStep('details');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Invoices</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={handleOpenSettings}
            className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
            title="Invoice settings"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </button>
          {uninvoicedJobs.length > 0 && (
            <button
              onClick={() => setShowCreateModal(true)}
              className="bg-obatek text-white px-4 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors"
            >
              Create Invoice
            </button>
          )}
        </div>
      </div>

      {/* Invoice List */}
      <div className="bg-white rounded-lg shadow">
        {loadingInvoices ? (
          <div className="p-8 text-center text-gray-500">Loading...</div>
        ) : invoices.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            No invoices yet.{' '}
            {uninvoicedJobs.length > 0 && (
              <button
                onClick={() => setShowCreateModal(true)}
                className="text-obatek hover:underline"
              >
                Create one
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Invoice #</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Job</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Total</th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Status</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {invoices.map((invoice: Invoice) => (
                  <tr key={invoice.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">
                      {invoice.invoice_number}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {invoice.client?.name || invoice.job?.client?.name} - {invoice.job?.title}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {formatDate(invoice.created_date)}
                    </td>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900 text-right">
                      {formatCurrency(invoice.total)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <select
                        value={invoice.status}
                        onChange={(e) =>
                          updateStatusMutation.mutate({
                            id: invoice.id,
                            status: e.target.value as Invoice['status'],
                          })
                        }
                        className={`text-xs font-medium px-2 py-1 rounded-full border-0 cursor-pointer ${STATUS_COLORS[invoice.status]}`}
                      >
                        <option value="draft">Draft</option>
                        <option value="sent">Sent</option>
                        <option value="paid">Paid</option>
                        <option value="overdue">Overdue</option>
                      </select>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => handleDownload(invoice)}
                          className="text-obatek hover:text-obatek-dark transition-colors"
                          title="Download PDF"
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                        </button>
                        <button
                          onClick={() => {
                            if (window.confirm('Are you sure you want to delete this invoice?')) {
                              deleteMutation.mutate(invoice.id);
                            }
                          }}
                          className="text-red-400 hover:text-red-600 transition-colors"
                          title="Delete invoice"
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create Invoice Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50 overflow-y-auto">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full p-6 my-8">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">
                {step === 'select' ? 'Create Invoice — Select Job' : 'Create Invoice — Review & Edit'}
              </h3>
              <button onClick={handleCloseModal} className="text-gray-400 hover:text-gray-600">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {createMutation.isError && (
              <div className="bg-red-50 text-red-600 p-3 rounded-lg text-sm mb-4">
                Failed to create invoice. Please try again.
              </div>
            )}

            {/* Step 1: Job Selection */}
            {step === 'select' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Select Job</label>
                  <select
                    value={selectedJobId || ''}
                    onChange={(e) => setSelectedJobId(Number(e.target.value) || null)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  >
                    <option value="">Choose a completed job...</option>
                    {uninvoicedJobs.map((job: Job) => (
                      <option key={job.id} value={job.id}>
                        {job.client?.name} - {job.title}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Preview panel */}
                {selectedJobId && (
                  <div className="bg-gray-50 rounded-lg p-4">
                    <h4 className="text-sm font-semibold text-gray-700 mb-2">Auto-Calculated Preview</h4>
                    {loadingPreview ? (
                      <p className="text-sm text-gray-500">Calculating...</p>
                    ) : preview ? (
                      <div className="grid grid-cols-2 gap-2 text-sm">
                        <span className="text-gray-600">Labour ({preview.labour_hours} hrs)</span>
                        <span className="text-right font-medium">{formatCurrency(preview.labour_amount)}</span>
                        <span className="text-gray-600">Travel ({preview.travel_km} km)</span>
                        <span className="text-right font-medium">{formatCurrency(preview.travel_amount)}</span>
                        <span className="text-gray-600">Materials</span>
                        <span className="text-right font-medium">{formatCurrency(preview.materials_amount)}</span>
                        <div className="col-span-2 border-t mt-1 pt-1"></div>
                        <span className="text-gray-600">Subtotal</span>
                        <span className="text-right font-medium">{formatCurrency(preview.subtotal)}</span>
                        <span className="text-gray-600">HST (13%)</span>
                        <span className="text-right font-medium">{formatCurrency(preview.hst_amount)}</span>
                        <span className="font-semibold text-gray-900">Total</span>
                        <span className="text-right font-bold text-gray-900">{formatCurrency(preview.total)}</span>
                      </div>
                    ) : null}
                  </div>
                )}

                <div className="flex justify-end gap-3 mt-6">
                  <button
                    onClick={handleCloseModal}
                    className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleNext}
                    disabled={!selectedJobId || loadingPreview || !preview}
                    className="bg-obatek text-white px-6 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}

            {/* Step 2: Editable Details */}
            {step === 'details' && (
              <div className="space-y-5">
                {/* Charges */}
                <div>
                  <h4 className="text-sm font-semibold text-gray-900 mb-3">Charges</h4>
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">Labour Hours</label>
                        <input
                          type="number"
                          step="0.25"
                          value={labourHours}
                          onChange={(e) => setLabourHours(parseFloat(e.target.value) || 0)}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">Labour Amount ($)</label>
                        <input
                          type="number"
                          step="0.01"
                          value={labourAmount}
                          onChange={(e) => setLabourAmount(parseFloat(e.target.value) || 0)}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                        />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">Travel (km)</label>
                        <input
                          type="number"
                          step="0.1"
                          value={travelKm}
                          onChange={(e) => setTravelKm(parseFloat(e.target.value) || 0)}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">Travel Amount ($)</label>
                        <input
                          type="number"
                          step="0.01"
                          value={travelAmount}
                          onChange={(e) => setTravelAmount(parseFloat(e.target.value) || 0)}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                        />
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">Materials — before tax ($)</label>
                      <input
                        type="number"
                        step="0.01"
                        value={materialsAmount}
                        onChange={(e) => setMaterialsAmount(parseFloat(e.target.value) || 0)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">Inventory Materials ($)</label>
                        <input
                          type="number"
                          step="0.01"
                          value={inventoryMaterials}
                          onChange={(e) => setInventoryMaterials(parseFloat(e.target.value) || 0)}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">Dump Fee ($)</label>
                        <input
                          type="number"
                          step="0.01"
                          value={dumpFee}
                          onChange={(e) => setDumpFee(parseFloat(e.target.value) || 0)}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                        />
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">Admin Fee ($)</label>
                      <input
                        type="number"
                        step="0.01"
                        value={adminFee}
                        onChange={(e) => setAdminFee(parseFloat(e.target.value) || 0)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                      />
                    </div>
                  </div>
                </div>

                {/* Live Totals */}
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="grid grid-cols-2 gap-1 text-sm">
                    <span className="text-gray-600">Subtotal</span>
                    <span className="text-right font-medium">${subtotal.toFixed(2)}</span>
                    <span className="text-gray-600">HST (13%)</span>
                    <span className="text-right font-medium">${hstAmount.toFixed(2)}</span>
                    <span className="font-semibold text-gray-900 pt-1 border-t mt-1">Total Due</span>
                    <span className="text-right font-bold text-gray-900 pt-1 border-t mt-1">${total.toFixed(2)}</span>
                  </div>
                </div>

                {/* HST Toggle */}
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={includeHst}
                    onChange={(e) => setIncludeHst(e.target.checked)}
                    className="w-4 h-4 text-obatek rounded border-gray-300 focus:ring-obatek"
                  />
                  <span className="text-sm text-gray-700">Include HST (13%)</span>
                </label>

                {/* Scope of Work */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Scope of Work</label>
                  <textarea
                    rows={5}
                    value={scopeOfWork}
                    onChange={(e) => setScopeOfWork(e.target.value)}
                    placeholder="Describe the work performed..."
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-obatek focus:border-transparent outline-none resize-y"
                  />
                </div>

                {/* Notes */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Notes (optional)</label>
                  <textarea
                    rows={2}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Additional notes for the invoice..."
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-obatek focus:border-transparent outline-none resize-y"
                  />
                </div>

                {/* Actions */}
                <div className="flex justify-between pt-2">
                  <button
                    onClick={() => setStep('select')}
                    className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                  >
                    Back
                  </button>
                  <div className="flex gap-3">
                    <button
                      onClick={handleCloseModal}
                      className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => createMutation.mutate()}
                      disabled={createMutation.isPending}
                      className="bg-obatek text-white px-6 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors disabled:opacity-50"
                    >
                      {createMutation.isPending ? 'Creating...' : 'Create Invoice'}
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
      {/* Settings Modal */}
      {showSettingsModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-sm w-full p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Invoice Settings</h3>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Next invoice number starts at
              </label>
              <input
                type="number"
                min={1}
                value={invoiceStartNumber}
                onChange={(e) => setInvoiceStartNumber(parseInt(e.target.value) || 1)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
              />
              <p className="text-xs text-gray-500 mt-1">
                New invoices will use at least this number (e.g., 18 gives INV-2026-0018).
              </p>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setShowSettingsModal(false)}
                className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => saveStartNumberMutation.mutate(invoiceStartNumber)}
                disabled={saveStartNumberMutation.isPending}
                className="bg-obatek text-white px-6 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors disabled:opacity-50"
              >
                {saveStartNumberMutation.isPending ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
