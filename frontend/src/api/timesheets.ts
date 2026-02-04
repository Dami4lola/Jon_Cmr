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

  update: async (id: number, data: Partial<TimesheetCreate>): Promise<Timesheet> => {
    const response = await api.put(`/timesheets/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/timesheets/${id}`);
  },

  uploadReceipts: async (timesheetId: number, files: File[]): Promise<Receipt[]> => {
    const result = await uploadFiles(`/timesheets/${timesheetId}/receipts`, files, 'files');
    return result as Receipt[];
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
