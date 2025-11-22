# IRENE: C-to-Rust Translation Framework

Implementation of the IRENE (Integrating Rules and Semantics) framework for LLM-based C-to-Rust translation using DSPy.

## Overview

IRENE improves upon vanilla LLM-based translation through three key modules:

1. **Rule-Augmented Retrieval**: Static analysis detects C patterns (I/O, pointers, arrays, mixed types) and retrieves relevant translation examples
2. **Structured Summarization**: Analyzes code structure (parameters, return types, functionality) before translation
3. **Error-Driven Refinement**: Iteratively compiles and refines Rust code based on rustc feedback (max 3 iterations)

## Architecture

```
C Code → Static Rule Analyzer → Rule Hints
           ↓
       BM25 Retrieval (intra-category) → Examples
           ↓
       Structured Summarizer → Summary
           ↓
       [Hints + Examples + Summary] → LLM → Rust Code
           ↓
       rustc compile
           ↓
       (if errors) → Refiner → Loop
```

## Setup

### 1. Install Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Install Rust (for compilation validation)

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

### 3. Configure LLM

Set your API key for one of the supported providers:

```bash
# Anthropic Claude (recommended)
export ANTHROPIC_API_KEY='your-key-here'

# Or OpenAI
export OPENAI_API_KEY='your-key-here'

# Or configure a local model
export IRENE_MODEL='ollama/mistral'
```

## Usage

### Quick Demo

Run a single test case:

```bash
cd irene
python demo.py --test scanf_two_ints
```

### Run All Tests

```bash
python demo.py --all
```

### Available Test Cases

- `scanf_two_ints`: Reading multiple integers with scanf
- `array_indexing`: Array access with integer indices
- `long_long_mult`: Type casting for large multiplication
- `malloc_array`: Dynamic array allocation with malloc
- `mixed_io_array`: Combined I/O and array operations
- `simple_pointer`: Basic pointer allocation
- `float_conversion`: Integer to float conversion

### Programmatic Usage

```python
import dspy
from irene.main import IRENEPipeline

# Configure LLM
lm = dspy.LM('anthropic/claude-3-5-sonnet-20241022')

# Create pipeline
pipeline = IRENEPipeline(lm_model=lm)

# Translate C code
c_code = """
#include <stdio.h>
int main() {
    int a, b;
    scanf("%d%d", &a, &b);
    printf("%d\\n", a + b);
    return 0;
}
"""

result = pipeline.translate(c_code, verbose=True)
print(result['rust_code'])
print(f"Compiled: {result['compiled']}")
```

## Project Structure

```
irene/
├── main.py              # IRENE pipeline orchestration
├── dspy_modules.py      # DSPy signatures (Summarizer, Translator, Refiner)
├── rule_analyzer.py     # Static C code analysis
├── retriever.py         # BM25-based example retrieval
├── compiler.py          # rustc wrapper
├── demo.py              # Demo script
├── corpus/
│   └── examples.json    # C→Rust translation examples (15 pairs)
└── tests/
    └── test_paper_examples.py  # Test cases from paper
```

## Components

### Static Rule Analyzer (`rule_analyzer.py`)

Detects C patterns using regex:

- **I/O**: `scanf`, `printf`  suggest `read_to_string` + parsing
- **Pointers**: `malloc`, pointer arithmetic  suggest `Vec`, `Box`
- **Array**: array indexing  suggest `as usize` casts
- **Mixtype**: type casts  suggest explicit Rust conversions

### Example Corpus (`corpus/examples.json`)

15 hand-crafted CRust translation pairs covering:
- Standard I/O operations
- Memory allocation patterns
- Array access patterns
- Type conversion idioms

Tagged by category for BM25 retrieval.

### BM25 Retrieval (`retriever.py`)

- Filters examples by detected rule categories
- Ranks by similarity using BM25 on C code
- Returns top-3 most relevant examples

### DSPy Modules (`dspy_modules.py`)

Three Chain-of-Thought modules:

1. **CodeSummary**: Extracts parameters, return type, functionality
2. **CToRust**: Translates with rule hints, examples, summary
3. **RefineRust**: Fixes code based on compiler errors

### Compilation Loop (`compiler.py`)

- Writes Rust to temp file
- Runs `rustc --crate-type lib`
- Captures stderr for refinement
- Max 3 refinement iterations

## Key Translation Patterns

### I/O: scanf  read_line + parse

```c
scanf("%d%d", &a, &b);
```

```rust
let mut input = String::new();
io::stdin().read_line(&mut input).unwrap();
let nums: Vec<i32> = input.split_whitespace()
    .map(|s| s.parse().unwrap()).collect();
let (a, b) = (nums[0], nums[1]);
```

### Array: int index  usize cast

```c
arr[i]  // i is int
```

```rust
arr[i as usize]
```

### Pointers: malloc  Vec/Box

```c
int *arr = malloc(n * sizeof(int));
```

```rust
let arr: Vec<i32> = Vec::with_capacity(n);
```

### Mixtype: explicit casts

```c
long long result = (long long)x * y;
```

```rust
let result = (x as i64) * (y as i64);
```

## Configuration Options

### IRENEPipeline Parameters

```python
pipeline = IRENEPipeline(
    lm_model=lm,                              # DSPy language model
    corpus_path="irene/corpus/examples.json", # Path to examples
    max_refinement_iterations=3,              # Max compile-fix loops
)
```

## Extending IRENE

### Add New Translation Patterns

Edit `corpus/examples.json`:

```json
{
  "c_code": "your C code",
  "rust_code": "your Rust code",
  "categories": ["I/O", "Array"],
  "description": "What this example demonstrates"
}
```

### Add New Rule Categories

1. Add detection logic in `rule_analyzer.py`:

```python
def _check_your_pattern(self, code: str) -> List[RuleHint]:
    if re.search(r'your_pattern', code):
        return [RuleHint(
            category="YourCategory",
            code_snippet="...",
            suggested_rust="...",
            explanation="..."
        )]
    return []
```

2. Call from `analyze()` method
3. Tag corpus examples with new category

### MVP Checklist

- [x] DSPy module definitions
- [x] Static rule analyzer (regex-based)
- [x] BM25 retrieval with example corpus
- [x] rustc compilation wrapper
- [x] End-to-end pipeline
- [x] Demo script with test cases

### Next Steps (Post-Hackathon)

1. **Better parsing**: Replace regex with tree-sitter or pycparser AST
2. **More examples**: Expand corpus to 100+ examples
3. **Evaluation**: Benchmark on Rosetta Code or programming contest problems
4. **DSPy optimization**: Use MIPRO to optimize prompts on labeled data
5. **Safety analysis**: Add checks for unsafe Rust patterns

## License

MIT

## Contact

For questions about this implementation, please open an issue.

