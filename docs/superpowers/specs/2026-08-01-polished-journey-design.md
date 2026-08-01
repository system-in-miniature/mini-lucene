# MiniLucene Polished Learning Surfaces Design

## Objective

MiniLucene keeps its existing bilingual eleven-chapter Mechanism Tutorial and
adds two reconstruction modes:

1. a thirty-Stage bilingual Self-Guided Rebuild with exact cumulative patches;
2. a direct, resumable Agent-Guided Rebuild started from the canonical checkout.

## Why thirty Stages

Eleven chapter-aligned Stages would combine unrelated storage, visibility, and
query-execution deltas into oversized lessons. A commit-for-commit Journey would
instead create several acceptance-only lessons with no new mechanism. The
selected map follows real mechanism commits and folds each phase acceptance
boundary into the mechanism it closes.

## Stage map

| Stage | Boundary | Mechanism increment |
|---:|---|---|
| 01 | `3751ebd..7db4ce2` | Package, fields, documents, schema validation, and public contract |
| 02 | `a469ab5` | Positional analysis pipeline and token attributes |
| 03 | `6d97fff` | Immutable positional RAM segment and postings |
| 04 | `e88e295` | Closed positional query AST and matching |
| 05 | `02391db` | Snapshot-wide corpus statistics |
| 06 | `33df4a2` | Global BM25, norms, and field boosts |
| 07 | `6ef37cb..50be416` | Bounded Top-K search and retrieval-kernel acceptance |
| 08 | `57d4e7b` | Immutable segment images |
| 09 | `666557d` | Bounded varint primitives |
| 10 | `1d97dd2` | Educational on-disk segment codec |
| 11 | `631d9d7` | Checksummed segment publication |
| 12 | `c3ace7d` | Manifest as the committed index root |
| 13 | `d653459` | Directory and writer lifecycle ownership |
| 14 | `5ebaa42` | Flush from RAM to immutable segments |
| 15 | `2710c95..e277c21` | Atomic commit, recovery, reopen, and phase acceptance |
| 16 | `851fb55` | Point-in-time reader snapshots |
| 17 | `839c3f9` | Explicit near-real-time refresh |
| 18 | `fae32a8` | Immutable live-document masks |
| 19 | `0d98f3f` | Exact-term deletion through live-doc overlays |
| 20 | `a93e6d3..7b08e8e` | Update as delete-plus-add and live-only BM25 statistics |
| 21 | `fe3ccc0` | Explicit immutable-segment merge |
| 22 | `2bbb6f8..2a0c23d` | Segment ownership, close semantics, cleanup, and NRT acceptance |
| 23 | `8a13da1` | Closed query-language lexer |
| 24 | `aa91e92` | Recursive-descent parser and precedence |
| 25 | `7fc8145` | Bounded prefix rewrite |
| 26 | `30a839a` | Highlighting from analyzer offsets |
| 27 | `f9b50ad..588b645` | Deterministic relevance metrics and reference corpus |
| 28 | `36219c7..530f74b` | Thin CLI, failure matrix, public surface, and V1 domain closure |
| 29 | `fc57315..dd4b50c` | Parser/token validation regressions and scoring/codec boundary fixes |
| 30 | `88296f0` | DAAT iterators, streaming scoring, collect-then-fetch, and differential oracle |

## Teaching contract

Every localized page is authored in this order: current problem; Test contract
with a nested failure preview and real critical assertion; concepts and
necessity; runtime mental model; grouped mechanism blocks with implementation
diffs and critical-statement explanations; verification; durable takeaways;
learner explanation; relevant tutorial chapter.

Tests belong only to the Test contract. A mechanism block may own several files
when they form one runtime boundary. Routine exports, fixtures, lockfiles, and
configuration are one collapsed supporting group. Tests motivate and verify the
mechanism without imposing a mandatory test-first teaching narrative.

## Patch and parity boundary

The Journey owns `src/minilucene/**`, behavioral tests and their fixtures/helpers,
`pyproject.toml`, and `uv.lock`. It excludes documentation, distribution
artifacts, and documentation-only tests. Stage 30 must match every owned current
byte exactly.

## Agent contract

`开始 Agent 带教 Stage NN` prepares or resumes a Stage-specific internal
workspace while the learner stays in the canonical checkout. The Agent performs
a short misconception screen, teaches concepts before implementation, uses the
authored test counterexample as evidence, walks mechanism blocks, and finishes
only after focused tests plus canonical parity pass. It never creates or asks
the learner to switch a teaching branch. The website contains only a short CLI
usage guide.

## Acceptance gates

Polished acceptance requires full tests, Ruff, compileall, all thirty cumulative
Stage checks, final byte parity, deterministic bilingual rendering, strict
MkDocs, and real-browser checks across analysis, indexing, codec, commit, NRT,
query language, regression, and DAAT Stages. Browser acceptance also checks
collapsed drawers, Test-contract ownership, same-Stage language switching, and
both Agent-guide routes.
