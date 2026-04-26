import api, { uploadFiles } from './client';
import type { JobInspection, InspectionPhoto, InspectionCreate } from '../types';

export const inspectionsApi = {
  listForJob: async (jobId: number): Promise<JobInspection[]> => {
    const response = await api.get(`/inspections/job/${jobId}`);
    return response.data;
  },

  get: async (id: number): Promise<JobInspection> => {
    const response = await api.get(`/inspections/${id}`);
    return response.data;
  },

  create: async (
    jobId: number,
    type: 'pre' | 'post',
    data?: InspectionCreate
  ): Promise<JobInspection> => {
    const response = await api.post(`/inspections/job/${jobId}/${type}`, data || {});
    return response.data;
  },

  update: async (id: number, data: InspectionCreate): Promise<JobInspection> => {
    const response = await api.put(`/inspections/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/inspections/${id}`);
  },

  uploadPhotos: async (inspectionId: number, files: File[]): Promise<InspectionPhoto[]> => {
    const result = await uploadFiles(`/inspections/${inspectionId}/photos`, files, 'files');
    return result as InspectionPhoto[];
  },

  deletePhoto: async (photoId: number): Promise<void> => {
    await api.delete(`/inspections/photos/${photoId}`);
  },

  updatePhotoCaption: async (photoId: number, caption: string): Promise<InspectionPhoto> => {
    const response = await api.put(`/inspections/photos/${photoId}`, { caption });
    return response.data;
  },
};
