from bcb import sgs

import matplotlib.pyplot as plt

import matplotlib as mpl

mpl.style.use('bmh')

df = sgs.get({'IPCA': 433}, start='2002-02-01')

df.index = df.index.to_period('M')

print(df.head())

dfr = df.rolling(12)

i12 = dfr.apply(lambda x: (1 + x/100).prod() - 1).dropna() * 100

print(i12.head())

i12.plot(figsize=(12,6))


plt.title('Fonte: https://dadosabertos.bcb.gov.br', fontsize=10)
#Text(0.5, 1.0, 'Fonte: https://dadosabertos.bcb.gov.br')

plt.suptitle('IPCA acumulado 12 meses - Janela Móvel', fontsize=18)
#Out[15]: Text(0.5, 0.98, 'IPCA acumulado 12 meses - Janela Móvel')

plt.xlabel('Data')
#Out[16]: Text(0.5, 0, 'Data')

plt.ylabel('%')
#Out[17]: Text(0, 0.5, '%') 
plt.legend().set_visible(False)