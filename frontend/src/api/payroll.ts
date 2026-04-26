import api from './client';
import type { PayrollWorkerSummary } from '../types';

export const payrollApi = {
  previewPayroll: async (startDate: string, endDate: string, workerIds?: number[]): Promise<PayrollWorkerSummary[]> => {
    const response = await api.post('/payroll/preview-period', {
      start_date: startDate,
      end_date: endDate,
      worker_ids: workerIds || null,
    });
    return response.data;
  },

  processPayroll: async (startDate: string, endDate: string, workerIds?: number[]): Promise<Blob> => {
    const response = await api.post(
      '/payroll/process-period',
      { start_date: startDate, end_date: endDate, worker_ids: workerIds || null },
      { responseType: 'blob' },
    );
    return response.data;
  },

  downloadPayrollZip: async (
    startDate: string,
    endDate: string,
    workerIds?: number[],
  ): Promise<void> => {
    const blob = await payrollApi.processPayroll(startDate, endDate, workerIds);
    const filename = `Payroll_${startDate}_${endDate}.zip`;

    if ('showSaveFilePicker' in window) {
      try {
        const handle = await (window as any).showSaveFilePicker({
          suggestedName: filename,
          types: [{ description: 'ZIP Archive', accept: { 'application/zip': ['.zip'] } }],
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
