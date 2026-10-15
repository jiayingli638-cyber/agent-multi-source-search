import React, { useState, useRef, useEffect } from 'react';
import {
  ChevronDown,
  Check,
  ArrowUp,
  Sparkles,
  Layers,
  Globe,
  Gauge,
  Radio,
  AlertCircle,
  CheckCircle2,
} from 'lucide-react';
import { ModelOption, SearchMode, SourceInfo } from '../types';
import { AVAILABLE_MODELS, SEARCH_MODES, SEARCH_DEPTHS, platformStyle } from '../data/mockData';

interface PromptConsoleProps {
  onSubmitPrompt: (
    prompt: string,
    model: ModelOption,
    mode: SearchMode,
    depth: string
  ) => void;
  model: ModelOption;
  onSelectModel: (m: ModelOption) => void;
  searchMode: SearchMode;
  onSelectSearchMode: (m: SearchMode) => void;
  depth: string;
  onSelectDepth: (d: string) => void;
  sources: SourceInfo[];
  onOpenSources: () => void;
}

const EXAMPLES = [
  '「AI Agent 记忆机制」目前有哪些主流方案，各自取舍是什么？',
  '最近一周关于大模型推理成本下降的讨论和数据有哪些？',
  '有没有成熟的开源爬虫框架可以替代 MediaCrawler？',
  'LangGraph、AutoGen、CrewAI 三者架构差异与适用场景',
];

export const PromptConsole: React.FC<PromptConsoleProps> = ({
  onSubmitPrompt,
  model,
  onSelectModel,
  searchMode,
  onSelectSearchMode,
  depth,
  onSelectDepth,
  sources,
  onOpenSources,
}) => {
  const [promptText, setPromptText] = useState('');
  const [showModelPicker, setShowModelPicker] = useState(false);
  const [showModePicker, setShowModePicker] = useState(false);
  const [showDepthPicker, setShowDepthPicker] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 220)}px`;
    }
  }, [promptText]);

  const handleSend = () => {
    const trimmed = promptText.trim();
    if (!trimmed) return;
    onSubmitPrompt(trimmed, model, searchMode, depth);
    setPromptText('');
  };

  const available = sources.filter((s) => s.available).length;

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 max-w-4xl mx-auto w-full relative overflow-y-auto">
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[520px] h-[260px] bg-gradient-to-r from-cyan-500/10 via-violet-600/10 to-emerald-500/10 blur-[90px] pointer-events-none rounded-full" />

      <div className="text-center mb-6 relative z-10 flex flex-col items-center">
        <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-white mb-3">
          多源
          <span className="bg-gradient-to-r from-cyan-400 via-sky-300 to-violet-400 bg-clip-text text-transparent">
            网络检索
          </span>
          Agent
        </h1>
        <p className="text-sm text-[#94a3b8] max-w-2xl text-center leading-relaxed font-normal">
          提问后自动调度国内外多个检索源并行采集，去重整理后输出带引用的答案
        </p>
      </div>

      {/* Console */}
      <div className="w-full relative z-10 rounded-2xl bg-[#11131c]/90 border border-white/[0.12] shadow-2xl p-3.5 backdrop-blur-xl transition-all focus-within:border-cyan-500/50 focus-within:shadow-[0_0_30px_-5px_rgba(6,182,212,0.25)]">
        <textarea
          ref={textareaRef}
          value={promptText}
          onChange={(e) => setPromptText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder="输入你想检索的问题… (Enter 发送, Shift+Enter 换行)"
          rows={3}
          className="w-full bg-transparent text-[14px] text-[#f1f5f9] placeholder:text-[#64748b] focus:outline-none resize-none leading-relaxed min-h-[72px]"
        />

        <div className="flex items-center justify-between pt-2.5 pb-2 border-b border-white/[0.06] text-xs">
          <div className="flex items-center gap-2">
            {/* 检索模式 */}
            <div className="relative">
              <button
                onClick={() => setShowModePicker(!showModePicker)}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white/[0.04] border border-white/[0.08] text-[#cbd5e1] hover:bg-white/[0.08] transition-colors cursor-pointer text-[11.5px] font-medium"
              >
                <Globe className="w-3.5 h-3.5 text-cyan-400" />
                <span>{searchMode}</span>
                <ChevronDown className="w-3 h-3 text-[#64748b]" />
              </button>
              {showModePicker && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowModePicker(false)} />
                  <div className="absolute left-0 top-full mt-1.5 w-44 bg-[#131622] border border-white/10 rounded-lg shadow-2xl p-1 z-50 text-xs">
                    {SEARCH_MODES.map((m) => (
                      <button
                        key={m}
                        onClick={() => {
                          onSelectSearchMode(m);
                          setShowModePicker(false);
                        }}
                        className={`w-full text-left px-2.5 py-1.5 rounded flex items-center justify-between cursor-pointer ${
                          searchMode === m
                            ? 'bg-cyan-500/15 text-cyan-300'
                            : 'text-[#cbd5e1] hover:bg-white/[0.05]'
                        }`}
                      >
                        <span>{m}</span>
                        {searchMode === m && <Check className="w-3.5 h-3.5 text-cyan-400" />}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>

            {/* 检索深度 */}
            <div className="relative">
              <button
                onClick={() => setShowDepthPicker(!showDepthPicker)}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white/[0.04] border border-white/[0.08] text-[#cbd5e1] hover:bg-white/[0.08] transition-colors cursor-pointer text-[11.5px] font-medium"
              >
                <Gauge className="w-3.5 h-3.5 text-violet-400" />
                <span>{depth}</span>
                <ChevronDown className="w-3 h-3 text-[#64748b]" />
              </button>
              {showDepthPicker && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowDepthPicker(false)} />
                  <div className="absolute left-0 top-full mt-1.5 w-60 bg-[#131622] border border-white/10 rounded-lg shadow-2xl p-1 z-50 text-xs">
                    {SEARCH_DEPTHS.map((d) => (
                      <button
                        key={d.id}
                        onClick={() => {
                          onSelectDepth(d.id);
                          setShowDepthPicker(false);
                        }}
                        className={`w-full text-left px-2.5 py-1.5 rounded flex flex-col gap-0.5 cursor-pointer ${
                          depth === d.id ? 'bg-cyan-500/15' : 'hover:bg-white/[0.05]'
                        }`}
                      >
                        <span className="flex items-center justify-between">
                          <span className={depth === d.id ? 'text-cyan-300' : 'text-[#cbd5e1]'}>
                            {d.label}
                          </span>
                          {depth === d.id && <Check className="w-3.5 h-3.5 text-cyan-400" />}
                        </span>
                        <span className="text-[10px] text-[#64748b]">{d.desc}</span>
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>

            {/* 模型 */}
            <div className="relative">
              <button
                onClick={() => setShowModelPicker(!showModelPicker)}
                className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-white/[0.04] border border-white/[0.08] hover:bg-white/[0.08] transition-colors cursor-pointer text-[11.5px]"
              >
                <span className="w-4 h-4 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-[8px] font-bold text-white">
                  D
                </span>
                <span className="text-[#cbd5e1] font-medium">{model.name}</span>
                <ChevronDown className="w-3 h-3 text-[#64748b]" />
              </button>
              {showModelPicker && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowModelPicker(false)} />
                  <div className="absolute left-0 top-full mt-1.5 w-60 bg-[#131622] border border-white/10 rounded-lg shadow-2xl p-1 z-50 text-xs">
                    {AVAILABLE_MODELS.map((m) => (
                      <button
                        key={m.id}
                        onClick={() => {
                          onSelectModel(m);
                          setShowModelPicker(false);
                        }}
                        className={`w-full text-left px-2.5 py-2 rounded-md flex items-center justify-between transition-colors cursor-pointer ${
                          model.id === m.id
                            ? 'bg-cyan-500/15 text-cyan-200'
                            : 'text-[#cbd5e1] hover:bg-white/[0.05]'
                        }`}
                      >
                        <div className="flex flex-col">
                          <span className="font-medium text-[12px]">{m.name}</span>
                          <span className="text-[10px] text-[#64748b]">
                            {m.provider} · {m.badge}
                          </span>
                        </div>
                        {model.id === m.id && <Check className="w-3.5 h-3.5 text-cyan-400" />}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={onOpenSources}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11.5px] text-[#94a3b8] hover:text-cyan-300 hover:bg-white/[0.06] transition-colors cursor-pointer"
              title="查看数据源可用状态"
            >
              <Radio className="w-3.5 h-3.5" />
              <span className="font-mono">{available} 源就绪</span>
            </button>

            <button
              onClick={handleSend}
              disabled={!promptText.trim()}
              className={`w-7 h-7 rounded-lg flex items-center justify-center transition-all cursor-pointer ${
                promptText.trim()
                  ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-[0_0_12px_rgba(16,185,129,0.5)]'
                  : 'bg-white/[0.08] text-[#64748b] cursor-not-allowed'
              }`}
            >
              <ArrowUp className="w-4 h-4 stroke-[2.5]" />
            </button>
          </div>
        </div>

        {/* Bottom strip */}
        <div className="flex items-center gap-3 pt-2 text-[11px] text-[#94a3b8]">
          <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
          <span>调度策略</span>
          <span className="text-white/10">·</span>
          <span className="truncate">
            并行采集 · 自动去重 · 来源标注 · 冲突提示
          </span>
        </div>
      </div>

      {/* Examples */}
      <div className="w-full mt-6 relative z-10">
        <div className="flex items-center gap-1.5 mb-2.5 px-1">
          <Layers className="w-3.5 h-3.5 text-[#64748b]" />
          <span className="text-[11px] text-[#64748b]">试试这些问题</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              onClick={() => setPromptText(ex)}
              className="text-left px-3.5 py-2.5 rounded-xl bg-[#11131c]/60 border border-white/[0.08] hover:border-cyan-500/40 hover:bg-[#131722]/80 text-[12.5px] text-[#cbd5e1] hover:text-white transition-all cursor-pointer leading-relaxed"
            >
              {ex}
            </button>
          ))}
        </div>
      </div>

      {/* Source quick strip */}
      {sources.length > 0 && (
        <div className="w-full mt-5 relative z-10 flex flex-wrap items-center gap-1.5 px-1">
          <span className="text-[10.5px] text-[#64748b] mr-1">已接入：</span>
          {sources.map((s) => {
            const style = platformStyle(s.name);
            return (
              <span
                key={s.name}
                title={s.available ? `${s.platform}（可用）` : `${s.platform}：${s.unavailable_reason}`}
                className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] border ${
                  s.available
                    ? `${style.bg} ${style.text}`
                    : 'bg-white/[0.03] border-white/[0.07] text-[#475569]'
                }`}
              >
                {s.available ? (
                  <CheckCircle2 className="w-2.5 h-2.5" />
                ) : (
                  <AlertCircle className="w-2.5 h-2.5" />
                )}
                {style.short}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
};
