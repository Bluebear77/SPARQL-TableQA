# LLM_as_a_Judge

This directory contains the judging pipeline used to categorize modality-level inconsistencies in KONTRAST.

## Purpose

After GRASP generates SPARQL and retrieves KG answers, KONTRAST must decide whether the KG answer agrees with the original table answer. This directory provides the LLM-based judging stage for that comparison.

The judge receives triples of the form:

```text
(question, table answer, KG answer)
```

and assigns a cross-modal consistency label.

## Taxonomy

The judging pipeline uses the following labels:

| Label | Meaning |
|---|---|
| `Same` | The table and KG answers express the same fact. |
| `Higher accuracy in KG than in Table` | The KG answer is more complete, or accurate. |
| `Higher accuracy in Table than in KG` | The table answer is more complete, or accurate. |
| `Different answer` | The table answer conflicts with KG answer. |
| `Temporal changes` | The table and KG reflect different time points. |

## Contents

This directory includes:

- judged CSV files for different model outputs;
- the LLM judging script, including judeg prompt.
