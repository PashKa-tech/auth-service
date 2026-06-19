// API client for Auth Service

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface ApiResponse<T = any> {
  success: boolean;
  data: T;
  message?: string;
  error?: any;
  meta?: any;
}

export function getApiKey(): string {
  return localStorage.getItem('auth_api_key') || import.meta.env.VITE_API_KEY || '';
}

export function setApiKey(key: string): void {
  localStorage.setItem('auth_api_key', key);
}

export function parseJwt(token: string): any {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      window
        .atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch (e) {
    return null;
  }
}

async function request<T = any>(
  endpoint: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  const url = `${API_BASE_URL.replace(/\/$/, '')}/${endpoint.replace(/^\//, '')}`;
  
  // Set defaults
  const headers = new Headers(options.headers || {});
  if (!headers.has('X-Api-Key')) {
    headers.set('X-Api-Key', getApiKey());
  }
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const config: RequestInit = {
    ...options,
    headers,
    credentials: 'include', // Crucial to send/receive httpOnly cookies (access_token, refresh_token)
  };

  let response = await fetch(url, config);
  
  // Auto token refresh on 401 (only if not already trying to refresh or login)
  if (response.status === 401 && !endpoint.includes('/auth/refresh') && !endpoint.includes('/auth/login')) {
    try {
      const refreshResponse = await fetch(`${API_BASE_URL.replace(/\/$/, '')}/api/v1/auth/refresh`, {
        method: 'POST',
        headers: { 'X-Api-Key': getApiKey() },
        credentials: 'include'
      });
      if (refreshResponse.ok) {
        // Retry original request
        response = await fetch(url, config);
      }
    } catch (e) {
      // Ignore refresh errors and let the original 401 fall through
    }
  }
  
  let json: any = {};
  const text = await response.text();
  if (text) {
    try {
      json = JSON.parse(text);
    } catch {
      json = { message: text };
    }
  }

  if (!response.ok) {
    const errorMsg = json.detail || json.error?.message || json.message || `Request failed with status ${response.status}`;
    throw new Error(errorMsg);
  }

  return json as ApiResponse<T>;
}

export const api = {
  get: <T = any>(endpoint: string, options?: RequestInit) => 
    request<T>(endpoint, { ...options, method: 'GET' }),
    
  post: <T = any>(endpoint: string, body?: any, options?: RequestInit) => 
    request<T>(endpoint, { 
      ...options, 
      method: 'POST', 
      body: body instanceof FormData ? body : JSON.stringify(body) 
    }),
    
  put: <T = any>(endpoint: string, body?: any, options?: RequestInit) => 
    request<T>(endpoint, { 
      ...options, 
      method: 'PUT', 
      body: body instanceof FormData ? body : (body !== undefined ? JSON.stringify(body) : undefined) 
    }),
    
  delete: <T = any>(endpoint: string, options?: RequestInit) => 
    request<T>(endpoint, { ...options, method: 'DELETE' }),
};
