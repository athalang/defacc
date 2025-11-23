import dspy

class CodeSummary(dspy.Signature):
    c_code: str = dspy.InputField(desc="C source code to analyse")
    arguments: str = dspy.OutputField(desc="Input arguments, their types and their semantics")
    outputs: str = dspy.OutputField(desc="Return values, their types and their semantics")
    function: str = dspy.OutputField(desc="What the code does at a high level")

class CToRust(dspy.Signature):
    c_code: str = dspy.InputField(desc="C source code to translate")
    rule_hints: str = dspy.InputField(desc="Translation rules and patterns to apply")
    examples: str = dspy.InputField(desc="Similar C-to-Rust translation examples")
    summary: str = dspy.InputField(desc="High-level summary of the code's purpose")
    rust_code: str = dspy.OutputField(desc="Pure Rust source code using ONLY std library, no markdown, no explanations")

class RefineRust(dspy.Signature):
    """Fix Rust code based on compiler errors.

    Analyze the rustc errors and produce corrected code that compiles successfully
    while maintaining the original functionality.

    REQUIREMENTS:
    - Use ONLY Rust standard library (std::*). NO external crates
    - Fix ONLY the errors shown. Do not add unnecessary features or dependencies
    - Return ONLY valid Rust source code that compiles with rustc
    - Do NOT include markdown code fences (```rust or ```)
    - Do NOT include explanatory text about what you fixed
    - Do NOT include file names or cargo configuration
    - Do NOT include any prose or instructions to the user
    """

    rust_code: str = dspy.InputField(desc="The Rust code that failed to compile")
    errors: str = dspy.InputField(desc="Compiler error messages from rustc")
    fixed_code: str = dspy.OutputField(desc="Pure Rust source code using ONLY std library, no markdown, no explanations")

class GUARDIANModules:
    """Container for all DSPy modules used in GUARDIAN pipeline."""

    def __init__(self):
        self.summarizer = dspy.ChainOfThought(CodeSummary)
        self.translator = dspy.ChainOfThought(CToRust)
        self.refiner = dspy.ChainOfThought(RefineRust)
