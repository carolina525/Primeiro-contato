"""
Parser da seção "Renda fixa > Liquidação" do Boletim Diário do Mercado (BDI) da B3.

Layout de origem
-----------------
O boletim é um PDF gigante (milhares de páginas) que muda de paginação a cada
dia. Em vez de "chutar" um número de página fixo, este parser lê o Sumário
(página 2) do próprio PDF, que lista cada seção com sua página inicial, e usa
isso para localizar exatamente onde a tabela "Liquidação" começa e termina
naquele dia específico. Isso torna o parser robusto a mudanças de tamanho do
boletim (mais ou menos ativos negociados, etc.).

A tabela "Liquidação" tem 7 colunas, sempre nesta ordem:
    Data referência | Instrumento financeiro | Data da operação |
    Tipo de operação | Modalidade de liquidação |
    Quantidade liquidada | Volume financeiro (R$)

Cada linha, quando extraída com `pdftotext -layout`, fica com os campos
separados por 2+ espaços, o que permite separar as colunas de forma confiável
mesmo com "Tipo de operação" e "Modalidade" contendo espaços internos.

Fonte de download
------------------
https://arquivos.b3.com.br/bdi/download/bdi/{AAAA-MM-DD}/BDI_{parte}_{AAAAMMDD}.pdf

A B3 mantém publicamente disponíveis apenas os últimos ~10 dias úteis nesse
endpoint (conforme comunicado oficial "Novo Boletim de Mercados B3"). Para
histórico mais antigo, será necessário outra fonte (ex.: contrato com a B3,
arquivo salvo previamente, ou a área "Pesquisa por pregão" do site, que pode
exigir sessão autenticada). O sufixo "parte" (00, 01, 02...) também pode
variar de um dia para o outro dependendo de como a B3 particiona o boletim;
por isso o downloader tenta uma lista de candidatos por data.

Requisitos
----------
    pip install pandas requests --break-system-packages
    poppler-utils (pdftotext) precisa estar instalado no sistema.

Uso
---
    python bdi_liquidacao_parser.py --pdf caminho/para/BDI_00_20260803.pdf
    python bdi_liquidacao_parser.py --start 2026-07-24 --end 2026-08-03 --out liquidacao_historico.csv
"""

from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

# --------------------------------------------------------------------------- #
# Extração de texto do PDF
# --------------------------------------------------------------------------- #

def pdftotext_layout(pdf_path: Path, first_page: int, last_page: int) -> str:
    """Roda `pdftotext -layout` para um intervalo de páginas e devolve o texto."""
    result = subprocess.run(
        [
            "pdftotext", "-layout",
            "-f", str(first_page), "-l", str(last_page),
            str(pdf_path), "-",
        ],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


# --------------------------------------------------------------------------- #
# Sumário (TOC) -> mapeamento seção -> página
# --------------------------------------------------------------------------- #

TOC_LINE_RE = re.compile(r"^\s{2,}(?P<titulo>\S.*?)\s{2,}(?P<pagina>\d+)\s*$")


def read_toc(pdf_path: Path, toc_page: int = 2) -> list[tuple[str, int]]:
    """Lê o Sumário do boletim (por padrão, página 2) e devolve
    [(titulo_da_secao, pagina_inicial), ...] na ordem em que aparecem."""
    text = pdftotext_layout(pdf_path, toc_page, toc_page)
    entries: list[tuple[str, int]] = []
    for line in text.splitlines():
        m = TOC_LINE_RE.match(line)
        if not m:
            continue
        titulo = m.group("titulo").strip()
        pagina = int(m.group("pagina"))
        # ignora o rodapé "2   REFERENTE A ..." que também bate no regex
        if "REFERENTE A" in titulo.upper():
            continue
        entries.append((titulo, pagina))
    return entries


def section_page_range(toc: list[tuple[str, int]], section_title: str) -> tuple[int, int]:
    """Dado o Sumário, devolve (pagina_inicial, pagina_final) da seção pedida.
    pagina_final é a última página antes do início da PRÓXIMA seção listada
    (que pode ter o mesmo número de página, ou uma página adiante)."""
    idx = next((i for i, (t, _) in enumerate(toc) if t == section_title), None)
    if idx is None:
        raise ValueError(
            f"Seção '{section_title}' não encontrada no Sumário. "
            f"Seções disponíveis: {[t for t, _ in toc][:10]}..."
        )
    start_page = toc[idx][1]
    end_page = start_page
    for _, pagina in toc[idx + 1:]:
        if pagina > start_page:
            end_page = pagina - 1
            break
    else:
        end_page = start_page  # última seção do sumário, sem próxima referência
    return start_page, max(end_page, start_page)


# --------------------------------------------------------------------------- #
# Parsing das linhas da tabela "Liquidação"
# --------------------------------------------------------------------------- #

COLUNAS = [
    "data_referencia",
    "instrumento_financeiro",
    "data_operacao",
    "tipo_operacao",
    "modalidade_liquidacao",
    "quantidade_liquidada",
    "volume_financeiro_reais",
]

_DATA_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")


def _parse_numero_br(valor: str) -> Optional[float]:
    """Converte número no formato BR ('1.234.567' ou '1.234,56') para float.
    Devolve None se não for um número (ex.: '-')."""
    valor = valor.strip()
    if valor in ("", "-"):
        return None
    valor = valor.replace(".", "").replace(",", ".")
    try:
        return float(valor)
    except ValueError:
        return None


def parse_liquidacao_text(texto: str, data_pregao: Optional[str] = None) -> pd.DataFrame:
    """Recebe o texto (pdftotext -layout) das páginas da seção Liquidação e
    devolve um DataFrame já tipado."""
    linhas = []
    for raw_line in texto.splitlines():
        campos = re.split(r"\s{2,}", raw_line.strip())
        if len(campos) != len(COLUNAS):
            continue
        if not _DATA_RE.match(campos[0]) or not _DATA_RE.match(campos[2]):
            continue
        linhas.append(campos)

    df = pd.DataFrame(linhas, columns=COLUNAS)
    if df.empty:
        return df

    df["data_referencia"] = pd.to_datetime(df["data_referencia"], format="%d/%m/%Y")
    df["data_operacao"] = pd.to_datetime(df["data_operacao"], format="%d/%m/%Y")
    df["quantidade_liquidada"] = df["quantidade_liquidada"].map(_parse_numero_br)
    df["volume_financeiro_reais"] = df["volume_financeiro_reais"].map(_parse_numero_br)

    if data_pregao:
        df.insert(0, "data_pregao_arquivo", pd.to_datetime(data_pregao))

    return df.reset_index(drop=True)


def parse_bdi_liquidacao(pdf_path: Path, data_pregao: Optional[str] = None) -> pd.DataFrame:
    """Ponto de entrada principal: recebe o caminho de um PDF do boletim e
    devolve o DataFrame da tabela Liquidação daquele dia."""
    pdf_path = Path(pdf_path)
    toc = read_toc(pdf_path)
    start_page, end_page = section_page_range(toc, "Liquidação")
    texto = pdftotext_layout(pdf_path, start_page, end_page)
    return parse_liquidacao_text(texto, data_pregao=data_pregao)


# --------------------------------------------------------------------------- #
# Download histórico
# --------------------------------------------------------------------------- #

BASE_URL = "https://arquivos.b3.com.br/bdi/download/bdi/{data_iso}/BDI_{parte}_{data_compacta}.pdf"

# A B3 já publicou o boletim sob sufixos diferentes (ex.: "00", "02", "02-0").
# Tentamos a lista em ordem até uma resposta 200 com conteúdo de PDF válido.
PARTES_CANDIDATAS = ["00", "01", "02", "02-0", "03"]


@dataclass
class ResultadoDownload:
    pregao: date
    caminho: Optional[Path]
    url: Optional[str]
    erro: Optional[str] = None


def baixar_bdi(pregao: date, destino_dir: Path, session: Optional[requests.Session] = None) -> ResultadoDownload:
    """Tenta baixar o boletim de um dia específico, testando os sufixos de
    parte conhecidos. Salva o primeiro PDF válido encontrado."""
    session = session or requests.Session()
    destino_dir.mkdir(parents=True, exist_ok=True)
    data_iso = pregao.strftime("%Y-%m-%d")
    data_compacta = pregao.strftime("%Y%m%d")

    ultimo_erro = None
    for parte in PARTES_CANDIDATAS:
        url = BASE_URL.format(data_iso=data_iso, parte=parte, data_compacta=data_compacta)
        try:
            resp = session.get(url, timeout=30)
        except requests.RequestException as exc:
            ultimo_erro = str(exc)
            continue

        if resp.status_code == 200 and resp.content[:4] == b"%PDF":
            caminho = destino_dir / f"BDI_{parte}_{data_compacta}.pdf"
            caminho.write_bytes(resp.content)
            return ResultadoDownload(pregao=pregao, caminho=caminho, url=url)

        ultimo_erro = f"HTTP {resp.status_code} em {url}"

    return ResultadoDownload(pregao=pregao, caminho=None, url=None, erro=ultimo_erro)


def dias_uteis(inicio: date, fim: date):
    """Gera datas de segunda a sexta entre inicio e fim (inclusive).
    Não considera feriados da B3 -- dias sem pregão simplesmente vão falhar
    no download e serão pulados com um aviso."""
    d = inicio
    while d <= fim:
        if d.weekday() < 5:  # 0=segunda ... 4=sexta
            yield d
        d += timedelta(days=1)


def loop_download_historico(
    inicio: date,
    fim: date,
    destino_dir: Path = Path("./bdi_downloads"),
    pausa_segundos: float = 1.0,
) -> pd.DataFrame:
    """Baixa e faz o parsing da tabela Liquidação para cada dia útil entre
    `inicio` e `fim`. Datas sem boletim disponível (feriado, ou fora da
    janela de retenção da B3 -- ~10 dias úteis) são puladas com aviso.

    Retorna um único DataFrame consolidado com todos os dias que deram certo.
    """
    session = requests.Session()
    dfs = []

    for pregao in dias_uteis(inicio, fim):
        resultado = baixar_bdi(pregao, destino_dir, session=session)

        if resultado.caminho is None:
            print(f"[AVISO] {pregao:%d/%m/%Y}: não foi possível baixar o boletim "
                  f"({resultado.erro}). Pulando.")
            time.sleep(pausa_segundos)
            continue

        try:
            df_dia = parse_bdi_liquidacao(resultado.caminho, data_pregao=pregao.isoformat())
            if df_dia.empty:
                print(f"[AVISO] {pregao:%d/%m/%Y}: seção 'Liquidação' não encontrada "
                      f"ou vazia no PDF baixado ({resultado.url}).")
            else:
                print(f"[OK] {pregao:%d/%m/%Y}: {len(df_dia)} registros extraídos.")
                dfs.append(df_dia)
        except Exception as exc:  # noqa: BLE001 -- log e segue para o próximo dia
            print(f"[ERRO] {pregao:%d/%m/%Y}: falha ao parsear ({exc}).")

        time.sleep(pausa_segundos)

    if not dfs:
        return pd.DataFrame(columns=["data_pregao_arquivo", *COLUNAS])

    return pd.concat(dfs, ignore_index=True)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=str, help="Caminho de um único PDF do BDI já baixado.")
    parser.add_argument("--start", type=str, help="Data inicial AAAA-MM-DD para o loop histórico.")
    parser.add_argument("--end", type=str, help="Data final AAAA-MM-DD para o loop histórico.")
    parser.add_argument("--downloads-dir", type=str, default="./bdi_downloads",
                         help="Onde salvar os PDFs baixados.")
    parser.add_argument("--out", type=str, default="liquidacao.csv",
                         help="Caminho do CSV de saída.")
    args = parser.parse_args()

    if args.pdf:
        df = parse_bdi_liquidacao(Path(args.pdf))
    elif args.start and args.end:
        inicio = date.fromisoformat(args.start)
        fim = date.fromisoformat(args.end)
        df = loop_download_historico(inicio, fim, destino_dir=Path(args.downloads_dir))
    else:
        parser.error("Use --pdf OU --start/--end.")
        return

    print(df.head())
    print(f"\nTotal de linhas: {len(df)}")
    df.to_csv(args.out, index=False)
    print(f"Salvo em {args.out}")


if __name__ == "__main__":
    _main()