# Quick Start Guide

This is the hands-on checklist. For background and architecture, see `README.md`.

---

## Prerequisites
- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (or another installer)
- Rust toolchain via `rustup`
- Access to a LiteLLM compatible endpoint

## Install & Verify

```bash
git clone https://github.com/athalang/defacc.git
cd defacc

# Recommended: uv handles the venv automatically
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync

# Or: standard virtualenv + pip
python -m venv .venv
source .venv/bin/activate
pip install -e .

rustc --version
```

## Configure the LLM

```bash
cp .env.example .env
```

Edit `.env` and set at least:
```
MODEL=anthropic/claude-3-5-sonnet-20241022   # swap for GPT-4, Ollama, vLLM, etc.
API_KEY=...
TEMPERATURE=0.7
```

### Common presets

**Local Model**
```bash
MODEL=ollama/qwen3-coder
TEMPERATURE=0.7
API_BASE=http://localhost:11434
```

**Hosted vLLM**
```bash
MODEL=hosted_vllm/Qwen/Qwen3-Coder-30B-A3B-Instruct
TEMPERATURE=0.7
API_BASE=your-api-base-here
API_KEY=PLACEHOLDER
```

**Anthropic**
```bash
MODEL=anthropic/claude-3-5-sonnet-20241022
TEMPERATURE=0.7
API_KEY=sk-ant-your-key
```

**OpenAI GPT-4**
```bash
MODEL=openai/gpt-4
TEMPERATURE=0.7
API_KEY=sk-openai-your-key
```

## Run the Pipeline

```bash
# Default demonstration
python main.py

# Specific regression from the built-in suite
python main.py --test buffer_overflow

# Whole suite (27 functions, mixes benign + adversarial)
python main.py --all
```

### Translate a real project

```bash
# Produce compile_commands.json (CMake example)
cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -S . -B build
cmake --build build

# or Bear + Make (see utf8/ for a sample)
cd utf8 && bear -- make clean all && cd ..

python main.py \
  --compile-commands path/to/compile_commands.json \
  --output-rust translated.rs
```

## Optional Checks

```bash
# Inspect AI evals (see README for details)
inspect eval guardian/evals/c_to_rust.py@all_tests
inspect eval guardian/evals/c_to_rust.py@adversarial_tests

# Baseline comparison scripts
./scripts/run_baseline_comparison.sh
python scripts/generate_comparison_report.py
```

## Use It From Python

```python
import dspy
from guardian.pipeline import GUARDIANPipeline

lm = dspy.LM(model="anthropic/claude-3-5-sonnet-20241022", api_key="...")
dspy.configure(lm=lm)

pipeline = GUARDIANPipeline(lm=lm)
c_code = """
int main() {
    char buffer[10];
    strcpy(buffer, very_long_string);
    return 0;
}
"""

result = pipeline.translate(c_code, verbose=True)
print(result.rust_code)
print(f"Compiled: {result.compilation.success}")
print(f"Iterations: {result.compilation.iterations}")
```

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `ModuleNotFoundError: dspy` | Activate the venv (`source .venv/bin/activate`) or rerun `uv sync`. |
| `rustc not found` | Install via `curl ... sh` (see above) and `source $HOME/.cargo/env`. |
| Missing `.env` | `cp .env.example .env` and add your credentials. |
| No corpus file | Run from repo root; `guardian/corpus/examples.json` ships in-tree. |
