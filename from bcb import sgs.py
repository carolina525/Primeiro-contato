from bcb import sgs

# único código → str
raw = sgs.get(433, start='2024-01-01', output='text')

# múltiplos códigos → dict[int, str]
raws = sgs.get([433, 189], start='2024-01-01', output='text')
# raws[433] → JSON string do IPCA
# raws[189] → JSON string do IGP-M

# salvar em disco
with open('ipca_raw.json', 'w') as f:
    f.write(raw)