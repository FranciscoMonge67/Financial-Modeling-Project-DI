# Perfil de investidor: estratégia core + satélite (Financial Modeling, Nova SBE)

**▶ App:** `PREENCHER_URL_DA_APP` (Streamlit Community Cloud)
**📓 Notebook do backtest:** [`Projeto_FM_notebook.ipynb`](Projeto_FM_notebook.ipynb)

App Streamlit open source que acompanha o nosso projeto de Financial Modeling. O utilizador responde a um questionário de
10 perguntas, a app sugere um perfil de risco (conservador, moderado ou agressivo), o utilizador aceita-o ou escolhe outro,
e vê como a carteira desse perfil se teria comportado desde 2011 contra o seu benchmark.

## O que a app mostra

- **Questionário e perfil sugerido.** Cada resposta vale 1 a 4 pontos (nas perguntas 6 e 7, opção segura = 1 e opção com
  risco = 4). Soma 10-19 = conservador, 20-30 = moderado, 31-40 = agressivo. A decisão final é sempre do utilizador.
  As perguntas estão em [`questionario_risco.md`](questionario_risco.md).
- **Performance histórica:** valor de 1 € investido, contra o benchmark do perfil (30/70, 60/40 ou 80/20 de SPY/AGG) e o
  S&P 500 TR; drawdown e retorno por ano civil.
- **Estatísticas:** retorno e volatilidade anuais, Sharpe, information ratio, alpha, beta, máximo drawdown e turnover,
  para 2011-2026, 2011-2018 e 2019-2026, com o satélite fixo (caso base) ou adaptativo.
- **Alocação atual:** core por ETF, satélite (e as ações escolhidas) e T-bills, e a evolução dos pesos ao longo do tempo.
- **Simulador "e se tivesse investido?":** escolhe-se um montante e um mês de entrada (entre o início do backtest e o
  último mês com dados) e a app mostra quanto valeria hoje com a estratégia do perfil e com o benchmark, em € e em %,
  com o gráfico da evolução. Usa só os retornos históricos de `data/returns.csv`, sem custos nem impostos.
- **Comparação dos três perfis.**

## A estratégia, em resumo

- **Core:** 8 ETFs (ações EUA, Europa, emergentes, imobiliário; Tesouro e obrigações de empresas; ouro; matérias-primas).
  Todos os meses, a carteira tangente de Markowitz com os últimos 60 meses (médias encolhidas, máximo 40% por ETF).
- **Perfil:** cada perfil mistura a tangente com T-bills até à volatilidade do seu benchmark (capital market line);
  o moderado pode alavancar até 1,2× e o agressivo até 1,5×.
- **Satélite (5%, 10%, 20%):** as 10 small caps do S&P 600 com maior momentum 6-1.

Os detalhes, as fórmulas e as limitações estão no notebook.

## Como funciona

A app **não descarrega dados nem corre o backtest**: lê os resultados que o notebook exporta (secção F.4) para a pasta
`data/`. As métricas são calculadas na app com as mesmas fórmulas do notebook (secção E.3).

```
app.py                       # a app
requirements.txt             # dependências
.streamlit/config.toml       # tema escuro
data/                        # resultados exportados do notebook (secção F.4)
  returns.csv                #   retornos log mensais: estratégias, benchmarks, S&P 500 TR, rf
  turnover.csv               #   turnover mensal de cada estratégia
  weights_history.csv        #   pesos da carteira total em cada mês
  allocation.csv             #   alocação proposta para o mês seguinte aos dados
  meta.json                  #   datas, ações do satélite; "synthetic": true/false
tools/
  notebook_export_cell.py    # cópia da célula F.4 do notebook
  make_synthetic_data.py     # gera dados SINTÉTICOS de teste com o mesmo formato
questionario_risco.md        # as 10 perguntas e a pontuação
Projeto_FM_notebook.ipynb    # o backtest (acrescentar a versão final)
LICENSE                      # MIT
```

Todos os dados usados são públicos (Yahoo Finance, FRED e a lista de holdings do ETF IJR da iShares). O repositório não
tem chaves, palavras-passe nem dados pessoais.

## Correr localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

Abre em http://localhost:8501. Funciona com Streamlit 1.32 ou mais recente (também no Anaconda; se der erro, atualizar
com `pip install -U streamlit plotly`).

## Atualizar os dados

1. Abrir o notebook no Google Colab e fazer *Runtime → Run all*.
2. A secção **F.4** descarrega `app_data.zip` (se o browser bloquear, está no painel de ficheiros do Colab).
3. Descompactar e copiar os 5 ficheiros para `data/`, por cima dos atuais.
4. Confirmar que `data/meta.json` tem `"synthetic": false`; o aviso laranja no topo da app desaparece.

---

## Para o grupo: publicar e entregar (apagar esta secção no fim, se quiserem)

**1. Dados reais.** Enquanto `data/meta.json` disser `"synthetic": true`, a app mostra o aviso de dados de teste.
Fazer primeiro "Atualizar os dados" (acima) e copiar o notebook final para esta pasta.

**2. Repositório público no GitHub.**
1. Em https://github.com/new: nome, por exemplo `fm-perfil-investidor`; **Public**; sem README; *Create repository*.
2. Enviar a pasta toda, de uma de duas formas:
   - **Browser:** *uploading an existing file* e arrastar **o conteúdo** da pasta (incluindo `.streamlit`, `data`,
     `tools`, `LICENSE`, `.gitignore`); *Commit changes*. No Mac, a pasta `.streamlit` está escondida: no Finder,
     `Cmd + Shift + .` mostra-a. Confirmar que `.streamlit/config.toml` aparece no repositório.
   - **Terminal:**
     ```bash
     cd pasta-da-app
     git init -b main
     git add .
     git commit -m "App Streamlit de perfil de investidor"
     git remote add origin https://github.com/<utilizador>/fm-perfil-investidor.git
     git push -u origin main
     ```

**3. Deploy no Streamlit Community Cloud (grátis).**
1. https://share.streamlit.io → **Continue with GitHub** → autorizar.
2. *Create app* → *Deploy a public app from GitHub*.
3. **Repository** `<utilizador>/fm-perfil-investidor`, **Branch** `main`, **Main file path** `app.py`,
   **App URL** por exemplo `fm-perfil-investidor`.
4. *Advanced settings* → Python 3.12 (não há secrets). *Deploy*. Demora 1-3 minutos.
5. Cada `git push` atualiza a app sozinha.

**4. Antes de entregar.**
- Abrir os dois links numa **janela anónima**: o repositório tem de ser público e a app visível para todos
  (*Settings → Sharing → "This app is public"*).
- Fazer o questionário até ao fim e confirmar que não aparece o aviso de dados sintéticos.
- Pôr os dois URLs no prospeto, no notebook (primeira célula) e no topo deste README (`PREENCHER_URL_DA_APP`).
- As apps grátis adormecem após alguns dias sem visitas: abrir a app na véspera da avaliação e, se pedir,
  carregar em *Yes, get this app back up*.

---

Resultados passados não garantem resultados futuros. Isto é um trabalho académico, não aconselhamento financeiro.
Licença [MIT](LICENSE).
