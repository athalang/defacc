def count_unsafe(rust_code: str) -> tuple[int, int, int, int]:
    """Count unsafe constructs in generated Rust code."""
    unsafe_blocks = rust_code.count("unsafe {") + rust_code.count("unsafe{")
    unsafe_fn = rust_code.count("unsafe fn")
    unsafe_impl = rust_code.count("unsafe impl")
    total_unsafe = unsafe_blocks + unsafe_fn + unsafe_impl
    return unsafe_blocks, unsafe_fn, unsafe_impl, total_unsafe
