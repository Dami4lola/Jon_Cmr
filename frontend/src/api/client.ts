import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';

// Helper to display error messages (can be integrated with toast notifications)
export function displayApiError(error: any) {
  const message = error.userMessage || getUserFriendlyMessage(error);

  // For now, just log to console
  // You can integrate with your toast notification system here
  console.error('API Error:', message);

  // Example with toast:
  // toast.error(message);

  return message;
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

// API error interface for type safety
export interface ApiError {
  detail?: string;
  errors?: Array<{
    field: string;
    message: string;
    type: string;
  }>;
  type?: string;
}

// Log error to console (and optionally to external service)
function logError(error: AxiosError, context: string) {
  const errorData = {
    context,
    url: error.config?.url,
    method: error.config?.method,
    status: error.response?.status,
    message: error.message,
    data: error.response?.data,
    timestamp: new Date().toISOString(),
  };

  if (import.meta.env.DEV) {
    console.error('API Error:', errorData);
  }

  // In production, you could send this to an error tracking service
  // Example with Sentry:
  // if (import.meta.env.PROD) {
  //   Sentry.captureException(error, { contexts: { api: errorData } });
  // }
}

// Get user-friendly error message
export function getUserFriendlyMessage(error: AxiosError<ApiError>): string {
  // Network errors
  if (!error.response) {
    if (error.code === 'ECONNABORTED') {
      return 'Request timeout. Please check your connection and try again.';
    }
    if (error.message === 'Network Error') {
      return 'Unable to connect to server. Please check your internet connection.';
    }
    return 'A network error occurred. Please try again.';
  }

  const status = error.response.status;
  const data = error.response.data;

  // Use backend error detail if available
  if (data?.detail) {
    return data.detail;
  }

  // Validation errors
  if (status === 422 && data?.errors) {
    const firstError = data.errors[0];
    return `${firstError.field}: ${firstError.message}`;
  }

  // Status-based messages
  switch (status) {
    case 400:
      return 'Invalid request. Please check your input.';
    case 401:
      return 'Your session has expired. Please log in again.';
    case 403:
      return 'You do not have permission to perform this action.';
    case 404:
      return 'The requested resource was not found.';
    case 409:
      return 'This action conflicts with existing data.';
    case 422:
      return 'Validation error. Please check your input.';
    case 500:
      return 'A server error occurred. Please try again later.';
    case 503:
      return 'Service temporarily unavailable. Please try again later.';
    default:
      return 'An unexpected error occurred. Please try again.';
  }
}

const api = axios.create({
  baseURL: API_URL,
  timeout: 30000, // 30 second timeout
});

// Request interceptor - add auth token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('access_token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor - handle errors and logging
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiError>) => {
    // Log the error
    logError(error, 'API Request Failed');

    // Handle 401 Unauthorized - session expired
    if (error.response?.status === 401) {
      // Clear auth state and redirect to login
      localStorage.removeItem('access_token');
      localStorage.removeItem('auth-storage');

      // Only redirect if not already on login page
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }

    // Attach user-friendly message to error
    (error as any).userMessage = getUserFriendlyMessage(error);

    return Promise.reject(error);
  }
);

export default api;

// Helper for multipart form data (file uploads)
export const uploadFile = async (
  endpoint: string,
  file: File,
  fieldName: string = 'file'
): Promise<unknown> => {
  const formData = new FormData();
  formData.append(fieldName, file);

  // Let axios auto-set Content-Type with correct multipart boundary
  const response = await api.post(endpoint, formData);

  return response.data;
};

export const uploadFiles = async (
  endpoint: string,
  files: File[],
  fieldName: string = 'files'
): Promise<unknown> => {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append(fieldName, file);
  });

  // Let axios auto-set Content-Type with correct multipart boundary
  const response = await api.post(endpoint, formData);

  return response.data;
};
