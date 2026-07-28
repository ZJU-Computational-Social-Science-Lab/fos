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
# Required local versions: Python 3.12 and Node.js 22.
# The beta development baseline is the `beta` branch.

# Create virtual environment
python3.12 -m venv .venv

# Activate (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Activate (Linux / macOS)
source .venv/bin/activate

# Upgrade packaging tools
python -m pip install --upgrade pip

# Install backend dependencies
pip install -r requirements-test.txt
pip install -e .

# Install frontend dependencies
cd frontend && npm ci && cd ..
```

Routine CI and local deterministic checks use the same baseline commands:

```bash
PYTHONPATH=src python -m pytest tests/ -q --no-header \
  --cov=fos.core \
  --cov-fail-under=58 \
  --ignore=tests/llm_prompt_testing \
  --ignore=tests/smoke_tests \
  --ignore=tests/integration/test_real_llm_phase1.py \
  --ignore=tests/integration/test_llm_action_selection.py \
  --ignore=tests/load

cd frontend
npm run test:run
npm run build
npm run test:e2e:smoke
cd ..

node --test tests/load/lib/loadUsers.test.mjs
```

Run every automated local suite with `python scripts/run_full_tests.py`. The complete
Playwright run can require an active local model/provider setup that routine CI does not provision.

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
.\.venv\Scripts\Activate.ps1       # Windows PowerShell
$env:PYTHONPATH = "src"
uvicorn fos.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Linux / macOS:**
```bash
source .venv/bin/activate
export PYTHONPATH="src"
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
- **Frontend**: Node.js 22, React 19, TypeScript, Vite, Zustand, TailwindCSS
- **Database**: SQLite (development) / PostgreSQL (production)

### Development

See [AGENTS.md](./AGENTS.md) for project architecture and coding conventions.

Beta handoff documents:

- [Quick Start](./QUICKSTART.md): shared setup and command baseline.
- [Frontend README](./frontend/README.md): FOS-specific frontend development guide.
- [Beta demo script](./docs/beta-demo.md): fixed demo path from login through export.
- [Beta acceptance criteria](./docs/beta-acceptance.md): phase-level completion checklist.

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
# 本地统一版本：Python 3.12 和 Node.js 22。
# Beta 开发统一基线为 `beta` 分支。

# 创建虚拟环境
python3.12 -m venv .venv

# 激活（Windows PowerShell）
.\.venv\Scripts\Activate.ps1

# 激活（Linux / macOS）
source .venv/bin/activate

# 升级打包工具
python -m pip install --upgrade pip

# 安装后端依赖
pip install -r requirements-test.txt
pip install -e .

# 安装前端依赖
cd frontend && npm ci && cd ..
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
.\.venv\Scripts\Activate.ps1       # Windows PowerShell
$env:PYTHONPATH = "src"
uvicorn fos.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Linux / macOS：**
```bash
source .venv/bin/activate
export PYTHONPATH="src"
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

#### 5. 标准测试命令

本地确定性检查与 CI 保持一致：

```bash
PYTHONPATH=src python -m pytest tests/ -q --no-header \
  --cov=fos.core \
  --cov-fail-under=58 \
  --ignore=tests/llm_prompt_testing \
  --ignore=tests/smoke_tests \
  --ignore=tests/integration/test_real_llm_phase1.py \
  --ignore=tests/integration/test_llm_action_selection.py \
  --ignore=tests/load

cd frontend
npm run test:run
npm run build
npm run test:e2e:smoke
cd ..

node --test tests/load/lib/loadUsers.test.mjs
```

完整本地测试可运行 `python scripts/run_full_tests.py`。完整 Playwright 测试可能需要本地模型或 provider 配置，常规 CI 不提供这些外部依赖。

### 使用流程

1. 注册账号并登录
2. 在「设置 → LLM 提供商」中添加 API Key
3. 点击「新建模拟」创建仿真
4. 推进回合、创建分支、查看智能体日志

### 技术栈

- **后端**: Python 3.12, Litestar, SQLAlchemy, Pydantic
- **前端**: Node.js 22, React 19, TypeScript, Vite, Zustand, TailwindCSS
- **数据库**: SQLite (开发) / PostgreSQL (生产)

### 开发说明

详见 [AGENTS.md](./AGENTS.md) 了解项目架构和编码规范。

Beta 交付文档：

- [Quick Start](./QUICKSTART.md)：统一环境与命令基线。
- [Frontend README](./frontend/README.md)：FOS 前端开发说明。
- [Beta demo script](./docs/beta-demo.md)：从登录到导出的固定演示路径。
- [Beta acceptance criteria](./docs/beta-acceptance.md)：阶段验收清单。
