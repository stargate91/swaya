import { useQuery, useMutation } from '@tanstack/react-query';
import api from '@/lib/api';

export const useScanStatusQuery = ({ enabled = true, select } = {}) => useQuery({
  queryKey: ['scan-status'],
  queryFn: () => api.scan.getStatus(),
  enabled,
  select,
  refetchInterval: (query) => (query.state.data?.active ? 1200 : 10000),
});

export const useScanMutation = () => useMutation({
  mutationFn: (payload) => api.scan.start(payload),
});

export const useHydrateStatusQuery = () => useQuery({
  queryKey: ['hydrate-status'],
  queryFn: () => api.hydrate.getStatus(),
  refetchInterval: 1200,
});
