# Solomon Raw Dataset (provenance-first)

Prepared on: 2026-04-14
Workspace: `D:/Hoc/DACTDLGT`

## 1. Source links used

- Solomon benchmark overview:
  - https://www.sintef.no/projectweb/top/vrptw/solomon-benchmark/
- 25 customers:
  - https://www.sintef.no/projectweb/top/vrptw/25-customers/
- 50 customers:
  - https://www.sintef.no/projectweb/top/vrptw/50-customers/
- 100 customers:
  - https://www.sintef.no/projectweb/top/vrptw/100-customers/
- Documentation (text format):
  - https://www.sintef.no/projectweb/top/vrptw/documentation2/
- Backup archive used for full 100-customer text set:
  - https://www.sintef.no/globalassets/project/top/vrptw/solomon/solomon-100.zip

## 2. External instance-definition link handling (required fallback)

The `25-customers` and `50-customers` pages point to:
- http://web.cba.neu.edu/~msolomon/problems.htm

From this environment, that external link timed out. Per SINTEF page guidance, the backup source was used (`solomon-100.zip`) and then processed into `25` and `50` subsets.

Probe log is saved at:
- `raw_data/solomon/sources/external_link_check.txt`

## 3. Folder layout

- `raw_data/solomon/100/solomon-100.zip`
  - downloaded backup archive
- `raw_data/solomon/100/txt/*.txt` (56 files)
  - extracted Solomon 100-customer text instances (no content edits)
- `raw_data/solomon/25/*.txt` (56 files)
  - derived as first 25 customers from each 100-customer file
- `raw_data/solomon/50/*.txt` (56 files)
  - derived as first 50 customers from each 100-customer file
- `raw_data/solomon/sized/n21/*.txt` (56 files)
- `raw_data/solomon/sized/n41/*.txt` (56 files)
- `raw_data/solomon/sized/n61/*.txt` (56 files)
- `raw_data/solomon/sized/n81/*.txt` (56 files)
- `raw_data/solomon/sized/n101/*.txt` (56 files)
  - mapped sets for your requested paper-size convention
- `raw_data/solomon/sources/*.html`
  - saved source-page snapshots
- `raw_data/solomon/source_manifest.csv`
  - per-file provenance table (which file came from which source)

## 4. Parsing rule used (from SINTEF documentation page)

Documentation states the text layout has:
- instance name
- VEHICLE block (NUMBER, CAPACITY)
- CUSTOMER table with columns:
  - `CUST NO., XCOORD., YCOORD., DEMAND, READY TIME, DUE DATE, SERVICE TIME`

Processing logic:
- Parse customer rows as 7 integer fields per row.
- Keep depot row (`CUST NO. = 0`) always.
- Build subsets by keeping rows `0..N` according to target set size.

## 5. Requested size mapping and assumptions

Requested mapping was applied as:
- `n21` from 25-customer set -> keep `CUST NO. 0..20` (21 nodes total)
- `n41` from 50-customer set -> keep `CUST NO. 0..40` (41 nodes total)
- `n61` from 100-customer set -> keep `CUST NO. 0..60` (61 nodes total)
- `n81` from 100-customer set -> keep `CUST NO. 0..80` (81 nodes total)
- `n101` from 100-customer set -> keep `CUST NO. 0..100` (101 nodes total)

Assumption made explicit:
- `nXX` is interpreted as total nodes including depot.

## 6. File-to-source traceability

Use:
- `raw_data/solomon/source_manifest.csv`

This manifest includes, for every file in this dataset bundle:
- local path
- artifact type (downloaded, extracted, derived)
- source URL
- source artifact (zip entry or upstream file)
- exact mapping/derivation rule
- notes/assumptions
