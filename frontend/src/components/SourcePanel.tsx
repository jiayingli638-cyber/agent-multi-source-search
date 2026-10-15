import React from 'react';
import { X, Radio, AlertCircle, CheckCircle2, KeyRound } from 'lucide-react';
import { SourceInfo } from '../types';
import { KIND_LABELS, platformStyle } from '../data/mockData';

interface SourcePanelProps {
  isOpen: boolean;
  onClose: () => void;
  sources: SourceInfo[];
}

const KIND_ORDER = ['general_cn', 'general_global', 'social_cn', 'recruit', 'code', 'academic', 'web'];

export const SourcePanel: React.FC<SourcePanelProps> = ({ isOpen, onClose, sources }) => {
  if (!isOpen) return null;

  const grouped = KIND_ORDER.map((kind) => ({
    kind,
    label: KIND_LABELS[kind] ?? kind,
    items: sources.filter((s) => s.kind === kind),
  })).filter((g) => g.items.length > 0);

  const available = sources.filter((s) => s.available).length;

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/40" onClick={onClose} />
      <aside className="w-[340px] h-full bg-[#0c0e16] border-l border-white/[0.08] flex flex-col shrink-0 z-50 absolute right-0 top-0 shadow-2xl">
        {/* Header */}
        <div className="h-12 border-b border-white/[0.08] px-4 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <Radio className="w-4 h-4 text-cyan-400" />
            <span className="text-sm font-medium text-white">数据源状态</span>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-white/[0.08] text-[#94a3b8] hover:text-white transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Summary */}
        <div className="px-4 py-3 border-b border-white/[0.06] bg-[#0a0c14]">
          <div className="flex items-center justify-between text-xs">
            <span className="text-[#94a3b8]">可用数据源</span>
            <span className="font-mono">
              <span className="text-emerald-400 font-semibold">{available}</span>
              <span className="text-[#64748b]"> / {sources.length}</span>
            </span>
          </div>
          <div className="mt-2 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-emerald-500 transition-all"
              style={{ width: `${sources.length ? (available / sources.length) * 100 : 0}%` }}
            />
          </div>
        </div>

        {/* Source list */}
        <div className="flex-1 overflow-y-auto p-3 space-y-4">
          {grouped.length === 0 && (
            <div className="text-center text-xs text-[#64748b] py-8">
              无法获取数据源信息。
              <br />
              请确认后端已启动（127.0.0.1:8000）
            </div>
          )}

          {grouped.map((group) => (
            <div key={group.kind}>
              <div className="px-1 mb-1.5 text-[10px] font-mono uppercase tracking-wider text-[#64748b]">
                {group.label}
              </div>
              <div className="space-y-1.5">
                {group.items.map((s) => {
                  const style = platformStyle(s.name);
                  return (
                    <div
                      key={s.name}
                      className="rounded-lg border border-white/[0.07] bg-[#111420]/60 px-3 py-2.5 hover:border-white/[0.14] transition-colors"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <span
                            className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium border ${style.bg} ${style.text}`}
                          >
                            {style.short}
                          </span>
                          <span className="text-[12.5px] text-[#e2e8f0] truncate">
                            {s.platform}
                          </span>
                        </div>
                        {s.available ? (
                          <span className="shrink-0 flex items-center gap-1 text-[10px] text-emerald-400">
                            <CheckCircle2 className="w-3 h-3" />
                            可用
                          </span>
                        ) : (
                          <span className="shrink-0 flex items-center gap-1 text-[10px] text-amber-400">
                            <AlertCircle className="w-3 h-3" />
                            未启用
                          </span>
                        )}
                      </div>

                      <p className="mt-1.5 text-[11px] text-[#64748b] leading-relaxed">
                        {s.description}
                      </p>

                      {!s.available && s.unavailable_reason && (
                        <p className="mt-1.5 flex items-start gap-1.5 text-[10.5px] text-amber-400/80 leading-relaxed">
                          <KeyRound className="w-3 h-3 mt-px shrink-0" />
                          <span>{s.unavailable_reason}</span>
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* Footer hint */}
        <div className="px-4 py-3 border-t border-white/[0.06] bg-[#0a0c14] text-[10.5px] text-[#64748b] leading-relaxed">
          未启用的数据源需在 <span className="font-mono text-[#94a3b8]">backend/.env</span> 中补齐凭证或完成本地部署。
          缺失凭证的源将降级为模拟数据，不影响整体检索。
        </div>
      </aside>
    </>
  );
};
