# Retrieval runs and judging pool

runs.csv contains both systems' top-100 rankings and scores. queries/ contains complete per-query results, timings and parsed-query diagnostics. corpus_snapshot.jsonl is the shared listing snapshot. manifest.json records hashes, configuration and corpus coverage. queries_input.jsonl preserves query intentions; those annotations were not used to drive retrieval.

judging_pool.csv and judging_pool.jsonl contain the randomized, deduplicated union of each system's top 10 (or configured pool depth), with listing evidence and blank judgment fields. Do not show judges runs.csv, pool_provenance.jsonl or queries/ because they reveal system identity, rank and scores. pool_provenance.jsonl is the private source/rank mapping.

Assign relevance labels before calculating retrieval metrics. A zero-result successful run is different from a failed query; inspect diagnostics.json. An incomplete pool must not be treated as a completed two-system comparison. New-system route mismatches against intended categories are recorded in summary.json; retrieval used the actual parser output without correcting it to expected labels. Timings exclude model initialization and are measured sequentially, not a production latency benchmark.

Copy the blank judging pool before adding labels; resuming this collector regenerates it. Raw result scores from the two systems are not directly comparable relevance grades.
