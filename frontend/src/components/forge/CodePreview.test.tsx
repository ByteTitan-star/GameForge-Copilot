import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { CodePreview, buildFileTree } from './CodePreview'
import { gamesApi } from '@/api/games'
import type { ArtifactFile } from '@/api/types'

vi.mock('@/api/games', () => ({
  gamesApi: {
    listVersionFiles: vi.fn(),
    fetchVersionFile: vi.fn(),
    downloadVersion: vi.fn(),
  },
}))

const listFiles = vi.mocked(gamesApi.listVersionFiles)
const fetchFile = vi.mocked(gamesApi.fetchVersionFile)

function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } })
}

function renderPreview(props: Partial<React.ComponentProps<typeof CodePreview>> = {}) {
  render(
    <QueryClientProvider client={makeClient()}>
      <CodePreview gameId="g-1" version={1} accessToken="tok" {...props} />
    </QueryClientProvider>,
  )
}

const singleFile: ArtifactFile[] = [{ path: 'index.html', size: 100, mime: 'text/html' }]

const multiFiles: ArtifactFile[] = [
  { path: 'index.html', size: 100, mime: 'text/html' },
  { path: 'assets/app.js', size: 50, mime: 'text/javascript' },
  { path: 'assets/style.css', size: 30, mime: 'text/css' },
]

function asList<T>(data: T[]) {
  return { data, total: data.length, page: 1, size: Math.max(data.length, 1) }
}

describe('buildFileTree', () => {
  it('单文件退化为单节点', () => {
    const tree = buildFileTree(singleFile)
    expect(tree).toHaveLength(1)
    expect(tree[0]!.name).toBe('index.html')
    expect(tree[0]!.isDir).toBe(false)
  })

  it('扁平多文件 + 嵌套目录正确折叠', () => {
    const tree = buildFileTree(multiFiles)
    // 顶层：index.html 文件 + assets 目录
    expect(tree.map((n) => n.name)).toEqual(['assets', 'index.html'])
    const assets = tree.find((n) => n.name === 'assets')!
    expect(assets.isDir).toBe(true)
    expect(assets.children!.map((c) => c.name)).toEqual(['app.js', 'style.css'])
  })

  it('目录排在文件之前', () => {
    const tree = buildFileTree(multiFiles)
    expect(tree[0]!.isDir).toBe(true)
  })
})

describe('CodePreview', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('加载文件树并默认选中 index.html 展示内容', async () => {
    listFiles.mockResolvedValue(asList(singleFile))
    fetchFile.mockResolvedValue('<!doctype html><body>hi</body>')

    renderPreview()

    await waitFor(() => {
      expect(screen.getAllByText('index.html').length).toBeGreaterThan(0)
    })
    // 代码区内容渲染
    expect(screen.getByText(/<!doctype html>/)).toBeTruthy()
    expect(fetchFile).toHaveBeenCalledWith('g-1', 1, 'index.html', 'tok')
  })

  it('空产物显示空状态', async () => {
    listFiles.mockResolvedValue(asList([]))

    renderPreview()

    await waitFor(() => {
      expect(screen.getByText(/暂无产物文件|No artifact files/i)).toBeTruthy()
    })
    // 空产物不发内容请求（组件 enabled 守卫）
    expect(fetchFile).not.toHaveBeenCalled()
  })

  it('加载失败显示错误态', async () => {
    listFiles.mockRejectedValue(new Error('boom'))

    renderPreview()

    await waitFor(() => {
      expect(screen.getByText('boom')).toBeTruthy()
    })
  })

  it('切换文件树节点重新拉取对应文件内容', async () => {
    listFiles.mockResolvedValue(asList(multiFiles))
    fetchFile.mockResolvedValue('content')

    renderPreview()

    await waitFor(() => {
      expect(fetchFile).toHaveBeenCalledWith('g-1', 1, 'index.html', 'tok')
    })

    fireEvent.click(screen.getByText('app.js'))
    await waitFor(() => {
      expect(fetchFile).toHaveBeenCalledWith('g-1', 1, 'assets/app.js', 'tok')
    })
  })

  it('version 切换后重置选中文件', async () => {
    listFiles.mockResolvedValue(asList(singleFile))
    fetchFile.mockResolvedValue('x')

    const { rerender } = render(
      <QueryClientProvider client={makeClient()}>
        <CodePreview gameId="g-1" version={1} accessToken="tok" />
      </QueryClientProvider>,
    )

    await waitFor(() => {
      expect(fetchFile).toHaveBeenCalledWith('g-1', 1, 'index.html', 'tok')
    })

    rerender(
      <QueryClientProvider client={makeClient()}>
        <CodePreview gameId="g-1" version={2} accessToken="tok" />
      </QueryClientProvider>,
    )

    await waitFor(() => {
      expect(fetchFile).toHaveBeenCalledWith('g-1', 2, 'index.html', 'tok')
    })
  })
})
