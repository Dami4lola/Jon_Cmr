import api, { uploadFiles } from './client';
import type { Timesheet, TimesheetCreate, Receipt } from '../types';

export const timesheetsApi = {
  list: async (params?: {
    skip?: number;
    limit?: number;
    worker_id?: number;
    job_id?: number;
    start_date?: string;
    end_date?: string;
  }): Promise<Timesheet[]> => {
    const response = await api.get('/timesheets/', { params });
    return response.data;
  },

  get: async (id: number): Promise<Timesheet> => {
    const response = await api.get(`/timesheets/${id}`);
    return response.data;
  },

  create: async (data: TimesheetCreate): Promise<Timesheet> => {
    const response = await api.post('/timesheets/', data);
    return response.data;
  },

  update: async (id: number, data: Partial<TimesheetCreate> & { minimum_hours_override?: number | null }): Promise<Timesheet> => {
    const response = await api.put(`/timesheets/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/timesheets/${id}`);
  },

  listPaid: async (): Promise<Timesheet[]> => {
    const response = await api.get('/timesheets/paid');
    return response.data;
  },

  listByJob: async (jobId: number): Promise<Timesheet[]> => {
    const response = await api.get(`/timesheets/by-job/${jobId}`);
    return response.data;
  },

  markUnpaid: async (id: number): Promise<Timesheet> => {
    const response = await api.post(`/timesheets/${id}/mark-unpaid`);
    return response.data;
  },

  uploadReceipts: async (timesheetId: number, files: File[]): Promise<void> => {
    for (const file of files) {
      const formData = new FormData();
      formData.append('files', file);
      await api.post(`/timesheets/${timesheetId}/receipts`, formData);
    }
  },

  getReceipts: async (timesheetId: number): Promise<Receipt[]> => {
    const response = await api.get(`/timesheets/${timesheetId}/receipts`);
    return response.data;
  },

  deleteReceipt: async (receiptId: number): Promise<void> => {
    await api.delete(`/timesheets/receipts/${receiptId}`);
  },

  calculatePayout: async (data: TimesheetCreate): Promise<{ calculated_pay: number }> => {
    const response = await api.post('/timesheets/calculate', data);
    return response.data;
  },
};
