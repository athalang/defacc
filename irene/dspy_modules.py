import dspy

class CodeSummary(dspy.Signature):
    c_code: str = dspy.InputField(desc="C source code snippet to analyse")
    declaration_context: str = dspy.InputField(
        desc="Plain-text description of what this snippet declares (function, struct, enum, typedef, SCC chunk, etc.)"
    )
    arguments: str = dspy.OutputField(desc="Inputs, members, or components involved in this declaration")
    outputs: str = dspy.OutputField(
        desc="Results, exposed data, or observable state produced/represented by this declaration"
    )
    function: str = dspy.OutputField(desc="High-level purpose or semantics regardless of declaration kind")


class CToRust(dspy.Signature):
    c_code: str = dspy.InputField(desc="C source code to translate")
    rule_hints: str = dspy.InputField(desc="Translation rules and patterns to apply")
    examples: str = dspy.InputField(desc="Similar C-to-Rust translation examples")
    summary: str = dspy.InputField(desc="High-level summary of the code's purpose")
    declaration_context: str = dspy.InputField(
        desc="Description of the declarations in this snippet so the translator can handle functions, structs, enums, etc."
    )
    dependency_context: str = dspy.InputField(
        desc="Summaries of already-translated upstream declarations you may reuse but must not redefine"
    )
    workspace_context: str = dspy.InputField(
        desc=(
            "Latest Rust workspace contents (trimmed). These definitions already exist."
            "DO NOT REDEFINE THEM AGAIN. Emit diffs only."
        )
    )
    workspace_file: str = dspy.InputField(
        desc=(
            "Absolute path to the Rust workspace file to edit."
            " You MUST output a unified diff against this file using '---'/'+++' headers"
            " and @@ hunk markers."
        )
    )
    translation_constraints: str = dspy.InputField(
        desc="Hard requirements on the shape/quantity of Rust declarations and formatting"
    )
    compiler_errors: str = dspy.InputField(
        desc="Rust compiler errors from the previous attempt (empty on first iteration)"
    )
    patch_diff: str = dspy.OutputField(
        desc=(
            "Unified diff (standard patch format) describing modifications to the workspace file."
            " MUST include file headers and hunk sections."
        )
    )

class IRENEModules:
    """Container for all DSPy modules used in IRENE pipeline."""

    def __init__(self):
        self.summarizer = dspy.ChainOfThought(CodeSummary)
        self.translator = dspy.ChainOfThought(CToRust)
