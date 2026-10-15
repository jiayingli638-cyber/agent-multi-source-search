import { ModelOption, SearchMode } from '../types';

export const AVAILABLE_MODELS: ModelOption[] = [
  {
    id: 'deepseek-chat',
    name: 'DeepSeek Chat',
    provider: 'DeepSeek',
    badge: '快速',
    iconBg: 'from-blue-600 to-indigo-700',
  },
  {
    id: 'deepseek-reasoner',
    name: 'DeepSeek Reasoner',
    provider: 'DeepSeek',
    badge: '深度推理',
    iconBg: 'from-violet-600 to-purple-700',
  },
];

export const SEARCH_MODES: SearchMode[] = [
  '全部来源',
  '国内优先',
  '国外优先',
  '仅社媒',
  '仅代码',
];

/** 检索深度：影响每源抓取量与并发 */
export type SearchDepth = '快速' | '标准' | '深度';

export const SEARCH_DEPTHS: { id: SearchDepth; label: string; desc: string }[] = [
  { id: '快速', label: '快速', desc: '每源 4 条，最快返回' },
  { id: '标准', label: '标准', desc: '每源 8 条，平衡质量与速度' },
  { id: '深度', label: '深度', desc: '每源 12 条，覆盖更广但更慢' },
];

/** 平台图标配色（按 source/platform 匹配） */
export const PLATFORM_STYLES: Record<string, { bg: string; text: string; short: string }> = {
  bing_cn: { bg: 'bg-sky-500/15 border-sky-500/30', text: 'text-sky-300', short: 'Bing' },
  google_web: { bg: 'bg-blue-500/15 border-blue-500/30', text: 'text-blue-300', short: 'Google' },
  github: { bg: 'bg-slate-400/15 border-slate-400/30', text: 'text-slate-200', short: 'GitHub' },
  nexus: { bg: 'bg-emerald-500/15 border-emerald-500/30', text: 'text-emerald-300', short: 'Nexus' },
  arxiv: { bg: 'bg-red-500/15 border-red-500/30', text: 'text-red-300', short: 'arXiv' },
  web_fetch: { bg: 'bg-teal-500/15 border-teal-500/30', text: 'text-teal-300', short: 'Web' },
  xiaoheihe: { bg: 'bg-amber-500/15 border-amber-500/30', text: 'text-amber-300', short: '小黑盒' },
  boss_zhipin: { bg: 'bg-green-500/15 border-green-500/30', text: 'text-green-300', short: 'BOSS' },
  mediacrawler_xhs: { bg: 'bg-rose-500/15 border-rose-500/30', text: 'text-rose-300', short: '小红书' },
  mediacrawler_dy: { bg: 'bg-pink-500/15 border-pink-500/30', text: 'text-pink-300', short: '抖音' },
  mediacrawler_ks: { bg: 'bg-fuchsia-500/15 border-fuchsia-500/30', text: 'text-fuchsia-300', short: '快手' },
  mediacrawler_bili: { bg: 'bg-cyan-500/15 border-cyan-500/30', text: 'text-cyan-300', short: 'B站' },
  mediacrawler_wb: { bg: 'bg-orange-500/15 border-orange-500/30', text: 'text-orange-300', short: '微博' },
  mediacrawler_tieba: { bg: 'bg-lime-500/15 border-lime-500/30', text: 'text-lime-300', short: '贴吧' },
  mediacrawler_zhihu: { bg: 'bg-indigo-500/15 border-indigo-500/30', text: 'text-indigo-300', short: '知乎' },
  // 兼容旧命名
  mediacrawler_weibo: { bg: 'bg-orange-500/15 border-orange-500/30', text: 'text-orange-300', short: '微博' },
  mediacrawler_douyin: { bg: 'bg-pink-500/15 border-pink-500/30', text: 'text-pink-300', short: '抖音' },
  mediacrawler_bilibili: { bg: 'bg-cyan-500/15 border-cyan-500/30', text: 'text-cyan-300', short: 'B站' },
};

export const KIND_LABELS: Record<string, string> = {
  general_cn: '国内通用',
  general_global: '国外通用',
  social_cn: '国内社媒',
  recruit: '招聘信息',
  code: '开源代码',
  academic: '学术文献',
  web: '网页正文',
};

export function platformStyle(source: string) {
  return (
    PLATFORM_STYLES[source] ?? {
      bg: 'bg-white/[0.06] border-white/15',
      text: 'text-[#cbd5e1]',
      short: '来源',
    }
  );
}
