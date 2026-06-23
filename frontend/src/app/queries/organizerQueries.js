import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';

export const getOrganizerQueryKey = (scanMode, sessionMode) => [
  'organizer',
  scanMode || 'all',
  sessionMode || 'sfw',
];

export const useOrganizerQuery = (scanMode, sessionMode) => useQuery({
  queryKey: getOrganizerQueryKey(scanMode, sessionMode),
  queryFn: () => api.organizer.get({ scanMode, sessionMode }),
  enabled: false,
});

export const useOrganizerCountQuery = (scanMode, sessionMode) => useQuery({
  queryKey: ['organizer-count', scanMode || 'all', sessionMode || 'sfw'],
  queryFn: () => api.organizer.getCount({ scanMode, sessionMode }),
});
