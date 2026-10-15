import React, { useState, useEffect, useRef, useCallback } from 'react';
import { TitleBar } from './components/TitleBar';
import { Sidebar } from './components/Sidebar';
import { PromptConsole } from './components/PromptConsole';
import { ActiveSessionView } from './components/ActiveSessionView';
import { SearchModal } from './components/SearchModal';
import { SourcePanel } from './components/SourcePanel';
import {
  ChatMessage,
  ModelOption,
  SearchMode,
  Session,
  SourceInfo,
  StreamEvent,
  ToolLog,
} from './types';
import { AVAILABLE_MODELS } from './data/mockData';
import { fetchSources, streamAgent } from './api/client';

export default function App() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [searchOpen, setSearchOpen] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [sources, setSources] = useState<SourceInfo[]>([]);
  const [model, setModel] = useState<ModelOption>(AVAILABLE_MODELS[0]);
  const [searchMode, setSearchMode] = useState<SearchMode>('全部来源');
  const [depth, setDepth] = useState('标准');
  const abortRef = useRef<AbortController | null>(null);

  const activeSession = sessions.find((s) => s.id === activeSessionId);

  // 启动时拉取数据源状态
  useEffect(() => {
    fetchSources()
      .then(setSources)
      .catch(() => setSources([]));
  }, []);

  const handleNewChat = useCallback(() => {
    abortRef.current?.abort();
    setActiveSessionId(null);
  }, []);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const isCmd = e.metaKey || e.ctrlKey;
      if (isCmd && e.key.toLowerCase() === 'b') {
        e.preventDefault();
        setSidebarOpen((v) => !v);
      } else if (isCmd && e.key.toLowerCase() === 'p') {
        e.preventDefault();
        setSearchOpen((v) => !v);
      } else if (isCmd && e.key.toLowerCase() === 'n') {
        e.preventDefault();
        handleNewChat();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [handleNewChat]);

  /** 更新指定助手消息的字段 */
  const patchMessage = useCallback(
    (sessionId: string, messageId: string, patch: Partial<ChatMessage>) => {
      setSessions((prev) =>
        prev.map((s) =>
          s.id === sessionId
            ? {
                ...s,
                messages: s.messages.map((m) => (m.id === messageId ? { ...m, ...patch } : m)),
              }
            : s
        )
      );
    },
    []
  );

  /** 统一执行一次检索，处理 SSE 事件 */
  const runSearch = useCallback(
    async (
      sessionId: string,
      messageId: string,
      task: string,
      history: { role: string; content: string }[],
      options: { mode: SearchMode; depth: string; model: string }
    ) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      const logs: ToolLog[] = [];
      let seq = 0;

      const onEvent = (e: StreamEvent) => {
        if (e.type === 'tool') {
          seq += 1;
          logs.push({
            id: `${messageId}-log-${seq}`,
            name: e.name,
            label: e.name,
            ok: e.ok,
            result: e.result,
            arguments: e.arguments,
            at: Date.now(),
          });
          patchMessage(sessionId, messageId, { toolLogs: [...logs] });
        } else if (e.type === 'final') {
          patchMessage(sessionId, messageId, {
            content: e.content,
            citations: e.citations ?? [],
            stats: e.stats,
            subQueries: e.sub_queries ?? [],
            plan: e.plan ?? [],
            degraded: e.degraded ?? false,
            notes: e.notes ?? [],
            status: 'complete',
          });
        } else if (e.type === 'error') {
          patchMessage(sessionId, messageId, { content: e.message, status: 'error' });
        }
      };

      try {
        await streamAgent(task, history, options, onEvent, controller.signal);
        // 若流结束仍处于 generating，兜底置为 complete
        setSessions((prev) =>
          prev.map((s) =>
            s.id === sessionId
              ? {
                  ...s,
                  messages: s.messages.map((m) =>
                    m.id === messageId && m.status === 'generating'
                      ? { ...m, status: 'complete' as const }
                      : m
                  ),
                }
              : s
          )
        );
      } catch (err) {
        if ((err as Error).name === 'AbortError') return;
        patchMessage(sessionId, messageId, {
          content: `调用后端失败：${err instanceof Error ? err.message : String(err)}\n\n请确认后端已启动：\n在 backend 目录执行  python -m uvicorn app.main:app --port 8000`,
          status: 'error',
        });
      }
    },
    [patchMessage]
  );

  const handleSubmitPrompt = useCallback(
    async (prompt: string, selectedModel: ModelOption, mode: SearchMode, selectedDepth: string) => {
      const sessionId = `sess-${Date.now()}`;
      const aiId = `msg-${Date.now()}-ai`;
      const nowTime = new Date().toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit',
      });

      setSessions((prev) => [
        {
          id: sessionId,
          title: prompt.length > 24 ? `${prompt.slice(0, 24)}…` : prompt,
          createdAt: '刚刚',
          project: 'retrieval-agent',
          messages: [
            { id: `msg-${Date.now()}-user`, sender: 'user', timestamp: nowTime, content: prompt },
            {
              id: aiId,
              sender: 'assistant',
              timestamp: nowTime,
              content: '正在调度多源检索…',
              status: 'generating',
              toolLogs: [],
            },
          ],
        },
        ...prev,
      ]);
      setActiveSessionId(sessionId);

      await runSearch(sessionId, aiId, prompt, [], {
        mode,
        depth: selectedDepth,
        model: selectedModel.id,
      });
    },
    [runSearch]
  );

  const handleSendMessage = useCallback(
    async (sessionId: string, message: string) => {
      const nowTime = new Date().toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit',
      });
      const aiId = `ai-${Date.now()}`;

      const history: { role: string; content: string }[] = [];
      const current = sessions.find((s) => s.id === sessionId);
      for (const m of current?.messages ?? []) {
        if (m.status === 'generating') continue;
        history.push({ role: m.sender, content: m.content });
      }
      history.push({ role: 'user', content: message });

      setSessions((prev) =>
        prev.map((s) =>
          s.id === sessionId
            ? {
                ...s,
                messages: [
                  ...s.messages,
                  {
                    id: `user-${Date.now()}`,
                    sender: 'user' as const,
                    timestamp: nowTime,
                    content: message,
                  },
                  {
                    id: aiId,
                    sender: 'assistant' as const,
                    timestamp: nowTime,
                    content: '正在调度多源检索…',
                    status: 'generating' as const,
                    toolLogs: [],
                  },
                ],
              }
            : s
        )
      );

      await runSearch(
        sessionId,
        aiId,
        message,
        history.slice(0, -1),
        { mode: searchMode, depth, model: model.id }
      );
    },
    [sessions, runSearch, searchMode, depth, model]
  );

  const availableCount = sources.filter((s) => s.available).length;

  return (
    <div className="flex flex-col h-screen w-screen bg-[#090a10] text-[#e2e8f0] overflow-hidden select-none font-sans">
      <TitleBar
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        onOpenSearch={() => setSearchOpen(true)}
        onToggleSources={() => setSourcesOpen(!sourcesOpen)}
        sourcesOpen={sourcesOpen}
        availableCount={availableCount}
        totalCount={sources.length}
      />

      <div className="flex-1 flex overflow-hidden relative">
        {sidebarOpen && (
          <Sidebar
            onNewChat={handleNewChat}
            sessions={sessions}
            activeSessionId={activeSessionId}
            onSelectSession={setActiveSessionId}
            model={model}
            onSelectModel={setModel}
            searchMode={searchMode}
            onSelectSearchMode={setSearchMode}
            depth={depth}
            onSelectDepth={setDepth}
          />
        )}

        <main className="flex-1 flex flex-col h-full bg-[#0a0c14] overflow-hidden relative">
          {activeSession ? (
            <ActiveSessionView
              session={activeSession}
              onBackToHome={() => setActiveSessionId(null)}
              onSendMessage={handleSendMessage}
            />
          ) : (
            <PromptConsole
              onSubmitPrompt={handleSubmitPrompt}
              model={model}
              onSelectModel={setModel}
              searchMode={searchMode}
              onSelectSearchMode={setSearchMode}
              depth={depth}
              onSelectDepth={setDepth}
              sources={sources}
              onOpenSources={() => setSourcesOpen(true)}
            />
          )}
        </main>

        <SourcePanel
          isOpen={sourcesOpen}
          onClose={() => setSourcesOpen(false)}
          sources={sources}
        />
      </div>

      <SearchModal
        isOpen={searchOpen}
        onClose={() => setSearchOpen(false)}
        sessions={sessions}
        onSelectSession={setActiveSessionId}
        onNewChat={handleNewChat}
      />
    </div>
  );
}
