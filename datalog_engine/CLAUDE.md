# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Soufflé Datalog project aimed at formalizing HIPAA privacy rules as a compliance checker. The source formalization lives in `HIPAA_FORMALIZATION.pdf` (first-order temporal logic, pages 30–122) and must be translated into Soufflé Datalog with provenance-based explanations for compliance decisions.

Currently in the **learning/prototyping phase** with two example `.dl` programs and extensive documentation.

## Running Soufflé Programs

```bash
# Run a program, writing output CSVs to a directory
souffle -D <output_dir> <program>.dl

# Run the family tree example via wrapper script
./run_example.sh

# Provenance / debugging
souffle -t explain <program>.dl       # interactive proof-tree REPL
souffle -t explore <program>.dl       # ncurses TUI for large proof trees
souffle --show=precedence-graph <program>.dl   # view stratification graph
souffle -r report.html <program>.dl            # HTML debug report (needs Graphviz)
```

There are no build steps, test suites, or linters — Soufflé compiles and evaluates `.dl` files directly.

## Key Files

- **family.dl** — Family-tree example: recursion, stratified negation, aggregation
- **comparisons.dl** — Numeric comparison operators (`>`, `>=`, `<`, `<=`, `=`, `!=`) and arithmetic
- **run_example.sh** — Bash wrapper that runs `family.dl` and pretty-prints results
- **souffle_guide.md** — In-depth reference covering Soufflé syntax, stratification, ADTs, and the explain/provenance feature
- **convo_summary.md** — Prior conversation notes on CLP, Soufflé stratification, and ADT explanation trees for compliance justification
- **task.md** — High-level project requirements for the HIPAA formalization
- **HIPAA_FORMALIZATION.pdf** — Source formalization in first-order temporal logic

## Architecture Notes

- Output CSVs go to `output/` (family.dl) and `output_comparisons/` (comparisons.dl) — these are generated artifacts, not source
- All `.dl` files are self-contained (inline facts, no `.input` from external files yet)
- The planned HIPAA compliance checker will use **ADT explanation trees** (tagged unions) to attach human-readable justifications to compliance decisions — see `convo_summary.md` for the recommended pattern
- Stratified negation is critical: "disclosure not allowed" rules must negate fully-computed positive relations
