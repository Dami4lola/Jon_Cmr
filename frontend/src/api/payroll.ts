import api from './client';
import type { PayrollWorkerSummary } from '../types';

export const payrollApi = {
  previewPayroll: async (startDate: string, endDate: string): Promise<PayrollWorkerSummary[]> => {
    const response = await api.post('/payroll/preview-period', {
      start_date: startDate,
      end_date: endDate,
    });
    return response.data;
  },

  processPayroll: async (startDate: string, endDate: string): Promise<Blob> => {
    const response = await api.post(
      '/payroll/process-period',
      { start_date: startDate, end_date: endDate },
      { responseType: 'blob' },
    );
    return response.data;
  },

  downloadPayrollZip: async (
    startDate: string,
    endDate: string,
  ): Promise<void> => {
    const blob = await payrollApi.processPayroll(startDate, endDate);
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `Payroll_${startDate}_${endDate}.zip`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  },
};
