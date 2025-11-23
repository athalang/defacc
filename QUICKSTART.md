# GUARDIAN Quick Start Guide

Get started with GUARDIAN in 5 minutes!

## Prerequisites

1. Python 3.8+
2. [uv](https://docs.astral.sh/uv/) - Fast Python package manager
3. Rust (optional, for compilation validation)
4. LLM access (Anthropic, OpenAI, or local via Ollama/vLLM)

## Installation

```bash
# 1. Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Sync dependencies (creates venv and installs packages)
uv sync

# 3. Activate the virtual environment
source .venv/bin/activate

# 4. Verify installation
python -c "import dspy; print('DSPy installed')"
python -c "import pydantic_settings; print('Pydantic installed')"
python -c "import rank_bm25; print('BM25 installed')"

# 5. Check Rust (optional)
rustc --version
```

## Configure Your LLM

```bash
# 1. Copy the example config
cp .env.example .env

# 2. Edit .env with your settings
# Choose one configuration:
```

**Option 1: Anthropic Claude (recommended)**
```bash
MODEL=anthropic/claude-3-5-sonnet-20241022
TEMPERATURE=0.7
API_KEY=sk-ant-your-key-here
```

**Option 2: OpenAI GPT-4**
```bash
MODEL=openai/gpt-4
TEMPERATURE=0.7
API_KEY=sk-your-key-here
```

**Option 3: Local Model (Ollama)**
```bash
MODEL=ollama/mistral
TEMPERATURE=0.7
API_BASE=http://localhost:11434
```

**Option 4: Self-hosted vLLM**
```bash
MODEL=hosted_vllm/Qwen/Qwen3-Coder-30B-A3B-Instruct
TEMPERATURE=0.7
API_BASE=http://127.0.0.1:8000/v1
API_KEY=PLACEHOLDER
```

## Run Your First Translation

```bash
# From the project root directory
python main.py
```

You should see:

```
GUARDIAN C-to-Rust Translation Pipeline
====================================

Step 1: Analyzing C code patterns...
  Detected categories: ['I/O']
  Found 2 rule hints

Step 2: Retrieving similar examples...
  Retrieved 3 relevant examples

Step 3: Summarizing C code structure...
  ...

Step 4: Translating to Rust...
  Initial translation complete

Step 5: Compiling and refining...
  Compilation successful after 1 iteration(s)!
```

## Test All Examples

```bash
python main.py --all
```

## Available Test Cases

- `scanf_two_ints` - Reading multiple integers with scanf (default)
- `array_indexing` - Array access with integer indices
- `long_long_mult` - Type casting for large multiplication
- `malloc_array` - Dynamic array allocation with malloc
- `mixed_io_array` - Combined I/O and array operations
- `simple_pointer` - Basic pointer allocation
- `float_conversion` - Integer to float conversion

Run a specific test:
```bash
python main.py --test array_indexing
```

## Run Evaluations (Optional)

GUARDIAN includes evaluation tasks built with [Inspect AI](https://inspect.ai-safety-institute.org.uk/) to measure translation quality:

```bash
# Run all test cases through eval framework
inspect eval src/defacc/evals/c_to_rust.py@all_tests

# View results in web UI
inspect view
```

This measures compilation success rate and tracks refinement iterations. See README.md for full details.

## Use in Your Code

```python
import dspy
from guardian.pipeline import GUARDIANPipeline

# 1. Configure LLM
lm = dspy.LM(
    model='anthropic/claude-3-5-sonnet-20241022',
    api_key='your-key-here'
)
dspy.configure(lm=lm)

# 2. Create pipeline
pipeline = GUARDIANPipeline(lm=lm)

# 3. Translate
c_code = """
int arr[10];
for (int i = 0; i < 10; i++) {
    arr[i] = i * 2;
}
"""

result = pipeline.translate(c_code, verbose=True)
print(result['rust_code'])
print(f"Compiled successfully: {result['compiled']}")
```

## Troubleshooting

### "No module named 'dspy'"
```bash
# Reinstall dependencies
uv sync

# Make sure venv is activated
source .venv/bin/activate
```

### "rustc not found"
```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
```

### "Missing configuration"
```bash
# Create .env file from example
cp .env.example .env

# Then edit .env with your settings:
# MODEL=anthropic/claude-3-5-sonnet-20241022
# API_KEY=sk-ant-your-key-here
# TEMPERATURE=0.7
```

### "Corpus file not found"
```bash
# Make sure you're in the project root
cd /path/to/defacc
python main.py

# The corpus should be at: src/defacc/corpus/examples.json
```

## Next Steps

1. **Add your own examples**: Edit `src/defacc/corpus/examples.json`
2. **Test on real code**: Try translating your own C snippets
3. **Tune parameters**: Adjust `max_refinement_iterations` in GUARDIANPipeline
4. **Try different LLMs**: Experiment with GPT-4, Claude, or local models

## Performance Tips

- **First run is slow**: DSPy caches responses, subsequent runs are faster
- **Use local models**: For faster iteration, try Ollama + Llama 3
- **Batch translations**: Process multiple files by calling `pipeline.translate()` in a loop
- **Skip compilation**: Set `check_rustc_available()` to return False for faster prototyping

## Example Output

**Input C:**
```c
int a, b;
scanf("%d%d", &a, &b);
printf("%d\n", a + b);
```

**Output Rust:**
```rust
use std::io::{self, BufRead};

fn main() {
    let mut input = String::new();
    io::stdin().read_line(&mut input).unwrap();
    let nums: Vec<i32> = input
        .split_whitespace()
        .map(|s| s.parse().unwrap())
        .collect();
    let (a, b) = (nums[0], nums[1]);
    println!("{}", a + b);
}
```

## Common Issues

| Issue | Solution |
|-------|----------|
| Import errors | Check you're in venv: `which python` should show `.venv/` |
| API rate limits | Add delays between calls or use caching |
| Compilation fails | Check rustc is in PATH: `echo $PATH | grep cargo` |
| Wrong category detected | Add more specific patterns in `rule_analyzer.py` |

## Happy Hacking! 🚀

For more details, see the full README.md
