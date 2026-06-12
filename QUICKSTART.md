# FOS Platform — Quick Start

## Backend Setup

### Step 1: Navigate to project directory
```cmd
cd C:\Users\Justin\Documents\ZJU_Work\fos
```

### Step 2: Activate conda environment
```cmd
conda activate fos
```
*(If fos doesn't exist, create it first: `conda create -n fos python=3.12 -y`)*

### Step 3: Set PYTHONPATH
```cmd
set PYTHONPATH=%cd%\src
```

### Step 4: Start backend server
```cmd
uvicorn fos.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Frontend Setup

### Open a NEW terminal/cmd window, then:

### Step 1: Navigate to frontend directory
```cmd
cd C:\Users\Justin\Documents\ZJU_Work\fos\frontend
```

### Step 2: Start frontend dev server
```cmd
npm run dev
```

---

## Access The Platform

Once both servers are running:

| Service | URL |
|---------|-----|
| **Frontend** | http://localhost:5173 |
| **Backend API** | http://localhost:8000/api |
| **API Docs** | http://localhost:8000/schema/swagger |

---

## Adding Ollama Model

### Step 1: Make sure Ollama is running
```cmd
ollama serve
```

### Step 2: Go to the frontend
Open http://localhost:5173 in your browser

### Step 3: Navigate to Settings → LLM Providers
Click "Add Provider" and fill in:

| Field | Value |
|-------|-------|
| **Label** | `Ollama` |
| **Provider** | `OpenAI-compatible` |
| **Model** | `qwen3:4b` |
| **Base URL** | `http://localhost:11434/v1` |
| **API Key** | `dummy` (Ollama doesn't need API key — any value works) |

### Step 4: Save
Click "Save" to add the provider

### Available Ollama Models
To list your installed models:
```cmd
ollama list
```

### Common Ollama Models
- `qwen2.5:7b` — Good general purpose
- `llama3:8b` — Meta's Llama 3
- `mistral:7b` — Fast and efficient
- `codellama:7b` — Code generation
- `phi3` — Microsoft's 3.8B parameter model

---

## Troubleshooting

### Backend won't start?
```cmd
# Install dependencies if missing
pip install -r requirements-test.txt

# Or update pip
python -m pip install --upgrade pip
```

### Frontend won't start?
```cmd
# Install dependencies
npm install
```

### PYTHONPATH issues?
The `set PYTHONPATH=%cd%\src` command tells Python where to find the `fos` package. It must be run from the `fos` directory.

---

## Stopping The Servers

**Backend:** Press `Ctrl+C` in the backend terminal

**Frontend:** Press `Ctrl+C` in the frontend terminal
