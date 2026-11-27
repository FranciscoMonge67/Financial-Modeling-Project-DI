# ===== F.4 Exportação dos resultados para a app Streamlit =====
# Cópia da célula F.4 do notebook (depois da F.3). Corre no fim do notebook.
import os, json, shutil                                        # NÃO DADO NAS AULAS: os/json/shutil para escrever ficheiros

EXPORT_DIR = 'app_data'                                        # no Colab fica em /content/app_data
os.makedirs(EXPORT_DIR, exist_ok=True)

# 1) retornos log mensais: estratégias (2 versões do satélite), benchmarks, S&P 500 TR e rf
out = pd.DataFrame(index=hold_months)
for profile in PROFILES:
    out[f'bench_{profile}'] = benchmark_rets[profile]
    for version in ['fixo', 'adaptativo']:
        out[f'strat_{profile}_{version}'] = strategy_rets[f'{profile} ({version})']
out['sp500tr'] = benchmark_rets['S&P 500 TR']
out['rf'] = rf_hold.loc[hold_months]
out.index.name = 'date'
out.to_csv(f'{EXPORT_DIR}/returns.csv')

# 2) turnover mensal de cada estratégia
turn = strategy_turnover.copy()
turn.columns = [c.replace(' (', '_').replace(')', '') for c in turn.columns]   # 'moderate (fixo)' -> 'moderate_fixo'
turn.index.name = 'date'
turn.to_csv(f'{EXPORT_DIR}/turnover.csv')

# 3) histórico de pesos da carteira total: (1 - satélite) x core (ETFs + RF) + satélite
rows = []
for profile in PROFILES:
    s = SATELLITE_SIZE[profile]
    w = (1 - s) * core_weights[profile][CORE_ETFS + ['RF']].fillna(0)
    w['SATELLITE'] = s
    long = w.stack().reset_index()                             # NÃO DADO NAS AULAS: stack passa a tabela para formato longo
    long.columns = ['date', 'item', 'weight']
    long['profile'] = profile
    rows.append(long)
pd.concat(rows)[['date', 'profile', 'item', 'weight']].to_csv(f'{EXPORT_DIR}/weights_history.csv', index=False)

# 4) alocação proposta (F.3), com nomes curtos nas linhas
alloc = allocation.copy()
alloc.index = CORE_ETFS + ['RF', 'SATELLITE']
alloc.index.name = 'item'
alloc.to_csv(f'{EXPORT_DIR}/allocation.csv')

# 5) metadados: datas, ações do satélite (e regras macro ativas, se existirem)
meta = {
    'synthetic': False,
    'note': 'Resultados exportados do notebook (secção F.4).',
    'generated_at': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M'),
    'backtest_start': BACKTEST_START,
    'test_start': TEST_START,
    'last_return_month': hold_months[-1].strftime('%Y-%m-%d'),
    'allocation_month': END_DATE,
    'satellite_stocks': list(sat_now[sat_now > 0].index),
    'satellite_size': SATELLITE_SIZE,
    'benchmark_weights': {p: list(BENCHMARK_WEIGHTS[p]) for p in PROFILES},
    'leverage_cap': LEVERAGE_CAP,
}
if 'caps_now' in globals():                                    # só se o notebook tiver regras macro (F.3)
    meta['macro'] = {'high_inflation': bool(caps_now['bonds'] < CLASS_CAPS_BASE['bonds']),
                     'inverted_curve': bool(caps_now['equity'] < CLASS_CAPS_BASE['equity'])}
with open(f'{EXPORT_DIR}/meta.json', 'w', encoding='utf-8') as f:
    json.dump(meta, f, ensure_ascii=False, indent=2)

shutil.make_archive('app_data', 'zip', EXPORT_DIR)            # app_data.zip para descarregar de uma vez
print('Ficheiros exportados:', sorted(os.listdir(EXPORT_DIR)))
try:
    from google.colab import files                             # só existe no Colab: descarrega o zip automaticamente
    files.download('app_data.zip')
except ImportError:
    print('Fora do Colab: copiar a pasta app_data/ para app/data/ do repositório.')
