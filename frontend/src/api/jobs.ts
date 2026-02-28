import api from './client';
import type { Job, JobCreate, JobPhoto, CalendarEvent } from '../types';

export const jobsApi = {
  list: async (params?: {
    skip?: number;
    limit?: number;
    worker_id?: number;
    is_completed?: boolean;
  }): Promise<Job[]> => {
    const response = await api.get('/jobs/', { params });
    return response.data;
  },

  get: async (id: number): Promise<Job> => {
    const response = await api.get(`/jobs/${id}`);
    return response.data;
  },

  create: async (data: JobCreate): Promise<Job> => {
    const response = await api.post('/jobs/', data);
    return response.data;
  },

  update: async (id: number, data: Partial<JobCreate>): Promise<Job> => {
    const response = await api.put(`/jobs/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/jobs/${id}`);
  },

  getDistance: async (id: number): Promise<{ distance_km: number; duration_minutes: number }> => {
    const response = await api.get(`/jobs/${id}/distance`);
    return response.data;
  },

  getCalendarEvents: async (params?: {
    start_date?: string;
    end_date?: string;
    worker_id?: number;
  }): Promise<CalendarEvent[]> => {
    const response = await api.get('/jobs/calendar', { params });
    return response.data;
  },

  assignWorkers: async (jobId: number, workerIds: number[]): Promise<Job> => {
    const response = await api.post(`/jobs/${jobId}/assign`, { worker_ids: workerIds });
    return response.data;
  },

  markCompleted: async (id: number): Promise<Job> => {
    const response = await api.put(`/jobs/${id}`, { is_completed: true });
    return response.data;
  },

  markActive: async (id: number): Promise<Job> => {
    const response = await api.put(`/jobs/${id}`, { is_completed: false });
    return response.data;
  },

  uploadPhotos: async (jobId: number, files: File[]): Promise<JobPhoto[]> => {
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));
    const response = await api.post(`/jobs/${jobId}/photos`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  deletePhoto: async (jobId: number, photoId: number): Promise<void> => {
    await api.delete(`/jobs/${jobId}/photos/${photoId}`);
  },
};
