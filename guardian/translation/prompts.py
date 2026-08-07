from typing import Any, Optional


def build_rust_partial(*, dependency_context: Optional[str]) -> str:
    return (dependency_context or "").strip()


def compose_rust_fragment(dependency_context: str, rust_code: str) -> str:
    dependency_context = (dependency_context or "").strip()
    rust_code = (rust_code or "").strip()
    if dependency_context and rust_code:
        return f"{dependency_context}\n\n{rust_code}"
    return dependency_context or rust_code


def clean_llm_response(response: Any) -> str:
    if isinstance(response, list):
        response = response[0] if response else ""
    text = str(response).strip()
    if text.startswith("```rust"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def build_translation_prompt(*, c_code: str, rust_partial: str) -> str:
    return (
        "Translate the following C code to Rust by completing the partial Rust code.\n\n"
        f"C code:\n{c_code.strip()}\n\n"
        f"Rust partial code:\n{rust_partial.strip()}\n\n"
        "Rust completion:"
    )


def build_refinement_prompt(
    *,
    rust_code: str,
    dependency_context: str,
    errors: str,
) -> str:
    return (
        "Fix the Rust completion so the combined Rust code compiles.\n\n"
        f"Rust partial code:\n{dependency_context.strip()}\n\n"
        f"Rust completion:\n{rust_code.strip()}\n\n"
        f"Compiler errors:\n{errors.strip()}\n\n"
        "Fixed Rust completion:"
    )


def build_vanilla_translation_prompt(c_code: str) -> str:
    return f"""Translate the following C code to safe Rust code.

Requirements:
- Use only Rust standard library (no external crates)
- Ensure memory safety
- Return ONLY valid Rust source code (no markdown, no explanations)

C code:
```c
{c_code}
```

Rust code:"""
