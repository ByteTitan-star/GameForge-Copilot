import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Check, Copy, Download, FileCode2, Loader2 } from 'lucide-react'
import { gamesApi } from '@/api/games'
import { formatApiError } from '@/api/error-message'
import type { ArtifactFile } from '@/api/types'
import { downloadFile } from '@/lib/download-file'
import { useT } from '@/i18n/use-t'
import { cn } from '@/lib/cn'

type Props = {
  gameId: string
  version: number
  accessToken: string
}

/** 大文件温和提示阈值（字节）：超过则在顶部提示下载查看，纯展示不阻断。 */
const LARGE_FILE_BYTES = 200 * 1024

// ── 文件树（扁平 → 嵌套，单文件退化为单节点）───────────────────────────────────

export type FileNode = {
  name: string
  path: string
  isDir: boolean
  children?: FileNode[]
}

/** 把扁平产物路径列表折叠成树。当前产物是单 index.html，会退化为单节点。 */
export function buildFileTree(files: ArtifactFile[]): FileNode[] {
  const root: FileNode = { name: '', path: '', isDir: true, children: [] }
  for (const f of files) {
    const parts = f.path.split('/')
    let cur = root
    parts.forEach((part, i) => {
      const isLeaf = i === parts.length - 1
      const path = parts.slice(0, i + 1).join('/')
      cur.children ??= []
      let next = cur.children.find((c) => c.name === part && c.isDir === !isLeaf)
      if (!next) {
        next = { name: part, path, isDir: !isLeaf, children: isLeaf ? undefined : [] }
        cur.children.push(next)
      }
      cur = next
    })
  }
  // 目录在前、文件在后，同级按名排序
  const sortNodes = (nodes: FileNode[]): FileNode[] => {
    nodes.forEach((n) => {
      if (n.children) n.children = sortNodes(n.children)
    })
    return [...nodes].sort((a, b) => {
      if (a.isDir !== b.isDir) return a.isDir ? -1 : 1
      return a.name.localeCompare(b.name)
    })
  }
  return sortNodes(root.children ?? [])
}

// ── 文件树渲染 ──────────────────────────────────────────────────────────────────

function TreeView({
  nodes,
  selectedPath,
  onSelect,
  depth = 0,
}: {
  nodes: FileNode[]
  selectedPath: string
  onSelect: (path: string) => void
  depth?: number
}) {
  return (
    <ul className={cn(depth === 0 ? '' : 'ml-3 border-l border-white/[0.06] pl-1')}>
      {nodes.map((node) => {
        const active = node.path === selectedPath
        if (!node.isDir) {
          return (
            <li key={node.path}>
              <button
                type="button"
                onClick={() => onSelect(node.path)}
                className={cn(
                  'flex w-full items-center gap-1.5 rounded-md px-1.5 py-1 text-left text-xs transition-colors',
                  active
                    ? 'bg-blue-500/15 text-blue-300 ring-1 ring-blue-400/20'
                    : 'text-[#94A3B8] hover:bg-white/[0.04] hover:text-[#E2E8F0]',
                )}
              >
                <FileCode2 className="h-3.5 w-3.5 shrink-0 opacity-70" aria-hidden="true" />
                <span className="truncate font-mono">{node.name}</span>
              </button>
            </li>
          )
        }
        return (
          <li key={node.path}>
            <div className="flex items-center gap-1 px-1.5 py-1 text-xs font-medium text-[#CBD5E1]">
              <span className="truncate font-mono">{node.name}/</span>
            </div>
            {node.children && (
              <TreeView
                nodes={node.children}
                selectedPath={selectedPath}
                onSelect={onSelect}
                depth={depth + 1}
              />
            )}
          </li>
        )
      })}
    </ul>
  )
}

// ── 代码块（扩展点：当前纯文本 <pre>，未来可替换为 Shiki/Monaco，调用方无感）─────

function CodeBlock({ content }: { content: string }) {
  return (
    <pre className="gf-forge-code-scroll min-h-0 flex-1 overflow-auto">
      <code className="block whitespace-pre px-4 py-3 font-mono text-xs leading-relaxed text-[#E2E8F0]">
        {content}
      </code>
    </pre>
  )
}

// ── 主组件 ──────────────────────────────────────────────────────────────────────

export function CodePreview({ gameId, version, accessToken }: Props) {
  const t = useT()
  const [selectedPath, setSelectedPath] = useState<string>('index.html')
  const [copied, setCopied] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState<string | null>(null)

  // 版本切换时重置选中文件（新版本可能结构不同）
  useEffect(() => {
    setSelectedPath('index.html')
  }, [version])

  const filesQuery = useQuery({
    queryKey: ['artifact-files', gameId, version],
    enabled: Boolean(gameId && accessToken),
    queryFn: () => gamesApi.listVersionFiles(gameId, version, accessToken),
  })

  const files = filesQuery.data?.data ?? []
  const tree = useMemo(() => buildFileTree(files), [files])
  const hasSelected = files.some((f) => f.path === selectedPath)

  const contentQuery = useQuery({
    queryKey: ['artifact-file-content', gameId, version, selectedPath],
    // 文件树加载完且选中文件确实存在才拉内容（空产物不发请求）
    enabled: Boolean(gameId && accessToken && selectedPath && hasSelected),
    queryFn: () => gamesApi.fetchVersionFile(gameId, version, selectedPath, accessToken),
  })

  const selectedSize = files.find((f) => f.path === selectedPath)?.size
  const isLarge = selectedSize != null && selectedSize > LARGE_FILE_BYTES

  async function handleCopy() {
    if (contentQuery.data == null) return
    try {
      await navigator.clipboard.writeText(contentQuery.data)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // 剪贴板被浏览器拒绝（iframe 权限等），静默；下载仍可用
    }
  }

  async function handleDownload() {
    setDownloading(true)
    setDownloadError(null)
    try {
      const file = await gamesApi.downloadVersion(gameId, version, accessToken)
      downloadFile(file.blob, file.filename ?? `game-v${version}.html`)
    } catch (e) {
      setDownloadError(formatApiError(e, t('forgeCodeDownloadFailed')))
    } finally {
      setDownloading(false)
    }
  }

  if (filesQuery.isLoading) {
    return (
      <div className="flex h-full items-center gap-2 px-1 text-xs text-[#94A3B8]">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        {t('loading')}
      </div>
    )
  }

  if (filesQuery.error) {
    return (
      <p className="px-1 py-2 text-xs text-rose-400">
        {formatApiError(filesQuery.error, t('forgeCodeLoadError'))}
      </p>
    )
  }

  if (files.length === 0) {
    return (
      <div className="grid h-full place-items-center px-6 text-center">
        <div className="max-w-sm">
          <FileCode2 className="mx-auto h-8 w-8 text-[#475569]" aria-hidden="true" />
          <p className="mt-3 text-sm font-medium text-[#CBD5E1]">{t('forgeCodeEmpty')}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 gap-2">
      {/* 文件树 */}
      <aside className="w-40 shrink-0 overflow-y-auto rounded-lg border border-white/[0.06] bg-black/20 p-1.5 lg:w-48">
        <TreeView nodes={tree} selectedPath={selectedPath} onSelect={setSelectedPath} />
      </aside>

      {/* 代码区 */}
      <div className="flex min-h-0 flex-1 flex-col rounded-lg border border-white/[0.06] bg-[#0B0F17]">
        <div className="flex items-center justify-between gap-2 border-b border-white/[0.06] px-3 py-1.5">
          <span className="truncate font-mono text-xs text-[#94A3B8]">{selectedPath}</span>
          <div className="flex shrink-0 items-center gap-1">
            <button
              type="button"
              onClick={handleCopy}
              disabled={contentQuery.isLoading || contentQuery.data == null}
              title={t('forgeCodeCopy')}
              aria-label={t('forgeCodeCopy')}
              className="grid h-7 w-7 cursor-pointer place-items-center rounded-md text-[#94A3B8] transition-colors hover:bg-white/[0.06] hover:text-[#E2E8F0] disabled:cursor-not-allowed disabled:opacity-40 focus-visible:ring-2 focus-visible:ring-[rgba(59,130,246,0.3)]"
            >
              {copied ? (
                <Check className="h-3.5 w-3.5 text-emerald-400" aria-hidden="true" />
              ) : (
                <Copy className="h-3.5 w-3.5" aria-hidden="true" />
              )}
            </button>
            <button
              type="button"
              onClick={handleDownload}
              disabled={downloading}
              title={t('forgeCodeDownload')}
              aria-label={t('forgeCodeDownload')}
              className="grid h-7 w-7 cursor-pointer place-items-center rounded-md text-[#94A3B8] transition-colors hover:bg-white/[0.06] hover:text-[#E2E8F0] disabled:cursor-not-allowed disabled:opacity-40 focus-visible:ring-2 focus-visible:ring-[rgba(59,130,246,0.3)]"
            >
              {downloading ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
              ) : (
                <Download className="h-3.5 w-3.5" aria-hidden="true" />
              )}
            </button>
          </div>
        </div>

        {isLarge ? (
          <div className="border-b border-amber-500/20 bg-amber-500/[0.08] px-3 py-1.5 text-[11px] text-amber-300">
            {t('forgeCodeLarge')}
          </div>
        ) : null}

        {contentQuery.isLoading ? (
          <div className="flex flex-1 items-center gap-2 px-3 py-2 text-xs text-[#94A3B8]">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            {t('loading')}
          </div>
        ) : contentQuery.error ? (
          <p className="px-3 py-2 text-xs text-rose-400">
            {formatApiError(contentQuery.error, t('forgeCodeLoadError'))}
          </p>
        ) : contentQuery.data != null ? (
          <CodeBlock content={contentQuery.data} />
        ) : null}

        {downloadError ? (
          <p className="border-t border-white/[0.06] px-3 py-1.5 text-[11px] text-rose-400">
            {downloadError}
          </p>
        ) : null}
      </div>
    </div>
  )
}
