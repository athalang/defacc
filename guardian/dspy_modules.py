import dspy

class CToRust(dspy.Signature):
    c_code: str = dspy.InputField(desc="C source code to translate")
    declaration_context: str = dspy.InputField(
        desc="Description of the declarations in this snippet so the translator can handle functions, structs, enums, etc."
    )
    dependency_context: str = dspy.InputField(
        desc="Summaries of already-translated upstream declarations you may reuse but must not redefine"
    )
    rust_code: str = dspy.OutputField(desc="Pure Rust source code only using std library. NO MARKDOWN, NO EXPLANATIONS. NO MARKDOWN.")

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
        self.translator = dspy.ChainOfThought(CToRust)
        self.refiner = dspy.ChainOfThought(RefineRust)
