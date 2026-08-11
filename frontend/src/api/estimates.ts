import api from './client';
import type {
  JobTypeOption,
  JobTypeRate,
  JobTypeRateUpdate,
  QuickQuoteRequest,
  QuickQuoteResponse,
  QuickQuoteRates,
  DistancePreviewResponse,
  MaterialSearchResult,
  Estimate,
  EstimateListItem,
  EstimatePayload,
  EstimateAmounts,
} from '../types';

// Round-trips a saved Estimate back into an update payload - used when a
// standalone estimate (created before a job existed) needs to be re-saved
// with a job_id once the job it belongs to is created.
export function estimateToPayload(estimate: Estimate): EstimatePayload {
  return {
    job_id: estimate.job?.id ?? null,
    client_id: estimate.client?.id ?? null,
    client_name_override: estimate.client_name_override,
    address_override: estimate.address_override,
    scope_of_work: estimate.scope_of_work,
    crew_size: estimate.crew_size,
    techs_traveling: estimate.techs_traveling,
    distance_km: estimate.distance_km != null ? parseFloat(estimate.distance_km) : null,
    km_rate: parseFloat(estimate.km_rate),
    dump_fee: parseFloat(estimate.dump_fee),
    permits_fee: parseFloat(estimate.permits_fee),
    admin_fee: parseFloat(estimate.admin_fee),
    redseal_amount: parseFloat(estimate.redseal_amount),
    include_admin_fee: estimate.include_admin_fee,
    include_hst: estimate.include_hst,
    status: estimate.status,
    tasks: estimate.tasks.map((t) => ({
      phase: t.phase, description: t.description, hours: parseFloat(t.hours),
      uses_heavy_equipment: t.uses_heavy_equipment, sort_order: t.sort_order,
    })),
    equipment_rows: estimate.equipment_rows.map((r) => ({
      category: r.category, description: r.description, rate: parseFloat(r.rate),
      unit: r.unit, quantity: parseFloat(r.quantity), markup_pct: parseFloat(r.markup_pct), sort_order: r.sort_order,
    })),
    material_rows: estimate.material_rows.map((r) => ({
      description: r.description, quantity: parseFloat(r.quantity), unit_cost: parseFloat(r.unit_cost), sort_order: r.sort_order,
    })),
  };
}

export const estimatesApi = {
  // Public - no auth required. Powers the customer-facing quick estimate form.
  listJobTypes: async (): Promise<JobTypeOption[]> => {
    const response = await api.get('/estimates/job-types');
    return response.data;
  },

  quickQuote: async (data: QuickQuoteRequest): Promise<QuickQuoteResponse> => {
    const response = await api.post('/estimates/quick-quote', data);
    return response.data;
  },

  // Manager-only: current rates behind both invoices and the quick quote
  getRates: async (): Promise<QuickQuoteRates> => {
    const response = await api.get('/estimates/quick-quote-rates');
    return response.data;
  },

  updateJobTypeRate: async (jobType: string, data: JobTypeRateUpdate): Promise<JobTypeRate> => {
    const response = await api.put(`/estimates/quick-quote-rates/${jobType}`, data);
    return response.data;
  },

  updateAdminFee: async (adminFee: number): Promise<QuickQuoteRates> => {
    const response = await api.put('/estimates/quick-quote-admin-fee', { admin_fee: adminFee });
    return response.data;
  },

  // Manager-only: preview round-trip travel km for an address before a job exists
  distancePreview: async (address: string): Promise<DistancePreviewResponse> => {
    const response = await api.post('/estimates/distance-preview', { address });
    return response.data;
  },

  // Manager-only: autocomplete search for Home Depot material prices, cached in the DB
  searchMaterials: async (q: string): Promise<MaterialSearchResult[]> => {
    const response = await api.get('/estimates/materials/search', { params: { q } });
    return response.data;
  },

  // Manager-only: persisted estimate builder (scope of work, phased task hours, full cost breakdown)
  preview: async (data: EstimatePayload): Promise<EstimateAmounts> => {
    const response = await api.post('/estimates/preview', data);
    return response.data;
  },

  create: async (data: EstimatePayload): Promise<Estimate> => {
    const response = await api.post('/estimates/', data);
    return response.data;
  },

  update: async (id: number, data: EstimatePayload): Promise<Estimate> => {
    const response = await api.put(`/estimates/${id}`, data);
    return response.data;
  },

  get: async (id: number): Promise<Estimate> => {
    const response = await api.get(`/estimates/${id}`);
    return response.data;
  },

  list: async (params?: { job_id?: number; standalone?: boolean; status_filter?: string }): Promise<EstimateListItem[]> => {
    const response = await api.get('/estimates/', { params });
    return response.data;
  },

  remove: async (id: number): Promise<void> => {
    await api.delete(`/estimates/${id}`);
  },

  downloadPdf: async (id: number): Promise<Blob> => {
    const response = await api.get(`/estimates/${id}/pdf`, { responseType: 'blob' });
    return response.data;
  },

  downloadPdfToFile: async (id: number, estimateNumber: string): Promise<void> => {
    const blob = await estimatesApi.downloadPdf(id);
    const filename = `Estimate-${estimateNumber}.pdf`;

    if ('showSaveFilePicker' in window) {
      try {
        const handle = await (window as any).showSaveFilePicker({
          suggestedName: filename,
          types: [{ description: 'PDF', accept: { 'application/pdf': ['.pdf'] } }],
        });
        const writable = await handle.createWritable();
        await writable.write(blob);
        await writable.close();
        return;
      } catch (e: any) {
        if (e?.name === 'AbortError') return;
      }
    }

    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  },
};
