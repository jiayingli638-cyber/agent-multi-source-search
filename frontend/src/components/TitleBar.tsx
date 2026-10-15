import React, { useState } from 'react';
import {
  PanelLeft,
  Search,
  Columns2,
  Minus,
  Square,
  X,
  Radio,
  Globe,
} from 'lucide-react';

interface TitleBarProps {
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  onOpenSearch: () => void;
  onToggleSources: () => void;
  sourcesOpen: boolean;
  availableCount: number;
  totalCount: number;
}

export const TitleBar: React.FC<TitleBarProps> = ({
  sidebarOpen,
  onToggleSidebar,
  onOpenSearch,
  onToggleSources,
  sourcesOpen,
  availableCount,
  totalCount,
}) => {
  const [activeMenu, setActiveMenu] = useState<string | null>(null);

  const menuItems = [
    {
      label: '检索(S)',
      options: ['新建检索 (⌘N)', '重新检索当前问题 (⌘R)', '导出引用为 Markdown', '导出检索报告 (JSON)', '清空会话'],
    },
    {
      label: '数据源(D)',
      options: ['查看数据源状态', '刷新数据源可用性', '打开 backend/.env 配置', 'MediaCrawler 部署指引', '官方 API 申请指引'],
    },
    {
      label: '查看(V)',
      options: ['切换侧边栏 (⌘B)', '切换数据源面板', '显示转载来源标注', '紧凑视图', '重置缩放 (⌘0)'],
    },
    {
      label: '帮助(H)',
      options: ['快捷键文档', '检索结果如何生成', '引用编号规则', '关于多源检索 Agent'],
    },
  ];

  return (
    <header className="h-9 bg-[#0b0d13] border-b border-white/[0.07] flex items-center justify-between px-2.5 text-xs text-[#94a3b8] select-none z-30 shrink-0">
      <div className="flex items-center gap-1.5">
        <button
          onClick={onToggleSidebar}
          title={sidebarOpen ? '折叠侧边栏 (⌘B)' : '展开侧边栏 (⌘B)'}
          className={`p-1 rounded transition-colors cursor-pointer ${
            sidebarOpen
              ? 'text-[#38bdf8] bg-white/[0.04]'
              : 'text-[#64748b] hover:text-white hover:bg-white/[0.05]'
          }`}
        >
          <PanelLeft className="w-3.5 h-3.5" />
        </button>

        <button
          onClick={onOpenSearch}
          title="搜索历史会话 (⌘P)"
          className="p-1 rounded text-[#64748b] hover:text-white hover:bg-white/[0.05] transition-colors cursor-pointer"
        >
          <Search className="w-3.5 h-3.5" />
        </button>

        <div className="h-3 w-[1px] bg-white/[0.08] mx-1" />

        <div className="flex items-center gap-0.5 relative">
          {menuItems.map((menu) => (
            <div key={menu.label} className="relative">
              <button
                onClick={() => setActiveMenu(activeMenu === menu.label ? null : menu.label)}
                onMouseEnter={() => {
                  if (activeMenu) setActiveMenu(menu.label);
                }}
                className={`px-2 py-1 rounded text-[11px] font-normal transition-colors cursor-pointer ${
                  activeMenu === menu.label
                    ? 'text-white bg-white/[0.08]'
                    : 'hover:text-white hover:bg-white/[0.04]'
                }`}
              >
                {menu.label}
              </button>

              {activeMenu === menu.label && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setActiveMenu(null)} />
                  <div className="absolute left-0 top-full mt-1 w-56 bg-[#121520] border border-white/10 rounded-md shadow-2xl py-1 z-50 text-[11px] backdrop-blur-md">
                    {menu.options.map((opt) => (
                      <button
                        key={opt}
                        onClick={() => setActiveMenu(null)}
                        className="w-full text-left px-3 py-1.5 hover:bg-[#38bdf8]/15 hover:text-[#38bdf8] text-[#cbd5e1] flex items-center justify-between transition-colors cursor-pointer"
                      >
                        <span>{opt.split(' (')[0]}</span>
                        {opt.includes('(') && (
                          <span className="text-[10px] text-[#64748b] font-mono">
                            {opt.split('(')[1].replace(')', '')}
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Center: brand */}
      <div className="absolute left-1/2 -translate-x-1/2 flex items-center gap-1.5 pointer-events-none">
        <Globe className="w-3.5 h-3.5 text-cyan-400" />
        <span className="text-[11.5px] font-medium text-[#cbd5e1] tracking-wide">
          多源网络检索 Agent
        </span>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={onToggleSources}
          title="数据源状态面板"
          className={`flex items-center gap-1.5 px-2 py-1 rounded text-[11px] transition-colors cursor-pointer ${
            sourcesOpen
              ? 'text-cyan-300 bg-cyan-500/10'
              : 'text-[#94a3b8] hover:text-white hover:bg-white/[0.06]'
          }`}
        >
          <Radio className="w-3.5 h-3.5" />
          <span className="font-mono">
            {availableCount}/{totalCount}
          </span>
        </button>

        <div className="h-3 w-[1px] bg-white/[0.08] mx-0.5" />

        <div className="flex items-center gap-1">
          <button
            title="分屏视图"
            className="p-1 rounded text-[#94a3b8] hover:text-white hover:bg-white/[0.05] transition-colors cursor-pointer"
          >
            <Columns2 className="w-3.5 h-3.5" />
          </button>
          <button
            title="最小化"
            className="w-6 h-6 flex items-center justify-center rounded hover:bg-white/[0.08] text-[#94a3b8] hover:text-white transition-colors"
          >
            <Minus className="w-3 h-3" />
          </button>
          <button
            title="最大化"
            className="w-6 h-6 flex items-center justify-center rounded hover:bg-white/[0.08] text-[#94a3b8] hover:text-white transition-colors"
          >
            <Square className="w-2.5 h-2.5" />
          </button>
          <button
            title="关闭窗口"
            className="w-6 h-6 flex items-center justify-center rounded hover:bg-rose-500/20 text-[#94a3b8] hover:text-rose-400 transition-colors"
          >
            <X className="w-3 h-3" />
          </button>
        </div>
      </div>
    </header>
  );
};
