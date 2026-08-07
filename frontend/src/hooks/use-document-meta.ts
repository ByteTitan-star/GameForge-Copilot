import { useEffect } from 'react'

type MetaInput = {
  title?: string
  description?: string
  url?: string
}

function upsertMeta(attr: 'name' | 'property', key: string, content: string) {
  let el = document.querySelector(`meta[${attr}="${key}"]`) as HTMLMetaElement | null
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute(attr, key)
    document.head.appendChild(el)
  }
  el.content = content
}

/** 轻量 OG / title 更新（无需 react-helmet-async） */
export function useDocumentMeta({ title, description, url }: MetaInput) {
  useEffect(() => {
    const prevTitle = document.title
    if (title) document.title = title
    if (description) {
      upsertMeta('name', 'description', description)
      upsertMeta('property', 'og:description', description)
    }
    if (title) upsertMeta('property', 'og:title', title)
    if (url) upsertMeta('property', 'og:url', url)
    return () => {
      document.title = prevTitle
    }
  }, [title, description, url])
}
