export function AdminPage() {
  return (
    <div className="space-y-5">
      <div>
        <p className="font-mono text-[10px] tracking-[0.16em] text-white/35 uppercase">Admin</p>
        <h1 className="text-2xl tracking-tight text-white/95 md:text-3xl">管理后台</h1>
        <p className="mt-1 text-sm text-white/40">审批队列 / 用户 / 系统用量（骨架）</p>
      </div>
      <div className="overflow-hidden rounded-2xl border border-white/[0.08] bg-[#12151a]">
        <table className="w-full text-left text-sm">
          <thead className="bg-white/[0.03] font-mono text-[10px] tracking-wider text-white/40 uppercase">
            <tr>
              <th className="px-4 py-3">游戏</th>
              <th className="px-4 py-3">状态</th>
              <th className="px-4 py-3">操作</th>
            </tr>
          </thead>
          <tbody className="text-white/75">
            <tr className="border-t border-white/[0.06]">
              <td className="px-4 py-3">像素跑酷（示例）</td>
              <td className="px-4 py-3 font-mono text-xs text-cyan-200/80">submitted</td>
              <td className="px-4 py-3 text-white/40">approve / reject（待接 API）</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}
