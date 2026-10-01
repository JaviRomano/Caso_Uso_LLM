# Proyecto original (congelado)

Código del primer intento (commit `7dd03b7`, tag `v1-original`). Se conserva para compararlo con el remake y citarlo; **no se ejecuta ni se modifica**.

- Las métricas de `readme.md` no son válidas: el dataset se sobremuestreó antes del split y el 50,8 % del test aparece literal en train. La fuga se reproduce en [../reports/data_report.md](../reports/data_report.md) (§5).
- Sus rutas son relativas a la antigua raíz (`data/Balanced_AHR.csv`, `models/`). El CSV está ahora en `../data/raw/Balanced_AHR.csv`.
- `models/` solo contiene configs y tokenizers, sin pesos.
