## Evaluation results

### Requirement extraction

| Metric | Text rules | qwen3:8b |
|---|---|---|
| Labelled requirements | 65 | 65 |
| Found | 62 | 64 |
| Correct | 60 | 63 |
| Extra (not a requirement) | 2 | 1 |
| Missed | 5 | 2 |
| Precision | 0.968 | 0.984 |
| Recall | 0.923 | 0.969 |
| F1 | 0.945 | 0.976 |
| Type accuracy (on correct ones) | 0.7 | 0.794 |

### Vague wording

| Metric | Text rules | qwen3:8b |
|---|---|---|
| Labelled vague | 5 | 5 |
| Flagged correctly | 5 | 5 |
| Flagged but not vague | 0 | 2 |
| Precision | 1.0 | 0.714 |
| Recall | 1.0 | 1.0 |

### Conflicts

| Metric | Text rules | qwen3:8b |
|---|---|---|
| Labelled conflicts | 5 | 5 |
| Found | 4 | 4 |
| Missed | 1 | 1 |
| False alarms | 3 | 0 |
| Look-alike pairs reported as conflicts | 3 | 0 |
| Look-alike pairs in total | 3 | 3 |

### Time

| Metric | Text rules | qwen3:8b |
|---|---|---|
| Seconds per document | 0.0 | 110.0 |

### Chat

| Metric | qwen3:8b |
|---|---|
| Questions | 10 |
| Passed the grounding check | 10 |
| Right answer | 9 |
| Seconds per question | 1.3 |

Peak GPU memory during the LLM run: 5922 MiB on NVIDIA GeForce RTX 4060 Laptop GPU.

Source runs: `results/evaluation/rules/20261119_222952`, `results/evaluation/llm/20261119_223915`.
