# Output_GRASP

This directory contains the Text-to-SPARQL outputs used by KONTRAST to surface cross-modal knowledge differences.

## Purpose

KONTRAST compares table-grounded answers with knowledge graph answers. This directory stores the intermediate evidence that makes that comparison possible:

- generated SPARQL queries;
- Wikidata execution results;
- model reasoning traces;
- valid and invalid cases;
- per-model statistics;
- taxonomy preparation files.


## Scripts

The `script/` folder contains utilities for cleaning and consolidating outputs, including scripts for:

- detecting unusually large KG result sets;
- merging taxonomy annotations;
- patching empty-SPARQL edge cases;
- sorting taxonomy outputs.

## How this directory connects to the experiment

This directory is the bridge between Table-QA and inconsistency labeling. It converts table questions into KG-side answers. The resulting table-answer versus KG-answer pairs are then judged in:

```text
LLM_as_a_Judge/
```

Final merged labels are stored in:

```text
Modality_inconsistency_labelled/
```


## JSON output Structure
```
root
 ├─ type : string
 ├─ task : string
 ├─ output : object
 │   ├─ sparql : string
 │   ├─ kg : string
 │   ├─ selections : string
 │   ├─ result : string
 │   ├─ endpoint : uri
 │   ├─ type : string
 │   ├─ answer : string (appears when there is a valid SPARQL execution)
 │   ├─ explanation : string (appears when there is no valid SPARQL execution)
 │   └─ formatted : string (final LLM response)
 ├─ elapsed : number
 ├─ error : string | null
 ├─ messages : Message[]
 ├─ known : string[]
 ├─ id : string
 ├─ source_csv : string
 ├─ row_index : integer
 ├─ question : string
 └─ reference_answer : string
```



