import { SearchMode, SourceInfo, StreamEvent } from '../types';

/** 后端地址：可通过 .env 的 VITE_API_BASE 覆盖 */
export const API_BASE =
  (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_BASE ??
  'http://127.0.0.1:8000';

/** 检索选项，随请求发给后端（后端可在 plan 节点读取） */
export interface QueryOptions {
  mode: SearchMode;
  depth: string;
  model: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`请求失败：HTTP ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

/** 健康检查 */
export async function fetchHealth(): Promise<{
  status: string;
  llm_ready: boolean;
  model: string;
  sources_available: number;
  sources_total: number;
}> {
  return request('/api/health');
}

/** 获取数据源可用状态 */
export async function fetchSources(): Promise<SourceInfo[]> {
  const data = await request<{ sources: SourceInfo[] }>('/api/sources');
  return data.sources ?? [];
}

/**
 * 调用后端 Agent 流式端点。
 * 逐条解析 SSE（data: {...}\n\n），通过 onEvent 回调通知上层。
 * 返回一个可调用的中止函数。
 */
export function streamAgent(
  task: string,
  history: { role: string; content: string }[],
  options: QueryOptions,
  onEvent: (e: StreamEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const body = JSON.stringify({
    task,
    history,
    // 以下字段后端可选消费，便于后续扩展
    mode: options.mode,
    depth: options.depth,
    model: options.model,
  });

  return fetch(`${API_BASE}/api/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
    signal,
  }).then(async (res) => {
    if (!res.ok || !res.body) {
      throw new Error(`后端请求失败：HTTP ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let idx: number;
      while ((idx = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        for (const line of frame.split('\n')) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data:')) continue;
          const payload = trimmed.slice(5).trim();
          if (payload === '[DONE]') return;
          try {
            onEvent(JSON.parse(payload) as StreamEvent);
          } catch {
            // 忽略无法解析的帧（心跳等）
          }
        }
      }
    }
  });
}
