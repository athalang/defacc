# IRENE Quick Start Guide

Get started with IRENE in 5 minutes!

## Prerequisites

1. Python 3.8+
2. Rust (optional, for compilation validation)
3. API key for Anthropic or OpenAI

## Installation

```bash
# 1. Activate virtual environment (already created)
source .venv/bin/activate

# 2. Verify installation
python -c "import dspy; print('✓ DSPy installed')"
python -c "import pycparser; print('✓ pycparser installed')"
python -c "import rank_bm25; print('✓ BM25 installed')"

# 3. Check Rust (optional)
rustc --version
```

## Set Your API Key

Choose one:

```bash
# Option 1: Anthropic Claude (recommended for accuracy)
export ANTHROPIC_API_KEY='sk-ant-...'

# Option 2: OpenAI GPT-4
export OPENAI_API_KEY='sk-...'

# Or configure a local model
export IRENE_MODEL='ollama/mistral'
```

## Run Your First Translation

```bash
cd irene
python demo.py --test scanf_two_ints
```

You should see:

```
IRENE C-to-Rust Translation Pipeline
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
  ✓ Compilation successful after 1 iteration(s)!
```

## Test All Examples

```bash
python demo.py --all
```

## Use in Your Code

```python
import dspy
from irene import IRENEPipeline

# 1. Configure LLM
lm = dspy.LM('anthropic/claude-3-5-sonnet-20241022')

# 2. Create pipeline
pipeline = IRENEPipeline(lm_model=lm)

# 3. Translate
c_code = """
int arr[10];
for (int i = 0; i < 10; i++) {
    arr[i] = i * 2;
}
"""

result = pipeline.translate(c_code)
print(result['rust_code'])
```

## Troubleshooting

### "No module named 'dspy'"
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### "rustc not found"
```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
```

### "No API keys found"
```bash
# Set your key
export ANTHROPIC_API_KEY='your-key'

# Or create .env file
echo "ANTHROPIC_API_KEY=your-key" > .env
python -c "from dotenv import load_dotenv; load_dotenv()"
```

### "Corpus file not found"
```bash
# Make sure you're in the project root
cd /path/to/defacc
python irene/demo.py
```

## Next Steps

1. **Add your own examples**: Edit `irene/corpus/examples.json`
2. **Test on real code**: Try translating your own C snippets
3. **Tune parameters**: Adjust `max_refinement_iterations` in IRENEPipeline
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
