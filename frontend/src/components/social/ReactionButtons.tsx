import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Heart, Loader2, Star } from 'lucide-react'
import { Link } from 'react-router-dom'
import { reactionsApi } from '@/api/reactions'
import { useT } from '@/i18n/use-t'
import { cn } from '@/lib/cn'

type Props = {
  gameId: string
  accessToken?: string | null
  readOnly?: boolean
  className?: string
}

export function ReactionButtons({ gameId, accessToken, readOnly = false, className }: Props) {
  const t = useT()
  const qc = useQueryClient()

  const q = useQuery({
    queryKey: ['reactions', gameId, accessToken ?? 'anon'],
    queryFn: () => reactionsApi.getState(gameId, accessToken),
  })

  const toggleMu = useMutation({
    mutationFn: async (kind: 'like' | 'favorite') => {
      if (!accessToken) throw new Error('login')
      const state = q.data ?? { liked: false, favorited: false, like_count: 0 }
      if (kind === 'like') {
        await reactionsApi.toggleLike(gameId, state.liked, accessToken)
      } else {
        await reactionsApi.toggleFavorite(gameId, state.favorited, accessToken)
      }
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['reactions', gameId] })
      await qc.invalidateQueries({ queryKey: ['favorites'] })
    },
  })

  const state = q.data
  const liked = state?.liked ?? false
  const favorited = state?.favorited ?? false
  const canMutate = Boolean(accessToken) && !readOnly

  function onToggle(kind: 'like' | 'favorite') {
    if (!canMutate) return
    toggleMu.mutate(kind)
  }

  return (
    <div className={cn('flex flex-wrap items-center gap-2', className)}>
      <button
        type="button"
        disabled={!canMutate || toggleMu.isPending}
        onClick={() => onToggle('like')}
        className={cn(
          'inline-flex cursor-pointer items-center gap-1.5 rounded-lg border px-3 py-2 text-xs transition',
          liked
            ? 'border-rose-400/40 bg-rose-400/15 text-rose-100'
            : 'border-white/15 bg-white/[0.04] text-white/80 hover:border-white/30',
          !canMutate && 'opacity-50',
        )}
        title={readOnly ? t('trialReactionsReadOnly') : !accessToken ? t('loginRequired') : undefined}
      >
        {toggleMu.isPending ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Heart className={cn('h-3.5 w-3.5', liked && 'fill-current')} />
        )}
        {t('reactionLike')}
        {state?.like_count ? ` · ${state.like_count}` : ''}
      </button>
      <button
        type="button"
        disabled={!canMutate || toggleMu.isPending}
        onClick={() => onToggle('favorite')}
        className={cn(
          'inline-flex cursor-pointer items-center gap-1.5 rounded-lg border px-3 py-2 text-xs transition',
          favorited
            ? 'border-amber-400/40 bg-amber-400/15 text-amber-100'
            : 'border-white/15 bg-white/[0.04] text-white/80 hover:border-white/30',
          !canMutate && 'opacity-50',
        )}
        title={readOnly ? t('trialReactionsReadOnly') : undefined}
      >
        <Star className={cn('h-3.5 w-3.5', favorited && 'fill-current')} />
        {t('reactionFavorite')}
      </button>
      {!accessToken ? (
        <Link to="/login" className="text-[11px] text-white/45 hover:text-white/70">
          {t('login')}
        </Link>
      ) : readOnly ? (
        <span className="text-[11px] text-white/45">{t('trialReactionsReadOnly')}</span>
      ) : null}
    </div>
  )
}
