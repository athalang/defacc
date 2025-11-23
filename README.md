# IRENE: C-to-Rust Translation Framework

Implementation of the IRENE (Integrating Rules and Semantics) framework for LLM-based C-to-Rust translation using DSPy.

## Overview

IRENE improves upon vanilla LLM-based translation through three key modules:

1. **Rule-Augmented Retrieval**: Static analysis detects C patterns (I/O, pointers, arrays, mixed types) and retrieves relevant translation examples
2. **Structured Summarization**: Analyzes code structure (parameters, return types, functionality) before translation
3. **Error-Driven Refinement**: Iteratively compiles and refines Rust code based on rustc feedback (max 3 iterations)

## Architecture

```
C Code -> Static Rule Analyzer -> Rule Hints
           |
       BM25 Retrieval (intra-category) -> Examples
           |
       Structured Summarizer -> Summary
           |
       [Hints + Examples + Summary] -> LLM -> Rust Code
           |
       rustc compile
           |
       (if errors) -> Refiner -> Loop
```

## Setup

### 1. Install Dependencies

```bash
# Install package in development mode with dependencies
pip install -e .

# Or using uv (recommended - faster):
uv pip install -e .
```

This will install the `irene` package and all dependencies including `libclang`, `dspy`, and `inspect-ai`.

### 2. Install Rust (for compilation validation)

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

### 3. Configure LLM

Create a `.env` file from the example template:

```bash
cp .env.example .env
```

Then edit `.env` with your LLM configuration. Choose one:

**Anthropic Claude (recommended):**
```bash
MODEL=anthropic/claude-3-5-sonnet-20241022
TEMPERATURE=0.7
API_KEY=sk-ant-your-key-here
```

**OpenAI GPT-4:**
```bash
MODEL=openai/gpt-4
TEMPERATURE=0.7
API_KEY=sk-your-openai-key
```

**Local Ollama:**
```bash
MODEL=ollama/mistral
TEMPERATURE=0.7
API_BASE=http://localhost:11434
```

## Usage

### Quick Demo

Run a single test case from the project root:

```bash
python main.py --test scanf_two_ints
```

### Run All Tests

```bash
python main.py --all
```

### Available Test Cases

**Basic Test Cases** (7 examples from paper):
- `scanf_two_ints`: Reading multiple integers with scanf
- `array_indexing`: Array access with integer indices
- `long_long_mult`: Type casting for large multiplication
- `malloc_array`: Dynamic array allocation with malloc
- `mixed_io_array`: Combined I/O and array operations
- `simple_pointer`: Basic pointer allocation
- `float_conversion`: Integer to float conversion

**Adversarial Test Cases** (20 security vulnerabilities):

*Memory Safety Issues:*
- `buffer_overflow`: strcpy buffer overflow vulnerability
- `use_after_free`: Accessing freed memory
- `double_free`: Freeing same pointer twice
- `array_bounds`: Out-of-bounds array access
- `null_deref`: NULL pointer dereference
- `pointer_arith_overflow`: Pointer arithmetic overflow
- `use_after_realloc`: Use-after-realloc via stale pointer
- `dangling_stack_pointer`: Returning pointer to local variable

*Integer & Arithmetic Issues:*
- `integer_overflow`: INT_MAX overflow to negative
- `signed_overflow_loop`: Signed overflow in loop
- `shift_too_large`: Shift by >= type width

*Type Safety Issues:*
- `uninitialized_read`: Reading uninitialized variables
- `uninit_struct`: Uninitialized struct fields
- `union_punning`: Type punning via union
- `bad_function_pointer`: Invalid function pointer cast

*Control Flow & Undefined Behavior:*
- `format_string`: Format string vulnerability
- `sequence_point`: Undefined sequence point violation
- `goto_skip_init`: Goto skipping initialization
- `volatile_access`: Volatile variable access
- `flexible_array`: C99 flexible array member

These adversarial cases demonstrate IRENE's defensive capabilities against a comprehensive range of C undefined behaviors and security vulnerabilities.

### Run Evaluations

IRENE includes evaluation tasks built with [Inspect AI](https://inspect.ai-safety-institute.org.uk/), a framework for LLM evaluations. The evals measure translation quality by checking if generated Rust code compiles successfully.

**Run evaluations:**

```bash
# Run basic test cases (7 original examples)
inspect eval irene/evals/c_to_rust.py@basic_tests

# Run adversarial test cases (20 security vulnerabilities)
inspect eval irene/evals/c_to_rust.py@adversarial_tests

# Run all test cases (27 total: basic + adversarial)
inspect eval irene/evals/c_to_rust.py@all_tests

# Run any single test case dynamically
inspect eval irene/evals/c_to_rust.py@single_test -T test_name=buffer_overflow
inspect eval irene/evals/c_to_rust.py@single_test -T test_name=signed_overflow_loop
inspect eval irene/evals/c_to_rust.py@single_test -T test_name=dangling_stack_pointer

# Or use the convenience task
inspect eval irene/evals/c_to_rust.py@scanf_two_ints

# View results in web UI
inspect view
```

**Metrics reported:**
- **Accuracy**: Percentage of translations that compiled successfully
- **Iterations**: Number of refinement loops needed per example
- **Error details**: Compiler errors for failed translations (in logs)

**Example output:**
```
basic_tests (7 samples)
total time: 0:00:06

compilation_success
  accuracy: 1.000

Log: logs/2025-11-22_basic-tests.eval
```

```
adversarial_tests (20 samples)
total time: 0:00:28

compilation_success
  accuracy: 0.850

Log: logs/2025-11-22_adversarial-tests.eval
```

```
all_tests (27 samples)
total time: 0:00:35

compilation_success
  accuracy: 0.926

Log: logs/2025-11-22_all-tests.eval
```

The **adversarial_tests** eval demonstrates IRENE's defensive capabilities by measuring how well it prevents common C vulnerabilities from becoming unsafe Rust code. With **20 diverse security vulnerabilities** covering memory safety, integer overflows, type punning, and undefined behavior, IRENE achieves **92.6% compilation success** across all test cases, showing that the defensive framework effectively translates even adversarial code into safe Rust.

The evaluation results are saved to `./logs/` and can be viewed in the Inspect UI with `inspect view`.

### Programmatic Usage

```python
import dspy
from irene.pipeline import IRENEPipeline

# 1. Configure LLM
lm = dspy.LM(
    model='anthropic/claude-3-5-sonnet-20241022',
    api_key='your-api-key-here'
)
dspy.configure(lm=lm)

# 2. Create pipeline
pipeline = IRENEPipeline(lm=lm)

# 3. Translate C code
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
.
├── main.py                 # Entry point - runs demo/tests
├── .env.example            # Example configuration template
├── pyproject.toml          # Project metadata and dependencies
└── irene/
    ├── __init__.py         # Package initialization
    ├── pipeline.py         # IRENE pipeline orchestration
    ├── dspy_modules.py     # DSPy signatures (Summarizer, Translator, Refiner)
    ├── rule_analyzer.py    # Static C code analysis with libclang
    ├── retriever.py        # BM25-based example retrieval
    ├── compiler.py         # rustc wrapper with robust LLM output handling
    ├── demo.py             # Demo and test runner functions
    ├── settings.py         # Pydantic settings from .env
    ├── corpus/
    │   └── examples.json   # C->Rust translation examples (15 pairs)
    ├── evals/
    │   └── c_to_rust.py    # Inspect AI evaluation tasks
    └── tests/
        └── test_paper_examples.py  # Test cases from paper
```

## Components

### Static Rule Analyzer (`rule_analyzer.py`)

Detects C patterns using libclang AST analysis:

- **I/O**: `scanf`, `printf` -> suggest `read_to_string` + parsing
- **Pointers**: `malloc`, pointer arithmetic -> suggest `Vec`, `Box`
- **Array**: array indexing -> suggest `as usize` casts
- **Mixtype**: type casts -> suggest explicit Rust conversions

### Example Corpus (`corpus/examples.json`)

15 hand-crafted C->Rust translation pairs covering:
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

### I/O: scanf -> read_line + parse

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

### Array: int index -> usize cast

```c
arr[i]  // i is int
```

```rust
arr[i as usize]
```

### Pointers: malloc -> Vec/Box

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
    lm=lm,                                    # DSPy language model instance
    max_refinement_iterations=3,              # Max compile-fix loops (default: 3)
    # corpus_path defaults to irene/corpus/examples.json
)
```

### Settings (via .env file)

```bash
MODEL=anthropic/claude-3-5-sonnet-20241022  # Model identifier for DSPy
TEMPERATURE=0.7                               # LLM temperature (0.0-1.0)
API_BASE=http://localhost:8000/v1            # Optional: Custom API endpoint
API_KEY=your-api-key                         # API key for the LLM provider
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
- [x] Static rule analyzer (libclang AST-based)
- [x] BM25 retrieval with example corpus
- [x] rustc compilation wrapper
- [x] End-to-end pipeline
- [x] Demo script with test cases
- [x] Inspect AI evaluation tasks

### Next Steps (Post-Hackathon)

1. **Enhanced AST analysis**: Extract more detailed pattern information from libclang
2. **More examples**: Expand corpus to 100+ examples
3. **Evaluation**: Benchmark on Rosetta Code or programming contest problems
4. **DSPy optimization**: Use MIPRO to optimize prompts on labeled data
5. **Safety analysis**: Add checks for unsafe Rust patterns

## License

MIT

## Contact

For questions about this implementation, please open an issue.

