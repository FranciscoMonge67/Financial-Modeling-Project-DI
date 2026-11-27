"""
DADOS SINTÉTICOS DE TESTE: NÃO SÃO RESULTADOS DO BACKTEST.

Gera ficheiros com o mesmo formato que a célula "F.4 Exportação para a app" do notebook,
só para testar a app antes de existirem os dados reais. O meta.json fica com
"synthetic": true e a app mostra um aviso bem visível.

Uso (a partir da pasta app/):  python tools/make_synthetic_data.py
"""
import json
import os

import numpy as np
import pandas as pd

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(2026)

PROFILES = ['conservative', 'moderate', 'aggressive']
BENCH_W = {'conservative': 0.30, 'moderate': 0.60, 'aggressive': 0.80}
SAT = {'conservative': 0.05, 'moderate': 0.10, 'aggressive': 0.20}
ETFS = ['SPY', 'VGK', 'EEM', 'VNQ', 'IEF', 'LQD', 'GLD', 'DBC']
dates = pd.date_range('2011-01-01', '2026-10-01', freq='MS')
n = len(dates)

# taxa sem risco anual aproximada por regime (só para parecer realista)
rf_ann = np.interp(np.arange(n), [0, 59, 96, 110, 132, 148, 156, 168, n - 1],
                   [0.0005, 0.0005, 0.023, 0.001, 0.0005, 0.045, 0.053, 0.050, 0.040])
rf = np.log(1 + rf_ann) / 12

cov = np.array([[0.15 ** 2, 0.15 * 0.045 * 0.1], [0.15 * 0.045 * 0.1, 0.045 ** 2]]) / 12
eq_bd = rng.multivariate_normal([0.10 / 12, 0.025 / 12], cov, size=n)
spy, agg = eq_bd[:, 0], eq_bd[:, 1]
sp500tr = spy + rng.normal(0, 0.001, n)

ret = pd.DataFrame(index=dates)
turn = pd.DataFrame(index=dates)
for p in PROFILES:
    w = BENCH_W[p]
    bench = np.log(w * np.exp(spy) + (1 - w) * np.exp(agg))
    ret[f'bench_{p}'] = bench
    for v, alpha, te in [('fixo', 0.006, 0.020), ('adaptativo', 0.004, 0.024)]:
        te = te * (0.6 + w)
        ret[f'strat_{p}_{v}'] = bench + alpha / 12 + rng.normal(0, te / np.sqrt(12), n)
        turn[f'{p}_{v}'] = np.clip(rng.normal(0.04 + 0.5 * SAT[p], 0.02, n), 0, None)
ret['sp500tr'] = sp500tr
ret['rf'] = rf
turn.iloc[0] = np.nan
ret.index.name = turn.index.name = 'date'
ret.to_csv(os.path.join(OUT, 'returns.csv'))
turn.to_csv(os.path.join(OUT, 'turnover.csv'))

# histórico de pesos (carteira total): ETFs do core + RF + satélite
rows = []
base = np.array([0.22, 0.08, 0.06, 0.06, 0.25, 0.15, 0.12, 0.06])
drift = np.cumsum(rng.normal(0, 0.03, (n, len(ETFS))), axis=0)
tan = np.clip(base * np.exp(drift - drift.mean(0)), 0, None)
tan = np.minimum(tan / tan.sum(1, keepdims=True), 0.40)
tan = tan / tan.sum(1, keepdims=True)
k_by = {'conservative': 0.55, 'moderate': 1.10, 'aggressive': 1.40}
for p in PROFILES:
    s = SAT[p]
    k = np.clip(k_by[p] + rng.normal(0, 0.05, n), 0, {'conservative': 1, 'moderate': 1.2, 'aggressive': 1.5}[p])
    for i, d in enumerate(dates):
        for j, e in enumerate(ETFS):
            rows.append([d, p, e, (1 - s) * k[i] * tan[i, j]])
        rows.append([d, p, 'RF', (1 - s) * (1 - k[i])])
        rows.append([d, p, 'SATELLITE', s])
wh = pd.DataFrame(rows, columns=['date', 'profile', 'item', 'weight'])
wh.to_csv(os.path.join(OUT, 'weights_history.csv'), index=False)

# alocação proposta para o mês seguinte ao último dado
last = wh[wh['date'] == dates[-1]].pivot(index='item', columns='profile', values='weight')
last = last.loc[ETFS + ['RF', 'SATELLITE'], PROFILES]
last.index.name = 'item'
last.to_csv(os.path.join(OUT, 'allocation.csv'))

meta = {
    'synthetic': True,
    'note': 'DADOS SINTÉTICOS DE TESTE: gerados por tools/make_synthetic_data.py, não são resultados do backtest.',
    'generated_at': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M'),
    'backtest_start': '2011-01-01',
    'test_start': '2019-01-01',
    'last_return_month': dates[-1].strftime('%Y-%m-%d'),
    'allocation_month': '2026-11-01',
    'macro': {'high_inflation': False, 'inverted_curve': False},
    'satellite_stocks': ['AAAA', 'BBBB', 'CCCC', 'DDDD', 'EEEE', 'FFFF', 'GGGG', 'HHHH', 'IIII', 'JJJJ'],
    'satellite_size': SAT,
    'benchmark_weights': {p: [BENCH_W[p], round(1 - BENCH_W[p], 2)] for p in PROFILES},
    'leverage_cap': {'conservative': 1.0, 'moderate': 1.2, 'aggressive': 1.5},
}
with open(os.path.join(OUT, 'meta.json'), 'w', encoding='utf-8') as f:
    json.dump(meta, f, ensure_ascii=False, indent=2)
print('Dados SINTÉTICOS escritos em', os.path.abspath(OUT))
