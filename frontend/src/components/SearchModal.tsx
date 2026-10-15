import React, { useState, useEffect } from 'react';
import { Search, X, FileText, MessageSquare, Terminal, Sparkles, ArrowRight } from 'lucide-react';
import { Session } from '../types';

interface SearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  sessions: Session[];
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
}

export const SearchModal: React.FC<SearchModalProps> = ({
  isOpen,
  onClose,
  sessions,
  onSelectSession,
  onNewChat,
}) => {
  const [query, setQuery] = useState('');

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'p') {
        e.preventDefault();
        // toggle modal
      }
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const filteredSessions = sessions.filter((s) =>
    s.title.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 px-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-150">
      <div
        className="fixed inset-0 -z-10"
        onClick={onClose}
      />
      <div className="w-full max-w-xl bg-[#11131f] border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col">
        {/* Search Input Bar */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-white/[0.08] bg-[#141827]">
          <Search className="w-4 h-4 text-cyan-400 shrink-0" />
          <input
            type="text"
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="搜索检索历史…"
            className="flex-1 bg-transparent text-sm text-white placeholder:text-[#64748b] focus:outline-none"
          />
          <button
            onClick={onClose}
            className="p-1 rounded text-[#64748b] hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Results List */}
        <div className="p-2 max-h-80 overflow-y-auto space-y-1 text-xs">
          <div className="px-3 py-1.5 text-[10px] font-mono text-[#64748b] uppercase tracking-wider">
            快捷操作
          </div>
          <button
            onClick={() => {
              onNewChat();
              onClose();
            }}
            className="w-full flex items-center justify-between px-3 py-2 rounded-lg hover:bg-cyan-500/10 hover:text-cyan-200 text-[#cbd5e1] transition-colors text-left"
          >
            <div className="flex items-center gap-2.5">
              <Sparkles className="w-4 h-4 text-cyan-400" />
              <span className="font-medium">发起新检索 (新建任务)</span>
            </div>
            <span className="text-[10px] font-mono text-[#64748b]">⌘N</span>
          </button>

          <div className="px-3 py-1.5 text-[10px] font-mono text-[#64748b] uppercase tracking-wider mt-2">
            检索历史 ({filteredSessions.length})
          </div>
          {filteredSessions.map((s) => (
            <button
              key={s.id}
              onClick={() => {
                onSelectSession(s.id);
                onClose();
              }}
              className="w-full flex items-center justify-between px-3 py-2 rounded-lg hover:bg-white/[0.05] text-[#cbd5e1] hover:text-white transition-colors text-left"
            >
              <div className="flex items-center gap-2.5 truncate">
                <MessageSquare className="w-3.5 h-3.5 text-[#64748b] shrink-0" />
                <span className="truncate">{s.title}</span>
              </div>
              <span className="text-[10px] text-[#64748b] shrink-0 font-mono">{s.createdAt}</span>
            </button>
          ))}
        </div>

        <div className="px-4 py-2 border-t border-white/[0.06] bg-[#0c0e18] flex items-center justify-between text-[11px] text-[#64748b]">
          <span>按 ESC 退出</span>
          <span>按 ↑↓ 选择，Enter 确认</span>
        </div>
      </div>
    </div>
  );
};
