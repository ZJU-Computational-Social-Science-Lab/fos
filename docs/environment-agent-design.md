# Environment Agent 设计文档

> 本文档为 FOS 环境代理功能的初始设计规范。
> 最后更新：2026-05-25

---

## 1. 概述

### 1.1 目标

为 FOS（Future of Society）多智能体社会仿真平台构建**环境代理（Environmental Agent）**系统，使仿真环境能够：

- 感知自身状态（时间、空间、智能体分布、资源）
- 分析环境趋势并生成可执行的建议
- **注入外部事件**影响智能体行为
- 通过 UI 手动触发或 API 自动驱动

### 1.2 设计原则

- **混合模式**：支持手动触发 + 自动触发 + API 驱动
- **离线友好**：无网络时使用最近缓存数据继续仿真
- **成本优先**：使用免费 API，5-15 分钟可配置轮询间隔
- **可扩展**：模块化设计，支持新增数据源

---

## 2. 系统架构

### 2.1 整体分层

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          FOS SYSTEM                                     │
│                                                                          │
│  ┌──────────────┐      ┌──────────────┐      ┌───────────────┐         │
│  │  Frontend    │      │   Backend    │      │    Core       │         │
│  │  (React)    │◀────▶│  (Litestar)  │◀────▶│  (Simulator)  │         │
│  └──────────────┘      └──────────────┘      └───────────────┘         │
│         │                      │                       │                   │
│         │              ┌───────┴───────┐               │                   │
│         │              ▼               ▼               ▼                   │
│         │      ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│         │      │   Event     │ │   Service    │ │   Environment │        │
│         │      │   Queue      │ │   Layer      │ │   Agent       │        │
│         │      └──────────────┘ └──────────────┘ └──────────────┘        │
│         │              ▲                                               │
│         │              │                                               │
│         │      ┌──────────────┐                                        │
│         │      │   Event      │                                        │
│         └─────▶│   Fetcher    │ ◀── External APIs (政策/市场/新闻)      │
│                │   (Celery)    │                                        │
│                └──────────────┘                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流

```
External APIs (政策/市场/新闻)
         │
         ▼  (每5-15分钟轮询)
┌─────────────────────┐
│   Event Fetcher    │ ──── Celery 后台任务
│  (Background Task)   │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│   Event Queue       │ ──── Redis/内存队列 + 过滤去重
│  (Buffer + Filter)  │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│   Rule Engine       │ ──── 阈值规则匹配 → 自动事件
│  (Auto-trigger)     │
└─────────────────────┘
         │
         ├────────────────────┐
         ▼                    ▼
┌─────────────────┐    ┌─────────────────┐
│  环境代理         │    │   UI 事件面板   │
│  (建议生成)       │    │ (手动注入)       │
└─────────────────┘    └─────────────────┘
         │
         ▼
┌─────────────────────┐
│  Simulation Engine  │
│  (Simulator)        │
└─────────────────────┘
```

---

## 3. 核心组件

### 3.1 EventFetcher (后台任务)

负责轮询外部 API 获取数据。

```python
class EventFetcher:
    """事件抓取器 - 后台任务"""
    
    async def poll_policy(self) -> List[PolicyEvent]:
        """政策数据 - 国家统计局 API / 政府开放数据"""
        pass
    
    async def poll_market(self) -> List[MarketEvent]:
        """市场数据 - Yahoo Finance / 东方财富"""
        pass
    
    async def poll_news(self) -> List[NewsEvent]:
        """新闻舆论 - NewsAPI / RSS 订阅"""
        pass
    
    async def poll_custom(self, config: CustomAPIConfig) -> List[Event]:
        """自定义 API - 用户配置的数据源"""
        pass
```

### 3.2 EventQueue

事件缓冲队列，带过滤去重。

```python
@dataclass
class Event:
    id: str
    type: EventType  # policy, market, news, custom, manual
    source: str
    title: str
    content: str
    timestamp: datetime
    severity: Severity  # low, medium, high, critical
    metadata: Dict[str, Any]

class EventQueue:
    """事件队列"""
    
    def enqueue(self, event: Event) -> None:
        """入队"""
        pass
    
    def dequeue(self) -> Optional[Event]:
        """出队"""
        pass
    
    def get_pending(self) -> List[Event]:
        """获取待处理事件"""
        pass
    
    def deduplicate(self, event: Event) -> bool:
        """去重检查"""
        pass
```

### 3.3 EnvironmentAgent

环境代理核心，分析状态并生成建议。

```python
class EnvironmentAgent:
    """环境代理 - 核心分析组件"""
    
    def __init__(self, clients: Optional[Dict[str, Any]] = None):
        self.clients = clients
    
    def analyze_state(self, context: Dict[str, Any]) -> AnalysisResult:
        """分析当前仿真状态"""
        pass
    
    def generate_suggestions(
        self, 
        context: Dict[str, Any], 
        count: int = 3
    ) -> List[Dict[str, Any]]:
        """生成环境建议"""
        pass
    
    def apply_event(self, event: Event) -> bool:
        """应用外部事件到仿真环境"""
        pass
```

### 3.4 RuleEngine

阈值规则引擎，自动触发事件。

```python
@dataclass
class Rule:
    id: str
    name: str
    condition: RuleCondition  # 条件表达式
    action: EventAction       # 触发的事件
    enabled: bool = True

class RuleEngine:
    """规则引擎 - 自动事件触发"""
    
    def evaluate(self, state: Dict[str, Any]) -> List[Event]:
        """评估规则，返回匹配的事件"""
        pass
    
    def add_rule(self, rule: Rule) -> None:
        pass
    
    def remove_rule(self, rule_id: str) -> None:
        pass
```

---

## 4. 免费 API 方案

### 4.1 政策数据 (Policy)

| 数据源 | 说明 | 限制 |
|--------|------|------|
| 国家统计局 API | stats.gov.cn 免费数据 | 频率限制 |
| 政府开放数据平台 | 各省市开放数据 | 各不相同 |
| RSS 订阅 | 抓取政府网站 RSS | 可能无 RSS |

### 4.2 市场数据 (Market)

| 数据源 | 说明 | 限制 |
|--------|------|------|
| Yahoo Finance (yfinance) | Python 库，免费 | 无 |
| 东方财富 | 需要申请 | 有频率限制 |
| Alpha Vantage | 免费额度 | 5 requests/min |

### 4.3 新闻舆论 (News)

| 数据源 | 说明 | 限制 |
|--------|------|------|
| NewsAPI.org | 免费额度 | 100 requests/day |
| RSS 订阅 | 微博热搜、非实时 | 取决于源 |
| 自定义爬虫 | 需要维护 | 成本较高 |

### 4.4 自定义 API (Custom)

| 配置项 | 说明 |
|--------|------|
| URL | REST API 端点 |
| Method | GET/POST |
| Auth | API Key / Bearer Token / None |
| Headers | 自定义请求头 |
| Mapping | JSON 字段映射 |

---

## 5. 用户界面

### 5.1 事件面板

- 显示外部事件列表（政策、市场、新闻）
- 支持手动触发事件到仿真
- 显示事件来源、时间戳、严重程度

### 5.2 规则配置

- 可视化配置阈值规则
- 启用/禁用规则
- 规则历史记录

### 5.3 环境建议

- 在仿真过程中显示环境代理建议
- 采纳/忽略建议的操作

---

## 6. 视频迁移

### 6.1 LandingPage 视频

**Before:**
```tsx
import landingDemoVideo from "../assets/landing/landing-demo.mp4";

<video 
  src={landingDemoVideo}
  autoPlay muted loop playsInline controls
/>
```

**After (Bilibili 外部播放器):**
```tsx
<iframe
  src="https://player.bilibili.com/player.html?bvid={BV_ID}"
  scrolling="no"
  border="none"
  frameBorder="0"
  allowFullScreen
  style={{ width: '100%', height: '100%' }}
/>
```

### 6.2 配置项

```typescript
// frontend/config/video.ts
export const VIDEO_CONFIG = {
  bilibili: {
    bvId: process.env.VITE_BILIBILI_VIDEO_BVID || '',
    baseUrl: 'https://player.bilibili.com/player.html'
  }
}
```

---

## 7. 实现计划

### Phase 1: MVP (当前阶段)

- [ ] EventQueue 数据结构
- [ ] 基础 EventFetcher (轮询框架)
- [ ] EnvironmentAgent stub (建议生成)
- [ ] LandingPage Bilibili 视频集成

### Phase 2: 核心功能

- [ ] RuleEngine (阈值触发)
- [ ] 前端事件面板 UI
- [ ] 规则配置 UI
- [ ] 免费 API 集成 (Yahoo Finance)

### Phase 3: 完善

- [x] LLM 语义分析增强
- [x] 政策数据 API
- [x] 新闻舆论数据
- [x] 自定义 API 配置

---

## 8. 决策记录

| # | 决策 | 选择 | 理由 |
|---|------|------|------|
| 1 | 外部事件注入方式 | C + D (混合模式 + API 驱动) | 灵活性最高，支持手动和自动 |
| 2 | API 优先级 | 政策 > 市场 > 新闻 > 自定义 | 用户指定 |
| 3 | 技术约束 | 5-15min轮询、缓存离线、免费API | 用户确认 |
| 4 | 设计方案 | 方案 A (事件轮询 + 消息队列) | 简单稳定，MVP 首选 |
| 5 | 视频方案 | Bilibili iframe 嵌入 | 官方播放器 API |
| 6 | API 来源 | 免费 API 优先 | 成本控制 |

---

## 9. 参考资料

- [NeurIPS 2025: Faithful Simulation of User-Agent-Environment Interactions](https://neurons.cc/virtual/2025/124569)
- [AAMAS 2019: Action-Potential/Result (APR) Model](https://www.ifaamas.org/Proceedings/aamas2019/pdfs/p763.pdf)
- [GPLab: LLM-ABM Framework](https://www.jasss.org/29/1/6.html)
- [Discrete Event Social Simulation (DESS) Framework](https://apps.dtic.mil/sti/pdfs/ADA553659.pdf)
