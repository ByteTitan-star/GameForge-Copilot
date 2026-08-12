import { useEffect, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { profileApi } from '@/api/profile'
import { formatApiError } from '@/api/error-message'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useT } from '@/i18n/use-t'

type Props = {
  accessToken: string
}

export function ProfilePanel({ accessToken }: Props) {
  const t = useT()
  const qc = useQueryClient()
  const q = useQuery({
    queryKey: ['profile'],
    queryFn: () => profileApi.get(accessToken),
  })

  const [handle, setHandle] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [profilePublic, setProfilePublic] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const [ok, setOk] = useState<string | null>(null)

  useEffect(() => {
    if (!q.data) return
    setHandle(q.data.handle ?? '')
    setDisplayName(q.data.display_name ?? '')
    setProfilePublic(q.data.profile_public ?? true)
  }, [q.data])

  const saveMu = useMutation({
    mutationFn: () =>
      profileApi.patch(
        {
          handle: handle.trim() || undefined,
          display_name: displayName.trim() || undefined,
          profile_public: profilePublic,
        },
        accessToken,
      ),
    onSuccess: async (data) => {
      setOk(t('profileSaved'))
      setErr(null)
      await qc.invalidateQueries({ queryKey: ['profile'] })
      setHandle(data.handle ?? '')
      setDisplayName(data.display_name ?? '')
      setProfilePublic(data.profile_public ?? true)
    },
    onError: (e) => {
      setOk(null)
      setErr(formatApiError(e, t('profileSaveFailed')))
    },
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    setOk(null)
    void saveMu.mutate()
  }

  if (q.isLoading) {
    return (
      <p className="gf-page-muted flex items-center gap-2 text-sm">
        <Loader2 className="h-4 w-4 animate-spin" />
        {t('loading')}
      </p>
    )
  }

  return (
    <section className="gf-glass rounded-2xl p-5">
      <h2 className="gf-page-body text-lg">{t('profileTitle')}</h2>
      <p className="gf-page-muted mt-1 text-xs">{t('profileSubtitle')}</p>

      <form className="mt-4 max-w-md space-y-3" onSubmit={onSubmit}>
        <Input
          label={t('profileHandle')}
          value={handle}
          onChange={(e) => setHandle(e.target.value.toLowerCase())}
          placeholder="my_handle"
          autoComplete="off"
        />
        <Input
          label={t('profileDisplayName')}
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder={t('profileDisplayName')}
        />
        <label className="flex cursor-pointer items-center gap-2 text-sm gf-page-body">
          <input
            type="checkbox"
            checked={profilePublic}
            onChange={(e) => setProfilePublic(e.target.checked)}
            className="h-4 w-4 rounded border gf-border-subtle"
          />
          {t('profilePublic')}
        </label>
        {err ? (
          <p role="alert" className="text-sm text-rose-400">
            {err}
          </p>
        ) : null}
        {ok ? (
          <p role="status" className="text-sm gf-text-accent">
            {ok}
          </p>
        ) : null}
        {handle.trim() ? (
          <p className="gf-page-muted text-[11px]">
            {t('profilePublicUrl')}: /u/{handle.trim()}
          </p>
        ) : null}
        <Button type="submit" className="gf-btn-primary !rounded-xl !border-0" disabled={saveMu.isPending}>
          {saveMu.isPending ? t('loading') : t('save')}
        </Button>
      </form>
    </section>
  )
}
