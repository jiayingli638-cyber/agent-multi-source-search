export type ModelId = 'deepseek-chat' | 'deepseek-reasoner';

export interface ModelOption {
  id: ModelId;
  name: string;
  provider: string;
  badge?: string;
  iconBg: string;
}

/** 检索模式：影响调度哪些源 */
export type SearchMode = '全部来源' | '国内优先' | '国外优先' | '仅社媒' | '仅代码';

/** 数据源可用状态（来自 GET /api/sources） */
export interface SourceInfo {
  name: string;
  platform: string;
  kind: string;
  available: boolean;
  requires_credentials: boolean;
  description: string;
  unavailable_reason: string;
}

/** 归一化检索结果（后端 Doc） */
export interface Citation {
  id: string;
  title: string;
  url: string;
  snippet: string;
  content?: string;
  source: string;
  source_kind: string;
  platform: string;
  author: string;
  published_at: string;
  score: number;
  engine_rank: number;
  extras: Record<string, unknown>;
}

export interface SearchStats {
  total_fetched: number;
  after_dedup: number;
  per_source: Record<string, number>;
  errors: Record<string, string>;
  elapsed_ms: number;
}

export interface SourcePlan {
  source: string;
  kind: string;
  query: string;
  reason: string;
  required: boolean;
}

export interface ToolLog {
  id: string;
  name: string;
  label: string;
  ok: boolean;
  result: string;
  arguments?: Record<string, unknown>;
  at: number;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  timestamp: string;
  content: string;
  /** 检索过程日志（工具执行流） */
  toolLogs?: ToolLog[];
  /** 引用来源 */
  citations?: Citation[];
  /** 检索统计 */
  stats?: SearchStats;
  /** 拆解出的子查询 */
  subQueries?: string[];
  /** 调度计划 */
  plan?: SourcePlan[];
  /** 是否降级（部分源无凭证 / 模型不可用） */
  degraded?: boolean;
  /** 提示信息 */
  notes?: string[];
  status?: 'complete' | 'generating' | 'error';
}

export interface Session {
  id: string;
  title: string;
  createdAt: string;
  project: string;
  messages: ChatMessage[];
  hasWarning?: boolean;
}

/** SSE 事件（与后端 app/graph/agent.py 对齐） */
export type StreamEvent =
  | { type: 'start'; task: string }
  | {
      type: 'tool';
      name: string;
      ok: boolean;
      result: string;
      arguments?: Record<string, unknown>;
    }
  | {
      type: 'final';
      content: string;
      citations?: Citation[];
      stats?: SearchStats;
      sub_queries?: string[];
      plan?: SourcePlan[];
      degraded?: boolean;
      notes?: string[];
    }
  | { type: 'error'; message: string };
