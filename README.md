# FOS — Future of Society

**English** | [中文](#中文版)

---

## English Version

An LLM-based multi-agent social simulation platform for exploring game-theoretic and social dynamics.

### Project Structure

```
fos/
├── frontend/          # React + TypeScript frontend
├── src/fos/           # Python backend
│   ├── backend/       # Litestar web API, services, database
│   ├── core/          # Simulation engine
│   │   ├── experiment/   # Experiment runner & agents
│   │   ├── scenes/       # Game-theory scenes
│   │   ├── contagion/    # SEIR contagion model
│   │   ├── llm/          # LLM client layer
│   │   ├── map/          # Grid world maps
│   │   └── scenarios/    # Preset scenario configs
│   ├── locales/       # i18n translations
│   └── templates/     # Report templates
├── tests/             # Test suite (pytest)
└── docs/              # Documentation
```

### Quick Start

#### 1. Environment Setup

```bash
# Create virtual environment (Python 3.12 recommended)
python -m venv venv

# Activate (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Install backend dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend && npm install && cd ..
```

#### 2. Configure Environment Variables

Copy `.env.example` to `.env` and modify as needed:

```bash
cp .env.example .env
```

Key configuration options:
- `FOS_DATABASE_URL`: Database connection (default: SQLite)
- `FOS_JWT_SIGNING_KEY`: JWT signing key
- `FOS_REQUIRE_EMAIL_VERIFICATION`: Email verification required (set to `false` for development)

#### 3. Start Services

**Start Backend** (port 8000):

```bash
# Activate venv and set Python path
.\venv\Scripts\Activate.ps1       # Windows PowerShell
$env:PYTHONPATH = "."
uvicorn fos.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Linux / macOS:**
```bash
source venv/bin/activate
export PYTHONPATH="."
uvicorn fos.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Start Frontend** (port 5173):
```bash
cd frontend
npm run dev
```

#### 4. Access

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000/api
- API Documentation: http://localhost:8000/schema/swagger

### Usage

1. Register an account and log in
2. Go to "Settings → LLM Providers" to add your API Key
3. Click "New Simulation" to create a simulation
4. Advance turns, create branches, and view agent logs

### Tech Stack

- **Backend**: Python 3.12, Litestar, SQLAlchemy, Pydantic
- **Frontend**: React 19, TypeScript, Vite, Zustand, TailwindCSS
- **Database**: SQLite (development) / PostgreSQL (production)

### Development

See [AGENTS.md](./AGENTS.md) for project architecture and coding conventions.

---

## 中文版

[English](#english-version) | **中文**

基于 LLM 的多智能体社会仿真平台，用于探索博弈论与社会动态。

### 项目结构

```
fos/
├── frontend/          # React + TypeScript 前端
├── src/fos/           # Python 后端
│   ├── backend/       # Litestar Web API、服务层、数据库
│   ├── core/          # 仿真引擎
│   │   ├── experiment/   # 实验运行器与智能体
│   │   ├── scenes/       # 博弈论场景
│   │   ├── contagion/    # SEIR 传染模型
│   │   ├── llm/          # LLM 客户端层
│   │   ├── map/          # 网格地图
│   │   └── scenarios/    # 预设场景配置
│   ├── locales/       # 国际化翻译
│   └── templates/     # 报告模板
├── tests/             # 测试套件 (pytest)
└── docs/              # 文档
```

### 快速启动

#### 1. 环境准备

```bash
# 创建虚拟环境（推荐 Python 3.12）
python -m venv venv

# 激活（Windows PowerShell）
.\venv\Scripts\Activate.ps1

# 安装后端依赖
pip install -r requirements.txt

# 安装前端依赖
cd frontend && npm install && cd ..
```

#### 2. 配置环境变量

复制 `.env.example` 为 `.env`，按需修改：

```bash
cp .env.example .env
```

主要配置项：
- `FOS_DATABASE_URL`: 数据库连接（默认 SQLite）
- `FOS_JWT_SIGNING_KEY`: JWT 签名密钥
- `FOS_REQUIRE_EMAIL_VERIFICATION`: 是否需要邮箱验证（开发时设为 `false`）

#### 3. 启动服务

**启动后端**（端口 8000）：

```bash
# 激活虚拟环境并设置 Python 路径
.\venv\Scripts\Activate.ps1       # Windows PowerShell
$env:PYTHONPATH = "."
uvicorn fos.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Linux / macOS：**
```bash
source venv/bin/activate
export PYTHONPATH="."
uvicorn fos.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**启动前端**（端口 5173）：
```bash
cd frontend
npm run dev
```

#### 4. 访问

- 前端: http://localhost:5173
- 后端 API: http://localhost:8000/api
- API 文档: http://localhost:8000/schema/swagger

### 使用流程

1. 注册账号并登录
2. 在「设置 → LLM 提供商」中添加 API Key
3. 点击「新建模拟」创建仿真
4. 推进回合、创建分支、查看智能体日志

### 技术栈

- **后端**: Python 3.12, Litestar, SQLAlchemy, Pydantic
- **前端**: React 19, TypeScript, Vite, Zustand, TailwindCSS
- **数据库**: SQLite (开发) / PostgreSQL (生产)

### 开发说明

详见 [AGENTS.md](./AGENTS.md) 了解项目架构和编码规范。
