from bcb import sgs

# Buscar taxa Selic (código 1)
df = sgs.get(1, start="2023-01-01", end="2024-12-31")
print(df.head())

from bcb import currency

# Buscar preços de compra/venda do USD
usd = currency.get("USD", start="2023-01-01", end="2024-12-31")
print(usd.head())

from bcb import Expectativas

api = Expectativas()
endpoint = api.get_endpoint("ExpectativasMercadoAnuais")

# Obter previsões do IPCA
df = endpoint.query().filter(endpoint.Indicador == "IPCA").limit(100).collect()
print(df.head())