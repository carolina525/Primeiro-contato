from bcb import sgs
import pandas as pd

# Exemplo: Buscando a taxa Selic diária (Código: 11)
# Você pode passar strings de data no formato 'AAAA-MM-DD'
df_selic = sgs.get({'selic': 11}, start='2025-01-01', end='2026-01-01')

print(df_selic.head())


