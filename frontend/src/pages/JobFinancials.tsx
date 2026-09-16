import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { financialsApi } from '../api/financials';
import { clientsApi } from '../api/clients';
import { formatCurrency, formatDate } from '../lib/utils';
import type {
  Client,
  JobCostLineDetail,
  JobFinancialsDetail,
  JobFinancialsListResponse,
  JobFinancialsSummary,
  JobWorkerCostSummary,
} from '../types';

type CompletionFilter = 'all' | 'active' | 'completed';

const DASH = '—';

function completedParam(filter: CompletionFilter): boolean | undefined {
  if (filter === 'active') return false;
  if (filter === 'completed') return true;
  return undefined;
}

function marginToneClass(marginAmount: string | null): string {
  if (marginAmount === null) return 'text-gray-400';
  return parseFloat(marginAmount) < 0 ? 'text-red-600' : 'text-green-600';
}

function BudgetPill({ job }: { job: JobFinancialsSummary }) {
  if (job.budget_amount === null) {
    return (
      <span className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-700">
        No Budget
      </span>
    );
  }
  return (
    <span
      className={`px-2 py-0.5 text-xs rounded-full ${
        job.is_over_budget ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
      }`}
    >
      {job.is_over_budget ? 'Over Budget' : 'On Budget'}
    </span>
  );
}

function SpendBar({ job }: { job: JobFinancialsSummary }) {
  if (job.budget_amount === null || parseFloat(job.budget_amount) === 0) return null;

  const usedPercent = (parseFloat(job.subtotal_cost) / parseFloat(job.budget_amount)) * 100;
  const width = Math.min(Math.max(usedPercent, 0), 100);

  return (
    <div className="mt-2">
      <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-2 rounded-full ${job.is_over_budget ? 'bg-red-500' : 'bg-obatek'}`}
          style={{ width: `${width}%` }}
        />
      </div>
      <p className="text-xs text-gray-500 mt-1">
        {usedPercent.toFixed(0)}% of budget spent
      </p>
    </div>
  );
}

function CostLineRow({ entry }: { entry: JobCostLineDetail }) {
  return (
    <tr className="hover:bg-white">
      <td className="py-2 whitespace-nowrap">{formatDate(entry.date)}</td>
      <td className="py-2 text-right">{parseFloat(entry.hours_worked).toFixed(1)}h</td>
      <td className="py-2 text-right">{parseFloat(entry.billable_hours).toFixed(2)}h</td>
      <td className="py-2 text-right">{formatCurrency(entry.labour_cost)}</td>
      <td className="py-2 text-right">
        {entry.worked_at_hq ? (
          <span className="text-gray-400">HQ</span>
        ) : (
          formatCurrency(entry.km_cost)
        )}
      </td>
      <td className="py-2 text-right">{formatCurrency(entry.personal_materials)}</td>
      <td className="py-2 text-right">{formatCurrency(entry.company_materials)}</td>
      <td className="py-2 text-right font-medium">{formatCurrency(entry.subtotal_cost)}</td>
      <td className="py-2 text-center">
        <span
          className={`px-2 py-0.5 text-xs rounded-full ${
            entry.is_paid ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
          }`}
        >
          {entry.is_paid ? 'Paid' : 'Unpaid'}
        </span>
      </td>
    </tr>
  );
}

function WorkerCostCard({ worker }: { worker: JobWorkerCostSummary }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
        <div>
          <p className="font-medium text-gray-900">{worker.worker_name}</p>
          <p className="text-xs text-gray-500">
            {formatCurrency(worker.hourly_rate)}/hr · {parseFloat(worker.total_hours).toFixed(2)}h
            billable · {worker.timesheet_count}{' '}
            {worker.timesheet_count === 1 ? 'timesheet' : 'timesheets'}
            {worker.charges_hst && ' · charges HST'}
          </p>
        </div>
        <p className="text-lg font-bold text-gray-900">{formatCurrency(worker.total_cost)}</p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b">
              <th className="pb-2 font-medium">Date</th>
              <th className="pb-2 font-medium text-right">Hours</th>
              <th className="pb-2 font-medium text-right">Billable</th>
              <th className="pb-2 font-medium text-right">Labour</th>
              <th className="pb-2 font-medium text-right">Travel</th>
              <th className="pb-2 font-medium text-right">Worker Mat.</th>
              <th className="pb-2 font-medium text-right">Co. Mat.</th>
              <th className="pb-2 font-medium text-right">Line Total</th>
              <th className="pb-2 font-medium text-center">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {worker.entries.map((entry) => (
              <CostLineRow key={entry.timesheet_id} entry={entry} />
            ))}
          </tbody>
        </table>
      </div>

      <div className="border-t mt-2 pt-2 text-sm space-y-1">
        <div className="flex justify-between text-gray-600">
          <span>Subtotal (before tax)</span>
          <span>{formatCurrency(worker.subtotal_cost)}</span>
        </div>
        {worker.charges_hst && (
          <div className="flex justify-between text-gray-600">
            <span>HST (subcontractor)</span>
            <span>{formatCurrency(worker.total_hst)}</span>
          </div>
        )}
        <div className="flex justify-between font-semibold text-gray-900">
          <span>Total</span>
          <span>{formatCurrency(worker.total_cost)}</span>
        </div>
      </div>
    </div>
  );
}

function JobCostBreakdown({ financials }: { financials: JobFinancialsDetail }) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="border border-gray-200 rounded-lg p-3 bg-white">
          <p className="text-xs text-gray-500">Labour</p>
          <p className="text-lg font-semibold text-gray-900">
            {formatCurrency(financials.labour_cost)}
          </p>
        </div>
        <div className="border border-gray-200 rounded-lg p-3 bg-white">
          <p className="text-xs text-gray-500">Travel</p>
          <p className="text-lg font-semibold text-gray-900">
            {formatCurrency(financials.travel_cost)}
          </p>
        </div>
        <div className="border border-gray-200 rounded-lg p-3 bg-white">
          <p className="text-xs text-gray-500">Worker Materials</p>
          <p className="text-lg font-semibold text-gray-900">
            {formatCurrency(financials.personal_materials_cost)}
          </p>
        </div>
        <div className="border border-gray-200 rounded-lg p-3 bg-white">
          <p className="text-xs text-gray-500">Company Materials</p>
          <p className="text-lg font-semibold text-gray-900">
            {formatCurrency(financials.company_materials_cost)}
          </p>
        </div>
        <div className="border border-gray-200 rounded-lg p-3 bg-white">
          <p className="text-xs text-gray-500">Subcontractor HST</p>
          <p className="text-lg font-semibold text-gray-900">
            {formatCurrency(financials.hst_cost)}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-gray-600">
        <span>
          Pre-tax cost:{' '}
          <span className="font-medium text-gray-900">
            {formatCurrency(financials.subtotal_cost)}
          </span>
        </span>
        <span>
          Unpaid so far:{' '}
          <span className="font-medium text-gray-900">
            {formatCurrency(financials.unpaid_cost)}
          </span>
        </span>
        {financials.estimate_number && (
          <span>
            Estimate {financials.estimate_number}:{' '}
            <span className="font-medium text-gray-900">
              {financials.estimate_amount ? formatCurrency(financials.estimate_amount) : DASH}
            </span>
          </span>
        )}
        {financials.invoice_number && (
          <span>
            Invoice {financials.invoice_number}:{' '}
            <span className="font-medium text-gray-900">
              {financials.invoice_total ? formatCurrency(financials.invoice_total) : DASH}
            </span>
          </span>
        )}
      </div>

      {financials.workers.length === 0 ? (
        <p className="text-sm text-gray-500">No timesheets have been filed against this job yet.</p>
      ) : (
        <div className="space-y-3">
          {financials.workers.map((worker) => (
            <WorkerCostCard
              key={`${worker.worker_id ?? 'orphaned'}-${worker.worker_name}`}
              worker={worker}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function JobFinancials() {
  const navigate = useNavigate();
  const [completionFilter, setCompletionFilter] = useState<CompletionFilter>('all');
  const [clientFilter, setClientFilter] = useState<number | undefined>(undefined);
  const [expandedJobId, setExpandedJobId] = useState<number | null>(null);

  const { data, isLoading } = useQuery<JobFinancialsListResponse>({
    queryKey: ['financials', 'jobs', { completed: completionFilter, clientId: clientFilter }],
    queryFn: () =>
      financialsApi.listJobs({
        completed: completedParam(completionFilter),
        client_id: clientFilter,
      }),
  });

  const { data: clients = [] } = useQuery<Client[]>({
    queryKey: ['clients'],
    queryFn: clientsApi.list,
  });

  const { data: expandedFinancials, isLoading: loadingBreakdown } =
    useQuery<JobFinancialsDetail>({
      queryKey: ['financials', 'job', expandedJobId],
      queryFn: () => financialsApi.getJob(expandedJobId!),
      enabled: !!expandedJobId,
    });

  const jobs = data?.jobs ?? [];
  const totals = data?.totals;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/manager')}
          className="text-gray-500 hover:text-gray-700 transition-colors"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <h1 className="text-2xl font-bold text-gray-900">Job Financials</h1>
      </div>

      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex flex-wrap gap-4">
          <div>
            <label className="block text-sm text-gray-600 mb-1">Status</label>
            <select
              value={completionFilter}
              onChange={(e) => {
                setCompletionFilter(e.target.value as CompletionFilter);
                setExpandedJobId(null);
              }}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
            >
              <option value="all">All jobs</option>
              <option value="active">Active</option>
              <option value="completed">Completed</option>
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">Client</label>
            <select
              value={clientFilter ?? ''}
              onChange={(e) => {
                setClientFilter(e.target.value ? Number(e.target.value) : undefined);
                setExpandedJobId(null);
              }}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
            >
              <option value="">All clients</option>
              {clients.map((client) => (
                <option key={client.id} value={client.id}>
                  {client.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {totals && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-sm text-gray-600">Total Spend</p>
            <p className="text-2xl font-bold text-gray-900">
              {formatCurrency(totals.total_cost)}
            </p>
            <p className="text-xs text-gray-500 mt-1">
              {formatCurrency(totals.subtotal_cost)} + {formatCurrency(totals.hst_cost)} HST
            </p>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-sm text-gray-600">Total Budget</p>
            <p className="text-2xl font-bold text-obatek">{formatCurrency(totals.total_budget)}</p>
            <p className="text-xs text-gray-500 mt-1">
              {totals.jobs_without_budget} of {totals.job_count} unbudgeted
            </p>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-sm text-gray-600">Margin</p>
            <p className={`text-2xl font-bold ${marginToneClass(totals.total_margin)}`}>
              {formatCurrency(totals.total_margin)}
            </p>
            <p className="text-xs text-gray-500 mt-1">
              {totals.total_margin_percent === null
                ? 'No budget set'
                : `${totals.total_margin_percent}% of budget`}
            </p>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-sm text-gray-600">Jobs Over Budget</p>
            <p className="text-2xl font-bold text-red-600">{totals.jobs_over_budget}</p>
            <p className="text-xs text-gray-500 mt-1">
              {formatCurrency(totals.unpaid_cost)} still unpaid
            </p>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">Loading...</div>
      ) : jobs.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
          No jobs match these filters.
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow divide-y">
          {jobs.map((job) => (
            <div key={job.job_id}>
              <div
                className="p-4 hover:bg-gray-50 cursor-pointer"
                onClick={() =>
                  setExpandedJobId(expandedJobId === job.job_id ? null : job.job_id)
                }
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <svg
                        className={`w-4 h-4 text-gray-400 flex-shrink-0 transition-transform ${
                          expandedJobId === job.job_id ? 'rotate-90' : ''
                        }`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M9 5l7 7-7 7"
                        />
                      </svg>
                      <p className="font-medium text-gray-900 truncate">{job.job_title}</p>
                      <BudgetPill job={job} />
                    </div>
                    <p className="text-sm text-gray-500 mt-1">
                      {job.client_name}
                      {job.start_date && ` · ${formatDate(job.start_date)}`}
                      {' · '}
                      {parseFloat(job.total_hours).toFixed(1)}h across {job.worker_count}{' '}
                      {job.worker_count === 1 ? 'worker' : 'workers'}
                    </p>
                    <SpendBar job={job} />
                  </div>

                  <div className="text-right flex-shrink-0">
                    <p className="text-lg font-bold text-gray-900">
                      {formatCurrency(job.total_cost)}
                    </p>
                    <p className="text-sm text-gray-500">
                      of {job.budget_amount === null ? DASH : formatCurrency(job.budget_amount)}
                    </p>
                    <p className={`text-sm font-medium ${marginToneClass(job.margin_amount)}`}>
                      {job.margin_amount === null ? DASH : formatCurrency(job.margin_amount)}
                      {job.margin_percent !== null && ` (${job.margin_percent}%)`}
                    </p>
                  </div>
                </div>
              </div>

              {expandedJobId === job.job_id && (
                <div className="bg-gray-50 border-t px-4 py-3">
                  {loadingBreakdown || !expandedFinancials ? (
                    <p className="text-sm text-gray-500">Loading breakdown...</p>
                  ) : (
                    <JobCostBreakdown financials={expandedFinancials} />
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
