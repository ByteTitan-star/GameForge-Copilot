// P1 验证用最小入口：在 #root 渲染一个 Canvas，证明 Vite+TS 构建链与 base:'./' 产物可加载。
// 不含任何游戏逻辑——P1 只验证构建基础设施，LLM 尚未参与。
const root = document.getElementById('root')
if (!root) {
  throw new Error('#root not found')
}

const canvas = document.createElement('canvas')
canvas.width = 320
canvas.height = 240
root.appendChild(canvas)

const ctx = canvas.getContext('2d')
if (ctx) {
  ctx.fillStyle = '#0f172a'
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  ctx.fillStyle = '#e2e8f0'
  ctx.font = '16px sans-serif'
  ctx.fillText('GameForge build pipeline OK', 20, 120)
}
