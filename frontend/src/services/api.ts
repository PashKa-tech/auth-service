import axios, { AxiosError } from 'axios';
import type { AxiosInstance, InternalAxiosRequestConfig } from 'axios';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface ApiResponse<T = any> {
  success: boolean;
  data: T;
  message?: string;
  error?: any;
  meta?: any;
}

export class ApiError extends Error {
  public status: number;
  public data: any;

  constructor(status: number, message: string, data?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

export function getApiKey(): string {
  return localStorage.getItem('auth_api_key') || import.meta.env.VITE_API_KEY || '';
}

export function setApiKey(key: string): void {
  localStorage.setItem('auth_api_key', key);
}

// Create an Axios instance
const axiosInstance: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true, // Send httpOnly cookies
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor to add API key
axiosInstance.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const apiKey = getApiKey();
    if (apiKey) {
      config.headers.set('X-Api-Key', apiKey);
    }
    return config;
  },
  (error) => Promise.reject(error)
);

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: unknown) => void;
  reject: (reason?: any) => void;
}> = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

// Response interceptor for auto token refresh
axiosInstance.interceptors.response.use(
  (response) => {
    // Return the response data directly as ApiResponse<T>
    return response.data;
  },
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // Handle 401 Unauthorized for token refresh
    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/auth/refresh') &&
      !originalRequest.url?.includes('/auth/login')
    ) {
      if (isRefreshing) {
        // Wait for ongoing refresh
        try {
          await new Promise((resolve, reject) => {
            failedQueue.push({ resolve, reject });
          });
          return axiosInstance(originalRequest);
        } catch (err) {
          return Promise.reject(err);
        }
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        await axiosInstance.post('/api/v1/auth/refresh');
        processQueue(null);
        return axiosInstance(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    // Format errors uniformly as ApiError
    const responseData = error.response?.data as any;
    const errorMsg =
      responseData?.detail ||
      responseData?.error?.message ||
      responseData?.message ||
      error.message ||
      `Request failed with status ${error.response?.status}`;
      
    if (error.response?.status === 401 || error.response?.status === 403) {
      if (!originalRequest.url?.includes('/auth/login')) {
        window.dispatchEvent(new CustomEvent('auth:unauthorized'));
      }
    }
      
    throw new ApiError(error.response?.status || 500, errorMsg, responseData);
  }
);

// Wrapper API object to retain identical interface to the old api client
export const api = {
  get: <T = any>(endpoint: string, config?: Record<string, any>): Promise<ApiResponse<T>> => 
    axiosInstance.get(endpoint, config) as unknown as Promise<ApiResponse<T>>,
    
  post: <T = any>(endpoint: string, data?: any, config?: Record<string, any>): Promise<ApiResponse<T>> => 
    axiosInstance.post(endpoint, data, config) as unknown as Promise<ApiResponse<T>>,
    
  put: <T = any>(endpoint: string, data?: any, config?: Record<string, any>): Promise<ApiResponse<T>> => 
    axiosInstance.put(endpoint, data, config) as unknown as Promise<ApiResponse<T>>,
    
  delete: <T = any>(endpoint: string, config?: Record<string, any>): Promise<ApiResponse<T>> => 
    axiosInstance.delete(endpoint, config) as unknown as Promise<ApiResponse<T>>,
};
