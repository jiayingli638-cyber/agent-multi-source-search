import React, { useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  SlidersHorizontal,
  Plus,
  Settings,
  Check,
  MessageSquare,
  Cpu,
  Globe,
  Gauge,
} from 'lucide-react';
import { ModelOption, SearchMode, Session } from '../types';
import { AVAILABLE_MODELS, SEARCH_MODES, SEARCH_DEPTHS } from '../data/mockData';

interface SidebarProps {
  onNewChat: () => void;
  sessions: Session[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  model: ModelOption;
  onSelectModel: (m: ModelOption) => void;
  searchMode: SearchMode;
  onSelectSearchMode: (m: SearchMode) => void;
  depth: string;
  onSelectDepth: (d: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  onNewChat,
  sessions,
  activeSessionId,
  onSelectSession,
  model,
  onSelectModel,
  searchMode,
  onSelectSearchMode,
  depth,
  onSelectDepth,
}) => {
  const [settingsExpanded, setSettingsExpanded] = useState(true);
  const [historyExpanded, setHistoryExpanded] = useState(true);

  return (
    <aside className="w-[260px] bg-[#0c0e16] border-r border-white/[0.06] flex flex-col justify-between h-full select-none shrink-0 relative z-20 text-[13px]">
      <div className="flex flex-col p-2.5 gap-2 overflow-y-auto flex-1">
        <button
          onClick={onNewChat}
          title="发起新检索 (⌘N)"
          className="w-full flex items-center justify-between px-3 py-2 rounded-lg bg-gradient-to-r from-cyan-500/10 via-cyan-500/5 to-violet-500/10 border border-cyan-500/30 hover:border-cyan-400/60 text-white font-medium hover:shadow-[0_0_15px_-3px_rgba(6,182,212,0.3)] transition-all group cursor-pointer"
        >
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded flex items-center justify-center bg-cyan-500/20 text-cyan-400 group-hover:bg-cyan-500 group-hover:text-black transition-colors">
              <Plus className="w-3.5 h-3.5" />
            </div>
            <span className="text-[13px] tracking-wide text-cyan-50 group-hover:text-white">
              新检索
            </span>
          </div>
          <span className="text-[11px] font-mono text-cyan-400/60 bg-white/[0.04] px-1.5 py-0.5 rounded border border-white/[0.06]">
            ⌘N
          </span>
        </button>

        <div className="h-[1px] bg-white/[0.05] my-1" />

        {/* 检索设置 */}
        <div className="flex flex-col gap-1">
          <button
            onClick={() => setSettingsExpanded((v) => !v)}
            className="flex items-center gap-1 px-2 py-1 text-[#64748b] text-[11px] font-medium hover:text-[#cbd5e1] transition-colors cursor-pointer"
          >
            {settingsExpanded ? (
              <ChevronDown className="w-3.5 h-3.5" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5" />
            )}
            <span>检索设置</span>
          </button>

          {settingsExpanded && (
            <div className="flex flex-col gap-2.5 px-1 pt-1">
              {/* 模型 */}
              <div>
                <div className="flex items-center gap-1.5 mb-1 px-1 text-[10px] font-mono uppercase tracking-wider text-[#475569]">
                  <Cpu className="w-2.5 h-2.5" />
                  推理模型
                </div>
                <div className="flex flex-col gap-0.5">
                  {AVAILABLE_MODELS.map((m) => (
                    <button
                      key={m.id}
                      onClick={() => onSelectModel(m)}
                      className={`w-full text-left px-2 py-1.5 rounded flex items-center justify-between transition-colors cursor-pointer ${
                        model.id === m.id
                          ? 'bg-cyan-500/12 text-cyan-200'
                          : 'text-[#94a3b8] hover:bg-white/[0.05] hover:text-[#cbd5e1]'
                      }`}
                    >
                      <div className="flex flex-col min-w-0">
                        <span className="text-[12px] truncate">{m.name}</span>
                        <span className="text-[10px] text-[#64748b]">{m.badge}</span>
                      </div>
                      {model.id === m.id && <Check className="w-3 h-3 text-cyan-400 shrink-0" />}
                    </button>
                  ))}
                </div>
              </div>

              {/* 检索范围 */}
              <div>
                <div className="flex items-center gap-1.5 mb-1 px-1 text-[10px] font-mono uppercase tracking-wider text-[#475569]">
                  <Globe className="w-2.5 h-2.5" />
                  检索范围
                </div>
                <div className="flex flex-wrap gap-1 px-1">
                  {SEARCH_MODES.map((m) => (
                    <button
                      key={m}
                      onClick={() => onSelectSearchMode(m)}
                      className={`px-2 py-1 rounded text-[11px] border transition-colors cursor-pointer ${
                        searchMode === m
                          ? 'bg-cyan-500/15 border-cyan-500/40 text-cyan-300'
                          : 'bg-white/[0.03] border-white/[0.07] text-[#94a3b8] hover:text-white hover:border-white/[0.16]'
                      }`}
                    >
                      {m}
                    </button>
                  ))}
                </div>
              </div>

              {/* 检索深度 */}
              <div>
                <div className="flex items-center gap-1.5 mb-1 px-1 text-[10px] font-mono uppercase tracking-wider text-[#475569]">
                  <Gauge className="w-2.5 h-2.5" />
                  检索深度
                </div>
                <div className="flex gap-1 px-1">
                  {SEARCH_DEPTHS.map((d) => (
                    <button
                      key={d.id}
                      onClick={() => onSelectDepth(d.id)}
                      title={d.desc}
                      className={`flex-1 px-2 py-1 rounded text-[11px] border transition-colors cursor-pointer ${
                        depth === d.id
                          ? 'bg-violet-500/15 border-violet-500/40 text-violet-300'
                          : 'bg-white/[0.03] border-white/[0.07] text-[#94a3b8] hover:text-white hover:border-white/[0.16]'
                      }`}
                    >
                      {d.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="h-[1px] bg-white/[0.05] my-1" />

        {/* 历史会话 */}
        <div className="flex flex-col gap-1 flex-1 min-h-0">
          <div className="flex items-center justify-between px-2 py-1 text-[#64748b] text-[11px] font-medium">
            <button
              onClick={() => setHistoryExpanded((v) => !v)}
              className="flex items-center gap-1 hover:text-[#cbd5e1] transition-colors cursor-pointer"
            >
              {historyExpanded ? (
                <ChevronDown className="w-3.5 h-3.5" />
              ) : (
                <ChevronRight className="w-3.5 h-3.5" />
              )}
              <span>检索历史</span>
            </button>
            <span className="text-[10px] font-mono text-[#475569]">{sessions.length}</span>
          </div>

          {historyExpanded && (
            <div className="flex flex-col gap-0.5 overflow-y-auto">
              {sessions.length === 0 ? (
                <div className="px-3 py-4 text-[11px] text-[#475569] text-center leading-relaxed">
                  暂无检索记录
                  <br />
                  从上方「新检索」开始
                </div>
              ) : (
                sessions.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => onSelectSession(s.id)}
                    className={`w-full text-left px-2.5 py-2 rounded-lg flex items-start gap-2 transition-colors cursor-pointer ${
                      activeSessionId === s.id
                        ? 'bg-cyan-500/10 border border-cyan-500/25'
                        : 'border border-transparent hover:bg-white/[0.04]'
                    }`}
                  >
                    <MessageSquare
                      className={`w-3.5 h-3.5 mt-0.5 shrink-0 ${
                        activeSessionId === s.id ? 'text-cyan-400' : 'text-[#475569]'
                      }`}
                    />
                    <div className="min-w-0 flex-1">
                      <div
                        className={`text-[12px] truncate ${
                          activeSessionId === s.id ? 'text-cyan-100' : 'text-[#cbd5e1]'
                        }`}
                      >
                        {s.title}
                      </div>
                      <div className="text-[10px] text-[#475569] font-mono mt-0.5">
                        {s.createdAt} · {s.messages.length} 轮
                      </div>
                    </div>
                  </button>
                ))
              )}
            </div>
          )}
        </div>
      </div>

      {/* Bottom bar */}
      <div className="p-2 border-t border-white/[0.06] bg-[#090b10]">
        <div className="flex items-center justify-between p-1.5 rounded-lg">
          <div className="flex items-center gap-2.5 truncate">
            <div className="w-7 h-7 rounded-md bg-gradient-to-tr from-cyan-500 via-violet-600 to-emerald-400 p-[1px] shrink-0 relative">
              <div className="w-full h-full bg-[#0b0d14] rounded-[5px] flex items-center justify-center">
                <span className="text-[10px] font-mono font-bold bg-gradient-to-r from-cyan-400 to-violet-400 bg-clip-text text-transparent">
                  RAG
                </span>
              </div>
              <div className="absolute -bottom-0.5 -right-0.5 w-2 h-2 rounded-full bg-emerald-400 border border-[#0b0d14]" />
            </div>
            <div className="flex flex-col text-left truncate">
              <span className="text-[12px] text-[#f1f5f9] font-medium truncate">本地检索节点</span>
              <span className="text-[10px] font-mono text-[#64748b]">127.0.0.1:8000</span>
            </div>
          </div>
          <Settings className="w-3.5 h-3.5 text-[#475569] shrink-0" />
        </div>
      </div>
    </aside>
  );
};
