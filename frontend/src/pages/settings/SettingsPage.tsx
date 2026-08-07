import { useState, type FormEvent } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { authApi } from '@/api/auth'
import { formatApiError } from '@/api/error-message'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useT } from '@/i18n/use-t'
import { useAuthStore } from '@/stores/auth-store'
import { LlmConfigPanel } from './LlmConfigPanel'
import { UsagePanel } from './UsagePanel'

export function SettingsPage() {
  const t = useT()
  const user = useAuthStore((s) => s.user)
  const token = useAuthStore((s) => s.access_token)
  const location = useLocation()
  const state = location.state as { needVerify?: boolean; justVerified?: boolean } | null

  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [pwdError, setPwdError] = useState('')
  const [pwdOk, setPwdOk] = useState('')
  const [pwdLoading, setPwdLoading] = useState(false)

  async function onChangePassword(e: FormEvent) {
    e.preventDefault()
    setPwdError('')
    setPwdOk('')
    if (!token) {
      setPwdError('请先登录')
      return
    }
    if (newPassword.length < 8) {
      setPwdError('新密码至少 8 位')
      return
    }
    if (newPassword !== confirmPassword) {
      setPwdError('两次输入的新密码不一致')
      return
    }
    setPwdLoading(true)
    try {
      await authApi.changePassword(oldPassword, newPassword, token)
      setPwdOk('密码已更新')
      setOldPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err) {
      setPwdError(formatApiError(err, '修改失败'))
    } finally {
      setPwdLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="font-mono text-[10px] tracking-[0.16em] text-white/35 uppercase">Account</p>
        <h1 className="text-2xl tracking-tight text-white/95 md:text-3xl">{t('settings')}</h1>
        <p className="mt-1 text-sm text-white/40">LLM 配置、用量与账号</p>
      </div>

      {state?.needVerify ? (
        <p role="status" className="rounded-xl border border-amber-400/25 bg-amber-400/10 px-4 py-3 text-sm text-amber-100">
          邮箱尚未验证：请先验证邮箱并配置 LLM，再开始生成游戏。
        </p>
      ) : null}
      {state?.justVerified ? (
        <p role="status" className="rounded-xl border border-teal-400/25 bg-teal-400/10 px-4 py-3 text-sm text-teal-100">
          邮箱已验证。接下来配置 LLM 即可开始创作。
        </p>
      ) : null}

      <section className="rounded-2xl border border-white/[0.08] bg-[#12151a] p-5">
        <h2 className="text-lg text-white/90">账号</h2>
        <dl className="mt-3 space-y-2 text-sm text-white/45">
          {[
            ['邮箱', user?.email],
            ['角色', user?.role],
            ['邮箱验证', user?.email_verified ? '已验证' : '未验证'],
          ].map(([k, v]) => (
            <div
              key={String(k)}
              className="flex justify-between gap-4 rounded-xl bg-black/25 px-3 py-2 ring-1 ring-white/[0.04]"
            >
              <dt>{k}</dt>
              <dd className="text-white/85">{v}</dd>
            </div>
          ))}
        </dl>
        {!user?.email_verified ? (
          <div className="mt-4">
            <Link to="/verify-email">
              <Button className="!rounded-lg !bg-teal-400 !text-black hover:!bg-teal-300">去验证邮箱</Button>
            </Link>
          </div>
        ) : null}
      </section>

      <section className="rounded-2xl border border-white/[0.08] bg-[#12151a] p-5">
        <h2 className="text-lg text-white/90">{t('changePassword')}</h2>
        <p className="mt-1 text-xs text-white/35">{t('changePasswordHint')}</p>
        <form className="mt-4 max-w-md space-y-3" onSubmit={onChangePassword}>
          <Input
            name="old_password"
            label={t('oldPassword')}
            type="password"
            value={oldPassword}
            onChange={(e) => setOldPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
          <Input
            name="new_password"
            label={t('newPassword')}
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
          />
          <Input
            name="confirm_password"
            label={t('confirmPassword')}
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
          />
          {pwdError ? (
            <p role="alert" className="text-sm text-red-300">
              {pwdError}
            </p>
          ) : null}
          {pwdOk ? (
            <p role="status" className="text-sm text-teal-200">
              {pwdOk}
            </p>
          ) : null}
          <Button
            type="submit"
            className="!rounded-lg !bg-teal-400 !text-black hover:!bg-teal-300"
            disabled={pwdLoading}
          >
            {pwdLoading ? t('savingPassword') : t('changePassword')}
          </Button>
        </form>
        <p className="mt-3 text-xs text-white/35">
          忘记旧密码？{' '}
          <Link to="/forgot-password" className="text-white/70 underline-offset-2 hover:underline">
            {t('forgot')}
          </Link>
        </p>
      </section>

      <LlmConfigPanel />
      <UsagePanel />
    </div>
  )
}
