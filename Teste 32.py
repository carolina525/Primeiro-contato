import matplotlib.pyplot as plt
from bcb import currency, sgs

# 1. Baixar dados do SGS (Selic, CDI, IPCA) e PTAX (Dólar)
df_sgs = sgs.get({"Selic": 11, "CDI": 12, "IPCA": 433}, start="2023-01-01",end='2026-08-01')
df_ptax = currency.get(["USD"], start="2023-01-01",end = '2026-08-01')

# 2. Juntar em um único DataFrame e limpar nulos
dados = df_sgs.join(df_ptax, how="inner").dropna()

# 3. Gerar gráfico simples
dados.plot(subplots=True, figsize=(10, 8), grid=True, title="Indicadores Econômicos - BCB")
plt.tight_layout()
plt.show()
