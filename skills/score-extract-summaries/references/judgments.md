# Judgment file contract

Write `judgments.json` alongside `input.json`. Compute `input_sha256` with the helper's `fingerprint(json.load(...))`: SHA-256 of `json.dumps(input, sort_keys=True, ensure_ascii=False).encode()`. This pins judgments to the exported candidate and gold snapshot; it does not prove semantic review quality.

```json
{
  "input_sha256": "<fingerprint of complete parsed input.json>",
  "reviewer": "actual session/agent identity (model)",
  "limitations": ["Self-reviewed; no independent reviewer."],
  "chunks": [
    {
      "pred": 7,
      "units": [
        {
          "id": "u1",
          "credit": 1,
          "reason": "Preserves the full storage instruction.",
          "prediction_spans": [{"start": 0, "end": 10, "quote": "Keep cool."}]
        }
      ],
      "claims": [
        {
          "start": 0, "end": 10, "quote": "Keep cool.",
          "status": "supported",
          "reason": "The source gives this instruction without an exception.",
          "evidence": [{"line": 12, "start": 0, "end": 10, "quote": "Keep cool."}]
        }
      ],
      "diagnostics": "Clear English; translation not applicable. Keywords match.",
      "similarity": {"score": 0.8, "reason": "Same storage instruction; the gold's exception clause is missing."}
    }
  ]
}
```

This is a fictional example, not a reusable judgment. `pred` is the exported database integer `id`, not `summary_id`. `id` under `units` is local to that gold chunk. Include exactly one judgment per aligned prediction and exactly one unit judgment per `included=true` gold unit. Missing chunks and duplicate/unknown-sequence rows require no judgment; the helper penalizes them automatically. Empty text has no claim spans. A missing/empty readable summary earns zero unit credit.

Offsets are zero-based Unicode code points, exclusive end, indexing the original prediction `summary_text` or canonical source `content`, including original whitespace. Claims must not overlap; together they cover every non-whitespace character in the prediction, including punctuation and bullet markers. Include formatting in an adjacent claim. Multiple claims may cite the same source evidence, and unit prediction spans may overlap. A unit can require several noncontiguous prediction spans. Positive unit credit requires at least one prediction span; zero credit can use `[]`.

Each supported claim needs one or more source spans in the same chunk. Include table headings, footnotes or exceptions when necessary to support the full meaning. Unsupported claims may have `evidence: []`; contradicted claims should cite contrary source evidence. Claim status is binary credit (supported=1, other=0); unit coverage allows half credit. Review every claim's scope, not just the words within its cited evidence. A sentence containing independently true and false assertions must be split into atomic claims. This prevents hiding an invention inside a mostly correct sentence. The helper verifies span accuracy and complete text accounting; the reviewer remains responsible for atomicity and semantic entailment.

For a 0.5 credit example, gold says “temperature must be at or below 8°C” but prediction says “temperature must be below 8°C”: central constraint retained, boundary changed. Explain and flag this critical error. “Always freeze it” is an additional unsupported instruction unless this chunk supports it; its relation to a maximum temperature alone does not establish a contradiction.

`similarity.score` is a number from 0 to 1 that judges the source-language `summary_text` against the gold `summary_text` in meaning: same actors, conditions, thresholds and exceptions score high; omitted or added material lowers it. Compare only that source-language text. Gold English summaries and keywords (both languages) are excluded from similarity and from the score. Language tags `zh` and `zh-cn` count as the same language. `similarity.reason` is required.

An included unit appearing only in an English translation does not rescue missing source-language coverage. Inspect translation and keywords separately in diagnostics. For comparative runs, keep claim segmentation and interpretation consistent; do not split supported material more finely to inflate faithfulness.
