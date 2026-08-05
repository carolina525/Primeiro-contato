from bcb import sgs
import pandas as pd

selic = sgs.get({'SELIC': 11}, start='2023-01-01', end='2023-12-31')
print(selic)

df = sgs.get({'IPCA': 433, 'IGP-M': 189}, start='2024-01-01')
print(df)

df_ultimos = sgs.get({'selic': 11}, last=10)
print(df_ultimos)