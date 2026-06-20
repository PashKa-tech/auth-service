import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';

export const useAuth = () => {
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: async () => {
      const resp = await api.get('/api/v1/auth/me');
      return resp.data;
    },
    retry: false,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  const setUser = (userData: any) => {
    queryClient.setQueryData(['auth', 'me'], userData);
  };

  const logout = async () => {
    try {
      await api.post('/api/v1/auth/logout');
    } catch (e) {
      console.error('Logout failed', e);
    }
    queryClient.setQueryData(['auth', 'me'], null);
  };

  return {
    user: data || null,
    isLoading,
    error,
    setUser,
    logout,
  };
};
