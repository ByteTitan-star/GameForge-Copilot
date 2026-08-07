import { useQuery } from '@tanstack/react-query'
import { gamesApi } from '@/api/games'
import { RunStatus } from '@/api/enums'

export function useActiveRuns(accessToken: string | null) {
  return useQuery({
    queryKey: ['active-runs', accessToken],
    enabled: Boolean(accessToken),
    queryFn: () => gamesApi.listActiveRuns(accessToken!),
    refetchInterval: (query) => {
      const rows = query.state.data?.data ?? []
      return rows.some(
        (r) => r.status === RunStatus.running || r.status === RunStatus.paused,
      )
        ? 8000
        : false
    },
    staleTime: 4000,
  })
}
