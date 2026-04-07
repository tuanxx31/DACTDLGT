# VRPCC Reproduction Guide

Huong dan nhanh de:
- Tao instance theo kich thuoc paper (`n21-k6`, `n41-k10`, `n61-k14`, ...)
- Chay so sanh MIP (10 phut + 2 gio) va thuat toan approximation
- Xuat bang CSV de doi chieu voi bai bao

## 1) Moi truong

Dung Python trong virtual environment cua project:

```powershell
& D:/Hoc/DACTDLGT/.venv/Scripts/Activate.ps1
```

Neu can, cai dependencies:

```powershell
python -m pip install -r requirements.txt
```

Kiem tra `gurobipy`:

```powershell
python -c "import gurobipy as gp; print(gp.gurobi.version())"
```

## 2) Tao instance MIP theo kich thuoc tuy y

Script: `MIP/instancegen.py`

### Tao 1 kich thuoc (vi du n41-k10)

```powershell
python MIP/instancegen.py --size 41:10
```

### Tao nhieu kich thuoc cung luc

```powershell
python MIP/instancegen.py --size 21:6 --size 41:10 --size 61:14 --size 81:18 --size 101:22
```

Format `--size`:
- `n_customers:n_vehicles`
- Vi du `41:10` tuong ung `n41-k10`

Output:
- `MIP/data/...` (tight compatibility, p=0.3)
- `MIP/data2/...` (relaxed compatibility, p=0.7)
- Moi size co du 3 layout: `c`, `r`, `RC`

## 3) Chay so sanh theo format bang paper

Script: `scripts/run_comparison.py`

### Chay nhanh bo nhe mac dinh (n21-k6)

```powershell
python scripts/run_comparison.py --mip-limit-1 600 --mip-limit-2 7200 --out-dir output_runs
```

### Chay mot bo cu the (vi du n41-k10, tight)

```powershell
python scripts/run_comparison.py `
  --instance "MIP/data/c-n41-k10/c-n41-k10.json" `
  --instance "MIP/data/r-n41-k10/r-n41-k10.json" `
  --instance "MIP/data/RC-n41-k10/RC-n41-k10.json" `
  --mip-limit-1 600 --mip-limit-2 7200 `
  --out-dir output_runs_n41k10
```

### Chi chay thuat toan (bo qua MIP)

```powershell
python scripts/run_comparison.py --skip-mip --out-dir output_runs_algo_only
```

## 4) Dinh nghia cac cot trong CSV

File ket qua chinh: `comparison_table.csv`

- `LB1`, `UB1`, `Time_10min_s`: MIP voi time limit lan 1
- `LB2`, `UB2`, `Time_2hours_s`: MIP voi time limit lan 2
- `Obj`: gia tri objective cua thuat toan = `max(route_costs)`
- `Time_algo_s`: thoi gian chay thuat toan
- `Obj_over_LB2`, `Obj_over_UB2`: ti le doi chieu theo bai bao

## 5) Luu y ve license Gurobi

- Mot so instance lon (thuong la `RC` o kich thuoc cao) co the vuot qua gioi han size-limited license.
- Script da duoc lam robust: neu 1 instance loi MIP, batch van tiep tuc, CSV van duoc ghi.
- Khi bi gioi han license, cac cot MIP cua instance do se la `-`.

## 6) File output quan trong

- `OUT_DIR/summary.json`: du lieu day du cho moi instance
- `OUT_DIR/comparison_table.csv`: bang tong hop de dua vao bao cao/so sanh
- `OUT_DIR/approx_algorithm.log`: trace qua trinh approximation

