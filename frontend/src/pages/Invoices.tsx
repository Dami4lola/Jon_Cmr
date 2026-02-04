import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { invoicesApi } from '../api/invoices';
import { jobsApi } from '../api/jobs';
import { formatCurrency, formatDate } from '../lib/utils';
import type { Invoice, Job } from '../types';

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700',
  sent: 'bg-blue-100 text-blue-700',
  paid: 'bg-green-100 text-green-700',
  overdue: 'bg-red-100 text-red-700',
};

export function Invoices() {
  const queryClient = useQueryClient();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [includeHst, setIncludeHst] = useState(true);

  // Fetch invoices
  const { data: invoices = [], isLoading: loadingInvoices } = useQuery({
    queryKey: ['invoices'],
    queryFn: () => invoicesApi.list(),
  });

  // Fetch jobs without invoices for creation
  const { data: jobs = [] } = useQuery({
    queryKey: ['jobs', 'all'],
    queryFn: () => jobsApi.list(),
  });

  // Jobs that are completed but don't have invoices
  const invoicedJobIds = new Set(invoices.map((inv: Invoice) => inv.job_id));
  const uninvoicedJobs = jobs.filter(
    (job: Job) => job.is_completed && !invoicedJobIds.has(job.id)
  );

  // Create invoice mutation
  const createMutation = useMutation({
    mutationFn: () =>
      invoicesApi.createForJob(selectedJobId!, { include_hst: includeHst }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      setShowCreateModal(false);
      setSelectedJobId(null);
    },
  });

  // Update status mutation
  const updateStatusMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: Invoice['status'] }) =>
      invoicesApi.updateStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
    },
  });

  // Download PDF
  const handleDownload = async (invoice: Invoice) => {
    try {
      await invoicesApi.downloadPdfToFile(invoice.id, invoice.invoice_number);
    } catch (error) {
      alert('Failed to download PDF');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Invoices</h1>
        {uninvoicedJobs.length > 0 && (
          <button
            onClick={() => setShowCreateModal(true)}
            className="bg-obatek text-white px-4 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors"
          >
            Create Invoice
          </button>
        )}
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
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Invoice #
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Job
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Date
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Total
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                    Status
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {invoices.map((invoice: Invoice) => (
                  <tr key={invoice.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">
                      {invoice.invoice_number}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {invoice.job?.client?.name} - {invoice.job?.description}
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
                        className={`text-xs font-medium px-2 py-1 rounded-full border-0 cursor-pointer ${
                          STATUS_COLORS[invoice.status]
                        }`}
                      >
                        <option value="draft">Draft</option>
                        <option value="sent">Sent</option>
                        <option value="paid">Paid</option>
                        <option value="overdue">Overdue</option>
                      </select>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => handleDownload(invoice)}
                        className="text-obatek hover:text-obatek-dark transition-colors"
                        title="Download PDF"
                      >
                        <svg
                          className="w-5 h-5"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                          />
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

      {/* Create Invoice Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <h3 className="text-lg font-semibold mb-4">Create Invoice</h3>

            {createMutation.isError && (
              <div className="bg-red-50 text-red-600 p-3 rounded-lg text-sm mb-4">
                Failed to create invoice. Please try again.
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Select Job
                </label>
                <select
                  value={selectedJobId || ''}
                  onChange={(e) => setSelectedJobId(Number(e.target.value))}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                >
                  <option value="">Choose a completed job...</option>
                  {uninvoicedJobs.map((job: Job) => (
                    <option key={job.id} value={job.id}>
                      {job.client?.name} - {job.description}
                    </option>
                  ))}
                </select>
              </div>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={includeHst}
                  onChange={(e) => setIncludeHst(e.target.checked)}
                  className="w-4 h-4 text-obatek rounded border-gray-300 focus:ring-obatek"
                />
                <span className="text-sm text-gray-700">Include HST (13%)</span>
              </label>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => {
                  setShowCreateModal(false);
                  setSelectedJobId(null);
                }}
                className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => createMutation.mutate()}
                disabled={!selectedJobId || createMutation.isPending}
                className="bg-obatek text-white px-6 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors disabled:opacity-50"
              >
                {createMutation.isPending ? 'Creating...' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
