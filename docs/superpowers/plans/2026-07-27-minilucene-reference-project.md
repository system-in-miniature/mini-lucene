# MiniLucene Reference Project Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and accept a Direct-first Python lexical search engine that connects field analysis, positional postings, BM25, immutable segments, NRT readers, mutation, merge, parsing, highlighting, and evaluation.

**Architecture:** The project is split into four dependency-ordered phases. Each phase produces working software, ends with the complete suite green, and makes one acceptance commit; later phases may consume only stable public contracts frozen by earlier phases.

**Tech Stack:** Python 3.12, standard library, dataclasses, pathlib, heapq, struct, hashlib, JSON, pytest 9, pytest-asyncio only where lifecycle tests need it, Ruff, Hatchling, uv.

---

## Authoritative design

[MiniLucene Reference Project Design](../specs/2026-07-27-minilucene-reference-project-design.md)

## Plan set

Execute in order:

1. [Retrieval Kernel](./2026-07-27-minilucene-retrieval-kernel.md)
2. [Immutable Storage and Commit](./2026-07-27-minilucene-storage-commit.md)
3. [NRT Mutation and Merge](./2026-07-27-minilucene-nrt-mutation.md)
4. [Product Closure and Final Acceptance](./2026-07-27-minilucene-product-acceptance.md)

```text
Phase 1: Schema + Analyzer + RAM postings + Query + BM25 + Top-K
   ↓
Phase 2: codecs + immutable segments + flush + manifest + recovery
   ↓
Phase 3: reader snapshots + refresh + live docs + update + merge
   ↓
Phase 4: parser + highlighting + evaluation + CLI + final acceptance
```

## Repository and workflow

- Repository root: `~/MiniLucene-workspace/MiniLucene`
- Branch: `main`
- Execution style: inline only; do not dispatch subagents.
- Use TDD for every behavior change.
- Make one focused local commit per task.
- Do not create a remote, push, PR, deployment, or course repository.

## Cross-phase invariants

- The schema fingerprint is stable and persisted.
- Analysis emits immutable term/position/original-offset values.
- Segment-local doc IDs are dense and never application identifiers.
- Posting doc IDs and positions are strictly increasing.
- Query matching and scoring remain separate.
- BM25 statistics use all live documents in the reader snapshot, never one
  segment's local corpus.
- Top-K retains at most K hits.
- Segment files and live-doc generations are immutable.
- Only a manifest publication creates a recoverable commit.
- Existing readers never change after refresh, commit, delete, update, or merge.
- Ordinary failures never partially publish a writer state or reader snapshot.
- TCP, HTTP, distributed coordination, vector retrieval, and course material
  remain outside V1.

## Phase acceptance protocol

At the end of each phase:

```bash
cd ~/MiniLucene-workspace/MiniLucene
uv sync --dev
uv run ruff check src tests tools
uv run pytest -q
uv run python -m compileall -q src tests tools
git diff --check
git status --short
git log -1 --oneline
```

No skipped or xfailed core test may be used to claim completion. The worktree
must be clean after the phase acceptance commit.

## Final stop condition

Stop after Phase 4 accepts the reference project. Do not create `course/`,
chapter files, review quizzes, a vector index, or another repository.
