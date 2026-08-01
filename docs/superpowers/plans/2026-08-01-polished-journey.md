# MiniLucene Polished Journey Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a thirty-Stage bilingual Self-Guided Rebuild and direct
Agent-Guided Rebuild while preserving MiniLucene's eleven-chapter tutorial and
proving exact final source parity.

**Architecture:** A Git-backed manifest reconstructs thirty cumulative source
trees. Checked-in patches, focused tests, bilingual goal sources, and grouped
layouts feed one deterministic renderer and one resumable workspace tool.

**Tech Stack:** Python 3.12, pytest, TOML, Git patches, MkDocs Material, uv, and
Playwright for browser acceptance.

---

### Task 1: Freeze history extraction

- [ ] Add `journey/manifest.toml`, `journey/tools/extract_history.py`, and
  failing extractor tests for thirty contiguous boundaries and final parity.
- [ ] Reconstruct combined boundaries from the latest commit in each declared
  range while owning every changed source/test file exactly.
- [ ] Prove all revisions resolve, patches apply cumulatively, and Stage 30
  equals the current owned tree; commit the extraction contract.

### Task 2: Generate and execute the canonical patch chain

- [ ] Generate thirty `journey/stages/NN-slug/stage.patch` and `tests.txt`
  pairs from the manifest.
- [ ] Add contracts for non-empty patches, real focused tests, cumulative
  applicability, and chronological file replacement.
- [ ] Build from an empty repository and run each Stage's focused tests,
  correcting only genuine historical-boundary problems; commit the chain.

### Task 3: Author lessons and layouts

- [ ] Add failing content tests for bilingual order, nested failure preview,
  real critical assertions, file ownership, and no test paths in mechanisms.
- [ ] Author Stages 01–15 for schema, analysis, retrieval, codec, publication,
  manifest, flush, and commit.
- [ ] Author Stages 16–30 for NRT visibility, mutation, merge, query language,
  evaluation, regressions, and DAAT.
- [ ] Group causal multi-file diffs and collapse routine support files; commit
  the complete authored corpus.

### Task 4: Render deterministic bilingual browser pages

- [ ] Add renderer tests for 62 generated pages, lossless diff coverage,
  collapsed deliverables/drawers, grouped explanations, and Test-contract
  ownership of every failure preview and test diff.
- [ ] Adapt the proven renderer to MiniLucene's package roles and eleven
  tutorial routes, then generate `docs/journey/**` and `docs/zh/journey/**`.
- [ ] Regenerate twice and require no drift; commit renderer and pages.

### Task 5: Add Self-Guided and Agent-Guided CLI behavior

- [ ] Add tests and implementation for `study`, `attempt`, `agent`, `check`,
  protected reset, Stage-specific `READY`/`RESUME`, focused tests, and parity.
- [ ] Add root `AGENTS.md` with quick misconception screening, concept-first
  teaching, small code slices, mechanism-block walkthrough, and no teaching
  branch.
- [ ] Add short English/Chinese Agent usage pages and verify a real prepare,
  resume, complete, and check cycle; commit the learning modes.

### Task 6: Integrate navigation, localization, and CI

- [ ] Expose Mechanism Tutorial, Self-Guided Rebuild, and Agent-Guided Rebuild
  in both READMEs, both home surfaces, and MkDocs navigation.
- [ ] Add same-path language switching for all thirty Stages and Agent guides.
- [ ] Add CI gates for tooling, rendered drift, Stage chain, full tests, Ruff,
  compileall, and strict MkDocs; commit site integration.

### Task 7: Perform polished acceptance

- [ ] Run full tests, Ruff, compileall, all Journey tests, all thirty Stage
  checks, final parity, rendered drift, and strict MkDocs.
- [ ] Serve locally and inspect representative bilingual analysis, indexing,
  codec, commit, NRT, merge, parser, regression, and DAAT pages with Playwright.
- [ ] Verify drawers are collapsed, Test contract precedes concepts and
  mechanisms, test diffs never appear in mechanisms, language links preserve
  Stage paths, and Agent routes work.
- [ ] Move generated site output outside the repository, commit any acceptance
  fixes, and require a clean feature worktree without pushing.
