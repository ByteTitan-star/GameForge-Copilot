export const oauthEnabled = import.meta.env.VITE_OAUTH_ENABLED === 'true'

export type OAuthProvider = 'github' | 'google'
