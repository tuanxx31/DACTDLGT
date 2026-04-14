# Paper-Style VRPCC Datasets (from Solomon)

This repository now includes reproducible VRPCC datasets generated from Solomon benchmark coordinates, following the computational-data description in Section 4 of:

- `2.An Approximation Algorithm for Vehicle Routing with Compatibility Constraints∗.pdf`
- Optimization-Online preprint: `https://optimization-online.org/wp-content/uploads/2018/06/6645.pdf`

## What was matched to the paper

- Node locations are taken from Solomon benchmark text files (R/C/RC categories).
- Distance matrix is Euclidean, symmetric, and uses minimum edge length `>= 1`.
- Compatibility matrix is generated randomly:
  - tight: `p = 0.3`
  - relaxed: `p = 0.7`
- Naming format follows paper style: `type-nXX-kYY`.

## Generated suites

- `MIP/data_paper_101/`
  - Matches the large-size suite (up to `n101`) used in the 101-node tables.
  - `tight/` and `relaxed/` each contain:
    - `c-n21-k6, c-n41-k10, c-n61-k14, c-n81-k18, c-n101-k22`
    - `r-n21-k6, r-n41-k10, r-n61-k14, r-n81-k18, r-n101-k22`
    - `RC-n21-k6, RC-n41-k10, RC-n61-k14, RC-n81-k18, RC-n101-k22`
- `MIP/data_paper_26/`
  - Matches the small-size suite (up to `n26`) used in the 26-node tables.
  - `tight/` and `relaxed/` each contain:
    - `c-n11-k4, c-n16-k4, c-n21-k6, c-n26-k6`
    - `r-n11-k4, r-n16-k4, r-n21-k6, r-n26-k6`
    - `RC-n11-k4, RC-n16-k4, RC-n21-k6, RC-n26-k6`

Each suite includes `manifest.json` and `manifest.csv` with full provenance:

- source subset (`25`, `50`, `100/txt`)
- source file (`c101.txt`, `r101.txt`, `rc101.txt`)
- seed
- output path

## Solomon source mapping used

Per requested mapping:

- `n21` from 25-customer set
- `n41` from 50-customer set
- `n61`, `n81`, `n101` from 100-customer set

For the small suite (`n11`, `n16`, `n21`, `n26`), source is 25-customer set.

Canonical category files used:

- C -> `c101.txt`
- R -> `r101.txt`
- RC -> `rc101.txt`

## Important reproducibility note

The paper specifies random compatibility generation (`p=0.3/0.7`) but does not publish original random seeds and exact sampled-node procedure in full detail.  
Therefore, this dataset is **paper-style reproducible** (same generation rules and source family), with deterministic fixed seeds documented in manifests; it is not a guaranteed bit-for-bit copy of the authors' hidden raw instances.

## Regenerate

From repo root:

```powershell
python MIP/instancegen_paper.py --clean
```

Useful options:

- `--skip-26` or `--skip-101`
- `--tight-only` or `--relaxed-only`
- `--solomon-root raw_data/solomon`
