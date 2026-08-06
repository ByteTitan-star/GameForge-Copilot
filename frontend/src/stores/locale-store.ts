import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type Locale = 'zh' | 'en'

type LocaleState = {
  locale: Locale
  setLocale: (locale: Locale) => void
}

export const useLocaleStore = create<LocaleState>()(
  persist(
    (set) => ({
      locale: 'zh',
      setLocale: (locale) => set({ locale }),
    }),
    { name: 'gf-locale' },
  ),
)
