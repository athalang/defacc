#!/bin/bash
# Run baseline comparison between Vanilla LLM and GUARDIAN
#
# This script runs evaluations and generates a comparison report

set -e

echo "=================================================="
echo "GUARDIAN Baseline Comparison"
echo "=================================================="
echo ""

# Create logs directory if it doesn't exist
mkdir -p logs/baseline_comparison

# Run vanilla LLM evaluations
echo "Running Vanilla LLM evaluations..."
echo "-----------------------------------"

echo "1/4: Vanilla LLM - Basic tests (7 cases)..."
inspect eval guardian/evals/baseline_comparison.py@vanilla_basic \
    --log-dir logs/baseline_comparison \
    --log-level warning \
    --log-format=json

echo "2/4: Vanilla LLM - Adversarial tests (20 cases)..."
inspect eval guardian/evals/baseline_comparison.py@vanilla_adversarial \
    --log-dir logs/baseline_comparison \
    --log-level warning \
    --log-format=json

echo ""
echo "Running GUARDIAN evaluations..."
echo "-------------------------------"

echo "3/4: GUARDIAN - Basic tests (7 cases)..."
inspect eval guardian/evals/baseline_comparison.py@guardian_basic \
    --log-dir logs/baseline_comparison \
    --log-level warning \
    --log-format=json

echo "4/4: GUARDIAN - Adversarial tests (20 cases)..."
inspect eval guardian/evals/baseline_comparison.py@guardian_adversarial \
    --log-dir logs/baseline_comparison \
    --log-level warning \
    --log-format=json

echo ""
echo "=================================================="
echo "Evaluation Complete!"
echo "=================================================="
echo ""
echo "Results saved to: logs/baseline_comparison/"
echo ""
echo "To view interactive results:"
echo "  inspect view"
echo ""
echo "To generate comparison report:"
echo "  python scripts/generate_comparison_report.py"
echo ""