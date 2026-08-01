# Self-Guided Rebuild

Each Stage is a complete independent-browser lesson: understand the current problem, concepts, and necessity; connect related files and critical statements through mechanism blocks; then close with evidence and your own explanation.

This is the browser-based path among MiniLucene's three learning modes. Use the [Mechanism Tutorial](../index.md) for topic-oriented study, or the [Agent-Guided usage guide](../agent-guide.md) for interactive CLI teaching.

For an editor-focused diff, run `python -m journey.tools.build_journey study N` and open `../MiniLucene-journey-workspace`.

| Stage | Topic | New tests | Book chapter |
|---:|---|---:|---:|
| [01](stage-01.md) | Field and document contract | 2 | [1](../tutorial/01-getting-started.md) |
| [02](stage-02.md) | Positional analysis | 1 | [2](../tutorial/02-analysis.md) |
| [03](stage-03.md) | Immutable RAM inverted index | 1 | [3](../tutorial/03-inverted-index.md) |
| [04](stage-04.md) | Closed query matching | 3 | [3](../tutorial/03-inverted-index.md) |
| [05](stage-05.md) | Snapshot corpus statistics | 2 | [8](../tutorial/08-scoring.md) |
| [06](stage-06.md) | Global BM25 ranking | 3 | [8](../tutorial/08-scoring.md) |
| [07](stage-07.md) | Bounded Top-K retrieval | 3 | [8](../tutorial/08-scoring.md) |
| [08](stage-08.md) | Immutable segment images | 1 | [4](../tutorial/04-codec.md) |
| [09](stage-09.md) | Bounded varint primitives | 1 | [4](../tutorial/04-codec.md) |
| [10](stage-10.md) | Educational segment codec | 1 | [4](../tutorial/04-codec.md) |
| [11](stage-11.md) | Checksummed segment publication | 1 | [4](../tutorial/04-codec.md) |
| [12](stage-12.md) | Manifest commit root | 1 | [7](../tutorial/07-commit-atomicity.md) |
| [13](stage-13.md) | Index lifecycle ownership | 1 | [5](../tutorial/05-segments-nrt.md) |
| [14](stage-14.md) | Writer flush | 1 | [5](../tutorial/05-segments-nrt.md) |
| [15](stage-15.md) | Atomic commit and reopen | 3 | [7](../tutorial/07-commit-atomicity.md) |
| [16](stage-16.md) | Point-in-time reader snapshots | 1 | [5](../tutorial/05-segments-nrt.md) |
| [17](stage-17.md) | Near-real-time refresh | 1 | [5](../tutorial/05-segments-nrt.md) |
| [18](stage-18.md) | Immutable live-doc masks | 2 | [6](../tutorial/06-deletes-updates.md) |
| [19](stage-19.md) | Delete by exact term | 1 | [6](../tutorial/06-deletes-updates.md) |
| [20](stage-20.md) | Update and live-only statistics | 2 | [6](../tutorial/06-deletes-updates.md) |
| [21](stage-21.md) | Explicit segment merge | 1 | [10](../tutorial/10-merge-and-beyond.md) |
| [22](stage-22.md) | Segment ownership and close | 3 | [10](../tutorial/10-merge-and-beyond.md) |
| [23](stage-23.md) | Closed query lexer | 1 | [9](../tutorial/09-query-language.md) |
| [24](stage-24.md) | Recursive-descent query parser | 1 | [9](../tutorial/09-query-language.md) |
| [25](stage-25.md) | Bounded prefix rewrite | 1 | [9](../tutorial/09-query-language.md) |
| [26](stage-26.md) | Offset-based highlighting | 1 | [9](../tutorial/09-query-language.md) |
| [27](stage-27.md) | Deterministic relevance evaluation | 4 | [8](../tutorial/08-scoring.md) |
| [28](stage-28.md) | CLI and domain closure | 5 | [1](../tutorial/01-getting-started.md) |
| [29](stage-29.md) | Query and token regressions | 4 | [9](../tutorial/09-query-language.md) |
| [30](stage-30.md) | Document-at-a-time execution | 4 | [11](../tutorial/11-daat.md) |
