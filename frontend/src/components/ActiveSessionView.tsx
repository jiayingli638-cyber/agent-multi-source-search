import React, { useState, useRef, useEffect } from 'react';
import {
  ArrowLeft,
  Terminal,
  Copy,
  Check,
  ChevronDown,
  ChevronRight,
  ArrowUp,
  Sparkles,
  Loader2,
  ExternalLink,
  AlertTriangle,
  Info,
  ListTree,
  FileText,
  Star,
  GitFork,
} from 'lucide-react';
import { Session, ChatMessage, Citation, ToolLog } from '../types';
import { platformStyle, KIND_LABELS } from '../data/mockData';

interface ActiveSessionViewProps {
  session: Session;
  onBackToHome: () => void;
  onSendMessage: (sessionId: string, message: string) => void;
}

/** 单条引用卡片 */
const CitationCard: React.FC<{ citation: Citation; index: number }> = ({ citation, index }) => {
  const style = platformStyle(citation.source);
  const stars = citation.extras?.stars as number | undefined;
  const likes = citation.extras?.likes as number | undefined;
  const mergedFrom = citation.extras?.merged_from as string | undefined;

  return (
    <a
      href={citation.url || undefined}
      target="_blank"
      rel="noreferrer"
      className="group flex gap-2.5 p-2.5 rounded-lg border border-white/[0.07] bg-[#0f121c]/70 hover:border-cyan-500/40 hover:bg-[#121624] transition-all"
    >
      <span className="shrink-0 w-6 h-6 rounded-md bg-white/[0.05] border border-white/[0.08] flex items-center justify-center text-[10.5px] font-mono text-[#94a3b8] group-hover:text-cyan-300 group-hover:border-cyan-500/40 transition-colors">
        {index}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 mb-1 flex-wrap">
          <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium border ${style.bg} ${style.text}`}>
            {style.short}
          </span>
          {citation.author && (
            <span className="text-[10px] text-[#64748b] truncate max-w-[120px]">{citation.author}</span>
          )}
          {citation.published_at && (
            <span className="text-[10px] text-[#475569]">{citation.published_at}</span>
          )}
          {typeof stars === 'number' && stars > 0 && (
            <span className="flex items-center gap-0.5 text-[10px] text-amber-400/90">
              <Star className="w-2.5 h-2.5" />
              {stars}
            </span>
          )}
          {typeof likes === 'number' && likes > 0 && (
            <span className="text-[10px] text-rose-400/90">♥ {likes}</span>
          )}
          {mergedFrom && (
            <span className="flex items-center gap-0.5 text-[10px] text-[#64748b]" title={`多源印证：${mergedFrom}`}>
              <GitFork className="w-2.5 h-2.5" />
              多源
            </span>
          )}
        </div>
        <div className="text-[12.5px] text-[#e2e8f0] leading-snug line-clamp-2 group-hover:text-white">
          {citation.title}
        </div>
        {citation.snippet && (
          <div className="mt-1 text-[11px] text-[#64748b] leading-relaxed line-clamp-2">
            {citation.snippet}
          </div>
        )}
      </div>
      <ExternalLink className="w-3 h-3 shrink-0 mt-1 text-[#475569] group-hover:text-cyan-400 transition-colors" />
    </a>
  );
};

/** 检索进度（工具执行流） */
const ProgressFeed: React.FC<{ logs: ToolLog[]; running: boolean }> = ({ logs, running }) => {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="rounded-xl border border-white/[0.08] bg-[#111420]/60 overflow-hidden">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs hover:bg-white/[0.02] transition-colors cursor-pointer"
      >
        <div className="flex items-center gap-2">
          {running ? (
            <Loader2 className="w-3.5 h-3.5 text-cyan-400 animate-spin" />
          ) : (
            <ListTree className="w-3.5 h-3.5 text-emerald-400" />
          )}
          <span className="font-medium text-[#cbd5e1]">
            {running ? '检索进行中…' : `检索过程（${logs.length} 步）`}
          </span>
        </div>
        {expanded ? (
          <ChevronDown className="w-3.5 h-3.5 text-[#64748b]" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5 text-[#64748b]" />
        )}
      </button>

      {expanded && logs.length > 0 && (
        <div className="px-3 py-2.5 border-t border-white/[0.05] bg-[#0c0e17] space-y-1.5">
          {logs.map((log) => (
            <div key={log.id} className="flex items-start gap-2 text-[11.5px] font-mono">
              <span
                className={`shrink-0 w-3.5 text-center ${
                  log.ok ? 'text-emerald-400' : 'text-amber-400'
                }`}
              >
                {log.ok ? '✓' : '!'}
              </span>
              <span className="shrink-0 text-cyan-300/90 min-w-[92px]">{log.name}</span>
              <span className="text-[#94a3b8] break-all">{log.result}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

/** 引用来源列表 */
const CitationList: React.FC<{ citations: Citation[] }> = ({ citations }) => {
  const [expanded, setExpanded] = useState(true);

  if (citations.length === 0) return null;

  // 按平台分组统计
  const byPlatform = citations.reduce<Record<string, number>>((acc, c) => {
    acc[c.platform || c.source] = (acc[c.platform || c.source] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="rounded-xl border border-white/[0.09] bg-[#0d101a] overflow-hidden">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2 bg-[#121522] border-b border-white/[0.07] hover:bg-[#161a2b] transition-colors cursor-pointer"
      >
        <div className="flex items-center gap-2">
          <FileText className="w-3.5 h-3.5 text-cyan-400" />
          <span className="text-[12.5px] text-white font-medium">
            引用来源 · {citations.length} 条
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="hidden sm:flex items-center gap-1.5">
            {Object.entries(byPlatform)
              .sort((a, b) => b[1] - a[1])
              .slice(0, 5)
              .map(([name, count]) => (
                <span key={name} className="text-[10px] text-[#64748b] font-mono">
                  {name}×{count}
                </span>
              ))}
          </div>
          {expanded ? (
            <ChevronDown className="w-3.5 h-3.5 text-[#64748b]" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 text-[#64748b]" />
          )}
        </div>
      </button>

      {expanded && (
        <div className="p-2 grid grid-cols-1 lg:grid-cols-2 gap-2 max-h-[420px] overflow-y-auto">
          {citations.map((c, i) => (
            <CitationCard key={c.id || i} citation={c} index={i + 1} />
          ))}
        </div>
      )}
    </div>
  );
};

/** 统计条 */
const StatsBar: React.FC<{ msg: ChatMessage }> = ({ msg }) => {
  const stats = msg.stats;
  if (!stats) return null;

  const errCount = Object.keys(stats.errors ?? {}).length;

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 px-3 py-2 rounded-lg bg-[#0f121c]/70 border border-white/[0.07] text-[11px]">
      <span className="text-[#94a3b8]">
        采集 <span className="text-cyan-300 font-mono">{stats.total_fetched}</span> 条
      </span>
      <span className="text-white/10">|</span>
      <span className="text-[#94a3b8]">
        去重后 <span className="text-cyan-300 font-mono">{stats.after_dedup}</span> 条
      </span>
      <span className="text-white/10">|</span>
      <span className="text-[#94a3b8]">
        引用 <span className="text-emerald-300 font-mono">{msg.citations?.length ?? 0}</span> 条
      </span>
      <span className="text-white/10">|</span>
      <span className="text-[#94a3b8]">
        耗时 <span className="text-violet-300 font-mono">{(stats.elapsed_ms / 1000).toFixed(1)}s</span>
      </span>
      {errCount > 0 && (
        <>
          <span className="text-white/10">|</span>
          <span className="flex items-center gap-1 text-amber-400">
            <AlertTriangle className="w-3 h-3" />
            {errCount} 个源异常
          </span>
        </>
      )}
      {msg.degraded && (
        <>
          <span className="text-white/10">|</span>
          <span className="flex items-center gap-1 text-amber-400" title={msg.notes?.join('\n')}>
            <Info className="w-3 h-3" />
            部分降级
          </span>
        </>
      )}
    </div>
  );
};

/** 子查询 + 调度计划 */
const PlanDetails: React.FC<{ msg: ChatMessage }> = ({ msg }) => {
  const [expanded, setExpanded] = useState(false);

  if (!msg.subQueries?.length && !msg.plan?.length) return null;

  return (
    <div className="rounded-xl border border-white/[0.07] bg-[#101320]/50 overflow-hidden">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs hover:bg-white/[0.02] transition-colors cursor-pointer"
      >
        <div className="flex items-center gap-2">
          <Sparkles className="w-3.5 h-3.5 text-violet-400" />
          <span className="text-[#cbd5e1] font-medium">
            查询拆解与调度策略
          </span>
          <span className="text-[10px] text-[#64748b] font-mono">
            {msg.subQueries?.length ?? 0} 子查询 · {msg.plan?.length ?? 0} 源
          </span>
        </div>
        {expanded ? (
          <ChevronDown className="w-3.5 h-3.5 text-[#64748b]" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5 text-[#64748b]" />
        )}
      </button>

      {expanded && (
        <div className="px-3 py-2.5 border-t border-white/[0.05] bg-[#0c0e17] space-y-3 text-[11.5px]">
          {msg.subQueries && msg.subQueries.length > 0 && (
            <div>
              <div className="text-[10px] font-mono uppercase tracking-wider text-[#64748b] mb-1.5">
                子查询
              </div>
              <div className="space-y-1">
                {msg.subQueries.map((q, i) => (
                  <div key={i} className="text-[#94a3b8] font-mono flex gap-2">
                    <span className="text-cyan-400/70">{i + 1}.</span>
                    <span className="break-all">{q}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {msg.plan && msg.plan.length > 0 && (
            <div>
              <div className="text-[10px] font-mono uppercase tracking-wider text-[#64748b] mb-1.5">
                调度计划
              </div>
              <div className="space-y-1.5">
                {msg.plan.map((p, i) => {
                  const style = platformStyle(p.source);
                  return (
                    <div key={i} className="flex items-start gap-2">
                      <span className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] border ${style.bg} ${style.text}`}>
                        {style.short}
                      </span>
                      <div className="min-w-0">
                        <div className="text-[#cbd5e1] font-mono text-[11px] break-all">
                          {p.query}
                        </div>
                        {p.reason && (
                          <div className="text-[10px] text-[#64748b]">
                            {KIND_LABELS[p.kind] ?? p.kind} · {p.reason}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

/** 答案文本（处理引用编号高亮） */
const AnswerBody: React.FC<{ content: string }> = ({ content }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  // 按行渲染，保留标题/列表结构；引用编号 [n] 高亮
  const renderLine = (line: string, key: number) => {
    const parts = line.split(/(\[\d+(?:\[\d+\])*\])/g);
    const isHeading = /^#{1,4}\s/.test(line) || /^\*\*[^*]+\*\*$/.test(line.trim());
    const isList = /^\s*[-*•]\s/.test(line) || /^\s*\d+\.\s/.test(line);

    const inner = parts.map((part, i) => {
      if (/^\[\d/.test(part)) {
        return (
          <span
            key={i}
            className="inline-flex items-center px-1 mx-0.5 rounded bg-cyan-500/15 text-cyan-300 text-[10.5px] font-mono align-baseline"
          >
            {part.replace(/[[\]]/g, '')}
          </span>
        );
      }
      return <span key={i}>{part.replace(/^#{1,4}\s/, '').replace(/\*\*/g, '')}</span>;
    });

    if (!line.trim()) return <div key={key} className="h-2" />;

    return (
      <div
        key={key}
        className={
          isHeading
            ? 'font-semibold text-white mt-2 mb-0.5'
            : isList
            ? 'text-[#cbd5e1]'
            : 'text-[#cbd5e1]'
        }
      >
        {inner}
      </div>
    );
  };

  return (
    <div className="px-4 py-3 rounded-2xl rounded-tl-sm bg-[#121524]/90 border border-white/[0.1] text-[13.5px] leading-relaxed shadow-xl relative group">
      <button
        onClick={handleCopy}
        title="复制答案"
        className="absolute top-2 right-2 p-1.5 rounded-md opacity-0 group-hover:opacity-100 hover:bg-white/[0.08] text-[#64748b] hover:text-white transition-all cursor-pointer"
      >
        {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
      </button>
      <div className="space-y-0.5 pr-6">
        {content.split('\n').map((line, i) => renderLine(line, i))}
      </div>
    </div>
  );
};

export const ActiveSessionView: React.FC<ActiveSessionViewProps> = ({
  session,
  onBackToHome,
  onSendMessage,
}) => {
  const [inputText, setInputText] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [session.messages]);

  const handleSend = () => {
    if (!inputText.trim()) return;
    onSendMessage(session.id, inputText.trim());
    setInputText('');
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#090a10] overflow-hidden">
      {/* Header */}
      <div className="h-12 border-b border-white/[0.08] bg-[#0c0e18]/80 backdrop-blur-md px-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={onBackToHome}
            className="flex items-center gap-1.5 px-2 py-1 rounded text-xs text-[#94a3b8] hover:text-white hover:bg-white/[0.06] transition-colors cursor-pointer shrink-0"
          >
            <ArrowLeft className="w-3.5 h-3.5 text-cyan-400" />
            <span>主页</span>
          </button>
          <div className="h-3 w-[1px] bg-white/[0.1]" />
          <h2 className="text-sm font-semibold text-white truncate">{session.title}</h2>
          {session.hasWarning && (
            <span className="flex items-center gap-1 text-[11px] text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20 shrink-0">
              <AlertTriangle className="w-3 h-3" />
              结果受限
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 text-[11px] shrink-0">
          <span className="font-mono text-[#64748b]">
            模型: <span className="text-cyan-300">DeepSeek</span>
          </span>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
        {session.messages.map((msg) => {
          const running = msg.status === 'generating';
          return (
            <div
              key={msg.id}
              className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}
            >
              <div className="flex items-center gap-2 mb-1.5 px-1">
                <span className="text-[11px] font-mono text-[#64748b]">
                  {msg.sender === 'user' ? '你' : '检索 Agent'}
                </span>
                <span className="text-[10px] text-[#475569]">{msg.timestamp}</span>
              </div>

              {msg.sender === 'user' ? (
                <div className="max-w-2xl px-4 py-2.5 rounded-2xl rounded-tr-sm bg-gradient-to-r from-cyan-950/60 to-blue-950/60 border border-cyan-500/30 text-white text-[13.5px] leading-relaxed shadow-lg whitespace-pre-wrap">
                  {msg.content}
                </div>
              ) : (
                <div className="max-w-3xl w-full flex flex-col gap-3">
                  {/* 检索过程 */}
                  {(running || (msg.toolLogs && msg.toolLogs.length > 0)) && (
                    <ProgressFeed logs={msg.toolLogs ?? []} running={running} />
                  )}

                  {/* 答案 */}
                  {msg.content && !running && <AnswerBody content={msg.content} />}

                  {/* 统计 */}
                  {!running && <StatsBar msg={msg} />}

                  {/* 拆解与计划 */}
                  {!running && <PlanDetails msg={msg} />}

                  {/* 引用 */}
                  {!running && msg.citations && msg.citations.length > 0 && (
                    <CitationList citations={msg.citations} />
                  )}

                  {/* 提示 */}
                  {!running && msg.notes && msg.notes.length > 0 && (
                    <div className="flex items-start gap-2 px-3 py-2 rounded-lg bg-amber-500/[0.07] border border-amber-500/20 text-[11.5px] text-amber-300/90">
                      <Info className="w-3.5 h-3.5 mt-px shrink-0" />
                      <div className="space-y-0.5">
                        {msg.notes.map((n, i) => (
                          <div key={i}>{n}</div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 错误时的终端样式 */}
                  {msg.status === 'error' && (
                    <div className="rounded-xl border border-rose-500/25 bg-[#0b0a10] overflow-hidden">
                      <div className="flex items-center gap-2 px-3 py-1.5 bg-rose-950/30 border-b border-rose-500/20 text-[11px] text-rose-300">
                        <Terminal className="w-3.5 h-3.5" />
                        <span className="font-mono">执行失败</span>
                      </div>
                      <div className="p-3 font-mono text-[11.5px] text-rose-200/90 whitespace-pre-wrap">
                        {msg.content}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-white/[0.08] bg-[#0c0e18]/95 backdrop-blur-xl">
        <div className="max-w-4xl mx-auto rounded-xl bg-[#121524] border border-white/[0.12] p-2 flex items-center gap-2 shadow-2xl focus-within:border-cyan-500/50">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="继续追问，Agent 会重新调度检索… (Enter 发送)"
            className="flex-1 bg-transparent text-sm text-white placeholder:text-[#64748b] px-3 focus:outline-none"
          />
          <button
            onClick={handleSend}
            disabled={!inputText.trim()}
            className={`w-8 h-8 rounded-lg flex items-center justify-center transition-all cursor-pointer ${
              inputText.trim()
                ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-[0_0_12px_rgba(16,185,129,0.5)]'
                : 'bg-white/[0.06] text-[#64748b] cursor-not-allowed'
            }`}
          >
            <ArrowUp className="w-4 h-4 stroke-[2.5]" />
          </button>
        </div>
      </div>
    </div>
  );
};
