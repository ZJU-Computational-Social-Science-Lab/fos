/**
 * Pre-built data source templates for common external APIs.
 * Users can select a template to auto-fill configuration.
 */

export interface DataSourceTemplate {
  id: string;
  name: string;
  description: string;
  icon: string;
  category: 'market' | 'news' | 'social' | 'crypto' | 'custom';
  /** Default values to populate the form */
  defaults: {
    name: string;
    api_url: string;
    auth_type: 'none' | 'bearer' | 'api_key';
    auth_token?: string;
    poll_interval_seconds: number;
    event_type: 'market' | 'policy' | 'news' | 'custom';
    field_mapping: {
      title_path: string;
      content_path: string;
      timestamp_path: string;
      url_path: string;
      items_path?: string;
    };
  };
  /** Hint shown to user after template is selected */
  hint?: string;
}

export const DATA_SOURCE_TEMPLATES: DataSourceTemplate[] = [
  // ── Market / Finance ──────────────────────────────────────────────
  {
    id: 'yahoo-finance',
    name: 'Yahoo Finance',
    description: 'Real-time stock quotes and market news',
    icon: '📈',
    category: 'market',
    defaults: {
      name: 'Yahoo Finance Market',
      api_url: 'https://query1.finance.yahoo.com/v1/finance/search?q=USDT&quotesQueryId=news',
      auth_type: 'none',
      poll_interval_seconds: 300,
      event_type: 'market',
      field_mapping: {
        items_path: 'quotes',
        title_path: 'shortName',
        content_path: 'longname',
        timestamp_path: 'quoteType',
        url_path: 'quoteType',
      },
    },
    hint: 'No auth required. Returns stock quotes — adjust items_path based on your query.',
  },

  {
    id: 'alphavantage',
    name: 'Alpha Vantage',
    description: 'Stock API with free tier (5 req/min)',
    icon: '📊',
    category: 'market',
    defaults: {
      name: 'Alpha Vantage',
      api_url: 'https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=IBM&apikey=DEMO',
      auth_type: 'api_key',
      auth_token: '', // user fills in their key
      poll_interval_seconds: 300,
      event_type: 'market',
      field_mapping: {
        items_path: '',
        title_path: '01. symbol',
        content_path: '01. symbol',
        timestamp_path: '07. latest trading day',
        url_path: '',
      },
    },
    hint: 'Get free API key at alphavantage.co. "DEMO" key has limited functionality.',
  },

  {
    id: 'coingecko',
    name: 'CoinGecko',
    description: 'Cryptocurrency prices and market data (free, no auth)',
    icon: '🪙',
    category: 'crypto',
    defaults: {
      name: 'CoinGecko Crypto',
      api_url: 'https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=volume_desc',
      auth_type: 'none',
      poll_interval_seconds: 120,
      event_type: 'market',
      field_mapping: {
        items_path: '',
        title_path: 'name',
        content_path: 'current_price',
        timestamp_path: 'last_updated',
        url_path: 'symbol',
      },
    },
    hint: 'No auth required. Rate limit: 10-30 calls/min. Use for crypto price events.',
  },

  // ── News ──────────────────────────────────────────────────────────
  {
    id: 'newsapi',
    name: 'NewsAPI',
    description: 'World news from thousands of sources',
    icon: '📰',
    category: 'news',
    defaults: {
      name: 'NewsAPI Headlines',
      api_url: 'https://newsapi.org/v2/top-headlines?country=us&category=business&apiKey=DEMO_KEY',
      auth_type: 'api_key',
      auth_token: '', // user fills in their key
      poll_interval_seconds: 600,
      event_type: 'news',
      field_mapping: {
        items_path: 'articles',
        title_path: 'title',
        content_path: 'description',
        timestamp_path: 'publishedAt',
        url_path: 'url',
      },
    },
    hint: 'Get free API key at newsapi.org. "DEMO" key returns headlines from The Guardian only.',
  },

  {
    id: 'hackernews',
    name: 'Hacker News',
    description: 'Tech news and startup discussions (free, no auth)',
    icon: '💻',
    category: 'news',
    defaults: {
      name: 'Hacker News Top',
      api_url: 'https://hacker-news.firebaseio.com/v0/topstories.json',
      auth_type: 'none',
      poll_interval_seconds: 300,
      event_type: 'news',
      field_mapping: {
        items_path: '',
        title_path: 'title',
        content_path: 'score',
        timestamp_path: 'time',
        url_path: 'url',
      },
    },
    hint: 'This returns story IDs. For full stories, use: https://hacker-news.firebaseio.com/v0/item/{id}.json',
  },

  // ── Social ─────────────────────────────────────────────────────────
  {
    id: 'reddit',
    name: 'Reddit',
    description: 'Social media posts and discussions (no auth for public)',
    icon: '💬',
    category: 'social',
    defaults: {
      name: 'Reddit r/worldnews',
      api_url: 'https://www.reddit.com/r/worldnews/hot.json?limit=10',
      auth_type: 'none',
      poll_interval_seconds: 600,
      event_type: 'news',
      field_mapping: {
        items_path: 'data.children',
        title_path: 'data.title',
        content_path: 'data.selftext',
        timestamp_path: 'data.created_utc',
        url_path: 'data.url',
      },
    },
    hint: 'Public endpoint (no auth). Rate limit ~60 req/min. Best for social sentiment.',
  },

  // ── Policy ─────────────────────────────────────────────────────────
  {
    id: 'gov.cn',
    name: '中国政府网',
    description: 'Official government announcements and policies',
    icon: '🏛️',
    category: 'policy',
    defaults: {
      name: '中国政府网公告',
      api_url: 'http://www.gov.cn/fore_1/api/news/list?page=1&pageSize=10',
      auth_type: 'none',
      poll_interval_seconds: 900,
      event_type: 'policy',
      field_mapping: {
        items_path: 'data',
        title_path: 'title',
        content_path: 'description',
        timestamp_path: 'pubDate',
        url_path: 'url',
      },
    },
    hint: 'No auth required. Adjust items_path based on actual API response structure.',
  },

  // ── Webhook (manual push) ──────────────────────────────────────────
  {
    id: 'webhook-generic',
    name: 'Webhook (自定义)',
    description: 'Receive events via POST — configure your own source',
    icon: '🔗',
    category: 'custom',
    defaults: {
      name: 'Webhook 数据源',
      api_url: 'https://your-server.com/events/api',
      auth_type: 'bearer',
      auth_token: 'your-webhook-secret-token',
      poll_interval_seconds: 0, // 0 = manual-only, no auto-poll
      event_type: 'custom',
      field_mapping: {
        title_path: 'title',
        content_path: 'content',
        timestamp_path: 'timestamp',
        url_path: 'url',
      },
    },
    hint: 'Set poll_interval_seconds=0 to disable auto-polling. Use POST /api/events/external to push events manually.',
  },
];

/** Categories for grouping templates in the UI */
export const TEMPLATE_CATEGORIES = [
  { id: 'market', label: '市场/金融', labelEn: 'Market / Finance' },
  { id: 'news', label: '新闻', labelEn: 'News' },
  { id: 'social', label: '社交', labelEn: 'Social' },
  { id: 'crypto', label: '加密货币', labelEn: 'Crypto' },
  { id: 'policy', label: '政策/政府', labelEn: 'Policy / Government' },
  { id: 'custom', label: '自定义', labelEn: 'Custom' },
] as const;