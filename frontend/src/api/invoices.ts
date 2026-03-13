import api from './client';
import type { Invoice, InvoiceCreate, InvoicePreview } from '../types';

export const invoicesApi = {
  list: async (params?: {
    skip?: number;
    limit?: number;
    status?: string;
  }): Promise<Invoice[]> => {
    const response = await api.get('/invoices/', { params });
    return response.data;
  },

  get: async (id: number): Promise<Invoice> => {
    const response = await api.get(`/invoices/${id}`);
    return response.data;
  },

  previewForJob: async (jobId: number): Promise<InvoicePreview> => {
    const response = await api.get(`/invoices/preview/job/${jobId}`);
    return response.data;
  },

  createForJob: async (jobId: number, data?: InvoiceCreate): Promise<Invoice> => {
    const response = await api.post(`/invoices/job/${jobId}`, data || {});
    return response.data;
  },

  updateStatus: async (id: number, status: Invoice['status']): Promise<Invoice> => {
    const response = await api.put(`/invoices/${id}/status`, { status });
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/invoices/${id}`);
  },

  downloadPdf: async (id: number): Promise<Blob> => {
    const response = await api.get(`/invoices/${id}/pdf`, {
      responseType: 'blob',
    });
    return response.data;
  },

  // Helper to trigger PDF download in browser
  downloadPdfToFile: async (id: number, invoiceNumber: string): Promise<void> => {
    const blob = await invoicesApi.downloadPdf(id);
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `Invoice-${invoiceNumber}.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  },
};

export const settingsApi = {
  getInvoiceStartNumber: async (): Promise<{ value: number }> => {
    const response = await api.get('/settings/invoice-start-number');
    return response.data;
  },

  setInvoiceStartNumber: async (value: number): Promise<{ value: number }> => {
    const response = await api.put('/settings/invoice-start-number', { value });
    return response.data;
  },
};
