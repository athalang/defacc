#!/usr/bin/env python3
"""
Quick demo script for IRENE C-to-Rust translation.
Runs the default scanf_two_ints test case.

Usage:
    python demo.py                    # Run default test (scanf_two_ints)
    python demo.py array_indexing     # Run specific test
    python demo.py --all              # Run all tests
"""

if __name__ == "__main__":
    import sys
    import dspy
    from defacc.settings import settings
    from defacc.irene.pipeline import IRENEPipeline
    from defacc.irene.demo import run_demo, run_all_tests

    # Simple argument handling
    if "--all" in sys.argv:
        print("Running all test cases...\n")
        lm = dspy.LM(
            model=settings.model,
            api_base=settings.api_base,
            temperature=settings.temperature,
            api_key=settings.api_key,
        )
        dspy.configure(lm=lm)
        pipeline = IRENEPipeline(lm=lm)
        run_all_tests(pipeline)
    else:
        test_name = sys.argv[1] if len(sys.argv) > 1 else "scanf_two_ints"
        print(f"Running IRENE demo with test case: {test_name}\n")
        lm = dspy.LM(
            model=settings.model,
            api_base=settings.api_base,
            temperature=settings.temperature,
            api_key=settings.api_key,
        )
        dspy.configure(lm=lm)
        pipeline = IRENEPipeline(lm=lm)
        run_demo(pipeline, test_name)