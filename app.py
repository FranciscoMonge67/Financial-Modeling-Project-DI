"""
App Streamlit do projeto de Financial Modeling (Nova SBE).

Fluxo: o utilizador responde a 10 perguntas, a app sugere um perfil de risco, o utilizador
aceita ou escolhe outro, e vê a performance histórica da carteira desse perfil contra o seu
benchmark (30/70, 60/40 ou 80/20), as estatísticas e a alocação mais recente.

A app não descarrega dados: lê os resultados exportados pelo notebook (secção F.4) da
pasta data/. As métricas usam as mesmas fórmulas do notebook (secção E.3).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DATA_DIR = Path(__file__).parent / 'data'


def _st_version():
    try:
        return tuple(int(x) for x in st.__version__.split('.')[:2])
    except ValueError:
        return (0, 0)


# Compatibilidade entre versões do Streamlit: as recentes usam width='stretch', as antigas
# use_container_width=True (que nas recentes está obsoleto). Usar sempre **FULL nos elementos.
FULL = {'width': 'stretch'} if _st_version() >= (1, 50) else {'use_container_width': True}

def L(values):
    # Listas simples nos gráficos: o plotly 6+ codifica arrays numpy em base64, que as versões
    # antigas do Streamlit não sabem ler (os gráficos apareciam como retas 0, 1, 2, ...).
    return [None if (isinstance(v, float) and np.isnan(v)) else v for v in list(values)]


# ------------------------------------------------------------------------------------------
# Identidade visual: fundo escuro, acentos neon. As cores dos gráficos foram validadas para
# fundo escuro (banda de luminosidade e separação para daltonismo); o benchmark é tracejado
# para não depender só da cor.
# ------------------------------------------------------------------------------------------
BG = '#0B0F1A'
PANEL = '#121829'
GRID = '#1E2740'
TEXT = '#E6EAF5'
MUTED = '#8C96B3'
C_STRAT = '#00AED0'    # ciano: estratégia
C_BENCH = '#FF3EA5'    # magenta: benchmark do perfil
C_SPX = '#64B21A'      # lima: S&P 500 TR
C_ALT = '#A879FF'      # violeta: versão alternativa / extra
C_ORANGE = '#E8780C'
NEON_CYAN = '#00F0FF'  # só para títulos e brilhos, nunca para marcas de dados
NEON_PINK = '#FF2BD6'

PROFILES = ['conservative', 'moderate', 'aggressive']
PROFILE_PT = {'conservative': 'Conservador', 'moderate': 'Moderado', 'aggressive': 'Agressivo'}
PROFILE_COLOR = {'conservative': C_STRAT, 'moderate': C_ALT, 'aggressive': C_BENCH}
PROFILE_BLURB = {
    'conservative': 'Dás prioridade a preservar o capital. A carteira procura a volatilidade de um 30/70 '
                    '(30% ações, 70% obrigações), sem alavancagem, com 5% no satélite de small caps.',
    'moderate': 'Aceitas oscilações moderadas em troca de mais retorno. A carteira procura a volatilidade de um '
                '60/40, pode alavancar até 1,2× o core e põe 10% no satélite.',
    'aggressive': 'Procuras crescimento e toleras perdas grandes pelo caminho. A carteira procura a volatilidade de '
                  'um 80/20, pode alavancar até 1,5× o core e põe 20% no satélite.',
}
BANDS = {'conservative': (10, 19), 'moderate': (20, 30), 'aggressive': (31, 40)}

ETF_INFO = {
    'SPY': ('Ações EUA (S&P 500)', 'Ações'), 'VGK': ('Ações Europa', 'Ações'),
    'EEM': ('Ações emergentes', 'Ações'), 'VNQ': ('Imobiliário EUA (REITs)', 'Ações'),
    'IEF': ('Tesouro EUA 7-10 anos', 'Obrigações'), 'LQD': ('Obrigações de empresas IG', 'Obrigações'),
    'GLD': ('Ouro', 'Ativos reais'), 'DBC': ('Matérias-primas', 'Ativos reais'),
    'RF': ('T-bills (negativo = empréstimo)', 'Sem risco'),
    'SATELLITE': ('Satélite: small caps de momentum', 'Satélite'),
}
CLASS_COLOR = {'Ações': C_STRAT, 'Obrigações': C_ALT, 'Ativos reais': C_ORANGE, 'Satélite': C_BENCH,
               'Sem risco': '#5B6582'}

# ------------------------------------------------------------------------------------------
# Questionário (aprovado pelo grupo). Cada opção vale 1 a 4 pontos pela ordem; nas perguntas
# 6 e 7 a opção segura vale 1 e a opção com risco vale 4.
# ------------------------------------------------------------------------------------------
QUESTIONS = [
    ('Parte 1 · Autoclassificação', 'Como te descreverias como investidor?',
     [('Só quero preservar o capital', 1), ('Aceito pequenas perdas', 2),
      ('Aceito perdas moderadas por mais retorno', 3), ('Procuro o retorno máximo', 4)]),
    ('Parte 1 · Autoclassificação', 'Qual a tua experiência a investir?',
     [('Nenhuma', 1), ('Poupanças e depósitos', 2), ('Fundos ou ETFs', 3), ('Ações e outros produtos', 4)]),
    ('Parte 1 · Autoclassificação', 'Qual é o teu horizonte de investimento?',
     [('Menos de 2 anos', 1), ('2 a 5 anos', 2), ('5 a 10 anos', 3), ('Mais de 10 anos', 4)]),
    ('Parte 1 · Autoclassificação', 'Qual o peso desta carteira na tua poupança total?',
     [('Mais de 75%', 1), ('50% a 75%', 2), ('25% a 50%', 3), ('Menos de 25%', 4)]),
    ('Parte 1 · Autoclassificação', 'Quão estável é o teu rendimento?',
     [('Instável', 1), ('Com alguma incerteza', 2), ('Estável', 3), ('Muito estável, com reserva de emergência', 4)]),
    ('Parte 2 · Ganhos e perdas', 'O que preferes?',
     [('Um ganho certo de 500 €', 1), ('50% de ganhar 1.100 € e 50% de não ganhar nada', 4)]),
    ('Parte 2 · Ganhos e perdas', 'E agora, o que preferes?',
     [('Uma perda certa de 500 €', 1), ('50% de perder 1.100 € e 50% de não perder nada', 4)]),
    ('Parte 2 · Ganhos e perdas', 'A tua carteira cai 20% em 3 meses. O que fazes?',
     [('Vendo tudo', 1), ('Vendo metade', 2), ('Mantenho', 3), ('Compro mais', 4)]),
    ('Parte 2 · Ganhos e perdas', 'A tua carteira sobe 30% num ano. O que fazes?',
     [('Realizo tudo', 1), ('Realizo metade', 2), ('Mantenho', 3), ('Aumento a posição', 4)]),
    ('Parte 2 · Ganhos e perdas', 'Que carteira preferes (pior e melhor ano possíveis)?',
     [('A: −3% a +6%', 1), ('B: −12% a +16%', 2), ('C: −25% a +30%', 3), ('D: −40% a +50%', 4)]),
]


def profile_from_score(score):
    for p, (lo, hi) in BANDS.items():
        if lo <= score <= hi:
            return p
    return 'moderate'


# ------------------------------------------------------------------------------------------
# Dados e métricas (fórmulas iguais às do notebook, E.3; retornos log mensais)
# ------------------------------------------------------------------------------------------
@st.cache_data
def load_data():
    returns = pd.read_csv(DATA_DIR / 'returns.csv', index_col=0, parse_dates=True)
    turnover = pd.read_csv(DATA_DIR / 'turnover.csv', index_col=0, parse_dates=True)
    weights = pd.read_csv(DATA_DIR / 'weights_history.csv', parse_dates=['date'])
    allocation = pd.read_csv(DATA_DIR / 'allocation.csv', index_col=0)
    with open(DATA_DIR / 'meta.json', encoding='utf-8') as f:
        meta = json.load(f)
    return returns, turnover, weights, allocation, meta


def wealth_index(r):
    w = np.exp(r.cumsum())
    start = pd.Series([1.0], index=[r.index[0] - pd.DateOffset(months=1)])
    return pd.concat([start, w])


def max_drawdown(r):
    w = wealth_index(r)
    return (w / w.cummax() - 1).min()


def metrics(r, rb, rf):
    ex, ex_b, active = r - rf, rb - rf, r - rb
    beta = ex.cov(ex_b) / ex_b.var()
    return {
        'Retorno anual': 12 * r.mean(),
        'Volatilidade anual': np.sqrt(12) * r.std(),
        'Sharpe': 12 * ex.mean() / (np.sqrt(12) * ex.std()),
        'Information ratio': 12 * active.mean() / (np.sqrt(12) * active.std()) if active.std() > 0 else np.nan,
        'Alpha anual': 12 * (ex.mean() - beta * ex_b.mean()),
        'Beta': beta,
        'Máx. drawdown': max_drawdown(r),
        'Retorno acumulado': np.exp(r.sum()) - 1,
    }


def pct(x, d=1):
    return '—' if pd.isna(x) else f'{x * 100:.{d}f}%'.replace('.', ',')


def num(x, d=2):
    return '—' if pd.isna(x) else f'{x:.{d}f}'.replace('.', ',')


def bench_label(meta, profile):
    w = meta.get('benchmark_weights', {}).get(profile, [0.6, 0.4])
    return f'Benchmark {int(round(100 * w[0]))}/{int(round(100 * w[1]))}'


# ------------------------------------------------------------------------------------------
# Estilo
# ------------------------------------------------------------------------------------------
CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500&display=swap');
html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
.stApp {{
  background: radial-gradient(1200px 600px at 10% -10%, rgba(0,240,255,0.08), transparent 60%),
              radial-gradient(900px 500px at 110% 10%, rgba(255,43,214,0.07), transparent 60%), {BG};
}}
section[data-testid="stSidebar"] {{ background: #0E1322; border-right: 1px solid {GRID}; }}
h1, h2, h3 {{ letter-spacing: -0.02em; }}
.hero-title {{
  font-size: 2.5rem; font-weight: 700; line-height: 1.1; margin: 0.2rem 0 0.4rem 0;
  background: linear-gradient(90deg, {NEON_CYAN}, {NEON_PINK});
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}}
.hero-sub {{ color: {MUTED}; font-size: 1.05rem; max-width: 60rem; }}
.eyebrow {{ color: {NEON_CYAN}; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem;
  letter-spacing: 0.14em; text-transform: uppercase; }}
.card {{
  background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01)), {PANEL};
  border: 1px solid {GRID}; border-radius: 16px; padding: 1.1rem 1.3rem; margin-bottom: 0.8rem;
}}
.kpi {{ min-height: 150px; }}
.glow {{ box-shadow: 0 0 0 1px rgba(0,240,255,0.25), 0 0 32px rgba(0,240,255,0.10); }}
.kpi-label {{ color: {MUTED}; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.08em; }}
.kpi-value {{ color: {TEXT}; font-size: 1.75rem; font-weight: 700; margin-top: 0.15rem; }}
.kpi-delta {{ color: {MUTED}; font-size: 0.82rem; margin-top: 0.1rem; }}
.kpi-delta b.up {{ color: #4ADE80; }} .kpi-delta b.down {{ color: #FB7185; }}
.profile-badge {{ display: inline-block; padding: 0.3rem 0.9rem; border-radius: 999px; font-weight: 700;
  font-size: 1.6rem; border: 1px solid currentColor; box-shadow: 0 0 24px currentColor inset, 0 0 18px currentColor; }}
.scorebar {{ position: relative; height: 12px; border-radius: 999px; margin: 1.2rem 0 0.4rem 0;
  background: linear-gradient(90deg, {C_STRAT} 0%, {C_STRAT} 33%, {C_ALT} 33%, {C_ALT} 70%, {C_BENCH} 70%); opacity: 0.9; }}
.scorebar .pin {{ position: absolute; top: -7px; width: 4px; height: 26px; background: #fff; border-radius: 2px;
  box-shadow: 0 0 12px #fff; }}
.scale {{ display: flex; justify-content: space-between; color: {MUTED}; font-size: 0.8rem; }}
.warn {{ background: rgba(232,120,12,0.12); border: 1px solid {C_ORANGE}; color: #FFD7B0; border-radius: 12px;
  padding: 0.7rem 1rem; margin-bottom: 1rem; font-weight: 500; }}
.small {{ color: {MUTED}; font-size: 0.85rem; }}
div.stButton > button {{ border-radius: 10px; border: 1px solid {GRID}; font-weight: 600; }}
div.stButton > button[kind="primary"] {{ background: linear-gradient(90deg, #00B8D9, #C026D3); border: none; color: white; }}
div[data-testid="stForm"] {{ border: 1px solid {GRID}; border-radius: 16px; background: {PANEL}; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 0.4rem; }}
.stTabs [data-baseweb="tab"] {{ background: {PANEL}; border-radius: 10px 10px 0 0; padding: 0.5rem 1rem; }}
</style>
"""


def kpi(label, value, delta_html=''):
    cls = 'card kpi' if delta_html else 'card'
    return (f'<div class="{cls}"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div>'
            f'<div class="kpi-delta">{delta_html}</div></div>')


def vs(a, b, fmt, higher_is_better=True, name='benchmark'):
    if pd.isna(a) or pd.isna(b):
        return ''
    good = (a >= b) if higher_is_better else (a <= b)
    cls = 'up' if good else 'down'
    arrow = '▲' if a >= b else '▼'
    return f'<b class="{cls}">{arrow}</b> {name}: {fmt(b)}'


def base_layout(fig, height=420, yfmt=None, ytitle=None):
    fig.update_layout(
        height=height, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Inter, sans-serif', color=TEXT, size=13),
        margin=dict(l=10, r=10, t=30, b=10), hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0, bgcolor='rgba(0,0,0,0)'),
        hoverlabel=dict(bgcolor=PANEL, bordercolor=GRID, font_color=TEXT),
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, tickfont=dict(color=MUTED), tickformat=yfmt,
                     title=dict(text=ytitle, font=dict(color=MUTED)))
    return fig


# ------------------------------------------------------------------------------------------
# Ecrãs
# ------------------------------------------------------------------------------------------
def header():
    st.markdown('<div class="eyebrow">Financial Modeling · Nova SBE</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-title">Qual é o teu perfil de investidor?</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-sub">Responde a 10 perguntas. Sugerimos um perfil, tu decides, e mostramos como a '
                'carteira desse perfil se comportou desde 2011 contra o seu benchmark.</div>', unsafe_allow_html=True)
    st.write('')


def screen_quiz():
    header()
    with st.form('quiz'):
        answers = []
        section = None
        for i, (sec, q, opts) in enumerate(QUESTIONS):
            if sec != section:
                st.markdown(f'#### {sec}')
                section = sec
            choice = st.radio(f'**{i + 1}.** {q}', [o[0] for o in opts], index=None, key=f'q{i}')
            answers.append(dict(opts).get(choice) if choice else None)
        submitted = st.form_submit_button('Ver o meu perfil  →', type='primary', **FULL)
    if submitted:
        missing = [str(i + 1) for i, a in enumerate(answers) if a is None]
        if missing:
            st.error(f'Falta responder à(s) pergunta(s) {", ".join(missing)}.')
            return
        st.session_state.score = int(sum(answers))
        st.session_state.suggested = profile_from_score(st.session_state.score)
        st.session_state.step = 'suggest'
        st.rerun()


def screen_suggest():
    score, p = st.session_state.score, st.session_state.suggested
    st.markdown('<div class="eyebrow">Resultado do questionário</div>', unsafe_allow_html=True)
    left, right = st.columns([3, 2], gap='large')
    with left:
        st.markdown(
            f'<div class="card glow"><div class="small">O perfil que te sugerimos é</div>'
            f'<div style="margin:0.6rem 0 0.8rem 0"><span class="profile-badge" style="color:{PROFILE_COLOR[p]}">'
            f'{PROFILE_PT[p]}</span></div>'
            f'<div style="color:{TEXT}">{PROFILE_BLURB[p]}</div>'
            f'<div class="scorebar"><div class="pin" style="left:calc({(score - 10) / 30 * 100:.1f}% - 2px)"></div></div>'
            f'<div class="scale"><span>10 · Conservador</span><span>20 · Moderado</span><span>31 · Agressivo · 40</span></div>'
            f'<div class="small" style="margin-top:0.7rem">A tua pontuação: <b style="color:{TEXT}">{score} / 40</b> '
            f'(10-19 conservador, 20-30 moderado, 31-40 agressivo).</div></div>',
            unsafe_allow_html=True)
    with right:
        st.markdown('#### Concordas com este perfil?')
        st.write('A sugestão vem das tuas respostas, mas a decisão final é tua.')
        if st.button(f'Sim, fico com o perfil {PROFILE_PT[p]}', type='primary', **FULL):
            st.session_state.final = p
            st.session_state.changed = False
            st.session_state.step = 'dashboard'
            st.rerun()
        st.write('')
        others = [x for x in PROFILES if x != p]
        alt_label = st.radio('Não, prefiro outro perfil:', [PROFILE_PT[x] for x in others], index=None)
        alt = {PROFILE_PT[x]: x for x in others}.get(alt_label)
        if st.button('Escolher este perfil', disabled=alt is None, **FULL):
            st.session_state.final = alt
            st.session_state.changed = True
            st.session_state.step = 'dashboard'
            st.rerun()
        if st.button('← Refazer o questionário', **FULL):
            reset()


def screen_dashboard(returns, turnover, weights, allocation, meta):
    p = st.session_state.final
    sug = st.session_state.get('suggested')
    st.markdown('<div class="eyebrow">A tua carteira</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="hero-title">Perfil {PROFILE_PT[p]}</div>', unsafe_allow_html=True)
    note = ''
    if sug and st.session_state.get('changed'):
        note = f' Sugerimos {PROFILE_PT[sug]} (pontuação {st.session_state.score}), mas escolheste {PROFILE_PT[p]}.'
    st.markdown(f'<div class="hero-sub">{PROFILE_BLURB[p]}{note}</div>', unsafe_allow_html=True)
    st.write('')

    # --- controlos numa só linha, acima dos gráficos ---
    test_start = pd.Timestamp(meta.get('test_start', '2019-01-01'))
    first, last = returns.index[0], returns.index[-1]
    periods = {f'{first.year}-{last.year} (completo)': (first, last + pd.offsets.MonthBegin(1)),
               f'{first.year}-{test_start.year - 1}': (first, test_start),
               f'{test_start.year}-{last.year}': (test_start, last + pd.offsets.MonthBegin(1))}
    c1, c2, c3 = st.columns([2, 2, 2])
    period = c1.radio('Período', list(periods), horizontal=True)
    versions = {'Momentum 6-1 fixo (caso base)': 'fixo', 'Janela adaptativa': 'adaptativo'}
    version = versions[c2.radio('Satélite', list(versions), horizontal=True)]
    show_spx = c3.toggle('Mostrar S&P 500 TR', value=True)
    log_y = c3.toggle('Escala logarítmica', value=False)

    start, end = periods[period]
    sel = (returns.index >= start) & (returns.index < end)
    R = returns.loc[sel]
    r, rb, rf, spx = R[f'strat_{p}_{version}'], R[f'bench_{p}'], R['rf'], R['sp500tr']
    m, mb, ms = metrics(r, rb, rf), metrics(rb, rb, rf), metrics(spx, rb, rf)
    t = turnover.loc[sel, f'{p}_{version}']
    blabel = bench_label(meta, p)

    # --- KPIs ---
    k = st.columns(6)
    k[0].markdown(kpi('Retorno anual', pct(m['Retorno anual']), vs(m['Retorno anual'], mb['Retorno anual'], pct, name=blabel)), unsafe_allow_html=True)
    k[1].markdown(kpi('Volatilidade', pct(m['Volatilidade anual']), vs(m['Volatilidade anual'], mb['Volatilidade anual'], pct, False, blabel)), unsafe_allow_html=True)
    k[2].markdown(kpi('Sharpe', num(m['Sharpe']), vs(m['Sharpe'], mb['Sharpe'], num, name=blabel)), unsafe_allow_html=True)
    k[3].markdown(kpi('Information ratio', num(m['Information ratio']), f'face ao {blabel.lower()}'), unsafe_allow_html=True)
    k[4].markdown(kpi('Máx. drawdown', pct(m['Máx. drawdown']), vs(m['Máx. drawdown'], mb['Máx. drawdown'], pct, name=blabel)), unsafe_allow_html=True)
    k[5].markdown(kpi('Turnover mensal', pct(t.mean()), f'≈ {num(12 * t.mean(), 1)}× a carteira por ano'), unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(['📈  Performance', '📊  Estatísticas', '🧩  Alocação atual', '⚖️  Comparar perfis'])

    with tab1:
        series = [('Estratégia', r, C_STRAT, 'solid'), (blabel, rb, C_BENCH, 'dash')]
        if show_spx:
            series.append(('S&P 500 TR', spx, C_SPX, 'dot'))
        fig = go.Figure()
        for name, s, color, dash in series:
            w = wealth_index(s)
            fig.add_trace(go.Scatter(x=L(w.index), y=L(w), name=name, mode='lines',
                                     line=dict(color=color, width=2.4 if name == 'Estratégia' else 2, dash=dash),
                                     hovertemplate='%{y:.2f} €<extra>' + name + '</extra>'))
            fig.add_annotation(x=w.index[-1], y=w.values[-1], text=f' {w.values[-1]:.2f}', showarrow=False,
                               xanchor='left', font=dict(color=TEXT, size=12))
        base_layout(fig, 440, ytitle='Valor de 1 € investido')
        if log_y:
            fig.update_yaxes(type='log')
        st.markdown('##### Valor de 1 € investido')
        st.plotly_chart(fig, **FULL, config={'displayModeBar': False})

        a, b = st.columns(2)
        with a:
            st.markdown('##### Drawdown (queda desde o máximo anterior)')
            fig = go.Figure()
            for name, s, color, dash in series[:2]:
                w = wealth_index(s)
                dd = w / w.cummax() - 1
                fig.add_trace(go.Scatter(x=L(dd.index), y=L(dd), name=name, mode='lines',
                                         line=dict(color=color, width=2, dash=dash),
                                         fill='tozeroy' if name == 'Estratégia' else None,
                                         fillcolor='rgba(0,174,208,0.12)',
                                         hovertemplate='%{y:.1%}<extra>' + name + '</extra>'))
            st.plotly_chart(base_layout(fig, 320, yfmt='.0%'), **FULL, config={'displayModeBar': False})
        with b:
            st.markdown('##### Retorno por ano civil')
            yr = pd.DataFrame({'Estratégia': r, blabel: rb}).groupby(r.index.year).sum().apply(np.exp) - 1
            fig = go.Figure()
            for name, color in [('Estratégia', C_STRAT), (blabel, C_BENCH)]:
                fig.add_trace(go.Bar(x=L(yr.index), y=L(yr[name]), name=name, marker_color=color,
                                     marker_line=dict(color=BG, width=2),
                                     hovertemplate='%{y:.1%}<extra>' + name + '</extra>'))
            fig.update_layout(barmode='group', bargap=0.25)
            st.plotly_chart(base_layout(fig, 320, yfmt='.0%'), **FULL, config={'displayModeBar': False})
        st.caption('Retornos mensais, sem custos de transação, com dados até ao fecho do mês anterior a cada decisão. '
                   'Resultados passados não garantem resultados futuros.')

    with tab2:
        rows = {'Estratégia': m, blabel: mb, 'S&P 500 TR': ms}
        tbl = pd.DataFrame(rows).T
        fmt = {c: pct for c in ['Retorno anual', 'Volatilidade anual', 'Alpha anual', 'Máx. drawdown', 'Retorno acumulado']}
        fmt.update({'Sharpe': num, 'Information ratio': num, 'Beta': num})
        shown = tbl.copy().astype(object)
        for c, f in fmt.items():
            shown[c] = tbl[c].map(f)
        shown['Turnover mensal'] = [pct(t.mean()), '—', '—']
        st.markdown(f'##### Estatísticas, {period}')
        st.dataframe(shown.T, **FULL)
        st.markdown(
            '<div class="small">Alpha, beta e information ratio medem-se face ao benchmark do perfil. '
            'Retorno anual = 12 × média do retorno log mensal; volatilidade = √12 × desvio-padrão; '
            'Sharpe = retorno em excesso da T-bill ÷ volatilidade desse excesso; information ratio = retorno ativo ÷ '
            'tracking error (acima de ~0,5 é bom); turnover = metade da soma das variações absolutas dos pesos.</div>',
            unsafe_allow_html=True)

        st.markdown('##### Sharpe nos dois subperíodos')
        names = list(periods)[1:]
        fig = go.Figure()
        for label, col, color in [('Estratégia', f'strat_{p}_{version}', C_STRAT), (blabel, f'bench_{p}', C_BENCH),
                                  ('S&P 500 TR', 'sp500tr', C_SPX)]:
            vals = []
            for nm in names:
                s0, e0 = periods[nm]
                Q = returns.loc[(returns.index >= s0) & (returns.index < e0)]
                vals.append(metrics(Q[col], Q[f'bench_{p}'], Q['rf'])['Sharpe'])
            fig.add_trace(go.Bar(x=names, y=vals, name=label, marker_color=color, marker_line=dict(color=BG, width=2),
                                 text=[num(v) for v in vals], textposition='outside', textfont=dict(color=TEXT),
                                 hovertemplate='%{y:.2f}<extra>' + label + '</extra>'))
        fig.update_layout(barmode='group', bargap=0.3)
        st.plotly_chart(base_layout(fig, 320), **FULL, config={'displayModeBar': False})

    with tab3:
        alloc_month = pd.Timestamp(meta.get('allocation_month', '2026-11-01'))
        a = allocation[p]
        st.markdown(f'##### Carteira proposta para {alloc_month:%m/%Y} (dados até ao fim do mês anterior)')
        macro = meta.get('macro')                      # opcional: só aparece se o notebook exportar regras macro
        if macro:
            flags = [('Inflação alta (obrigações ≤ 30%)', macro.get('high_inflation')),
                     ('Curva invertida (ações ≤ 40%)', macro.get('inverted_curve'))]
            st.markdown('Regras macro: ' + ' · '.join(f'{"🟢 ativa" if v else "⚪ inativa"}: {n}' for n, v in flags))
        c1, c2 = st.columns([2, 3], gap='large')
        with c1:
            by_class = a.groupby(a.index.map(lambda i: ETF_INFO[i][1])).sum()
            pos = by_class[by_class > 1e-6]
            fig = go.Figure(go.Pie(labels=L(pos.index), values=L(pos), hole=0.62, sort=False,
                                   marker=dict(colors=[CLASS_COLOR[c] for c in pos.index], line=dict(color=BG, width=3)),
                                   textinfo='label+percent', textfont=dict(color=TEXT),
                                   hovertemplate='%{label}: %{value:.1%}<extra></extra>'))
            lev = a.get('RF', 0)
            centre = 'Exposição (alavancada)' if lev < -1e-6 else 'Exposição'
            fig.add_annotation(text=f'<b>{pct(1 - lev, 0)}</b><br><span style="font-size:12px">{centre} a risco</span>',
                               showarrow=False, font=dict(size=22, color=TEXT))
            base_layout(fig, 360).update_layout(showlegend=False, hovermode=False)
            st.plotly_chart(fig, **FULL, config={'displayModeBar': False})
            if lev < -1e-6:
                st.markdown(f'<div class="small">O peso negativo em T-bills ({pct(lev)}) é o empréstimo que leva o core '
                            f'à volatilidade-alvo; paga T-bill + 1,5% ao ano. O gráfico mostra só as partes positivas.</div>',
                            unsafe_allow_html=True)
        with c2:
            core = a.drop(['RF', 'SATELLITE'])
            fig = go.Figure(go.Bar(y=[f'{i} · {ETF_INFO[i][0]}' for i in core.index], x=L(core), orientation='h',
                                   marker_color=[CLASS_COLOR[ETF_INFO[i][1]] for i in core.index],
                                   marker_line=dict(color=BG, width=2),
                                   text=[pct(v) for v in core.values], textposition='outside', textfont=dict(color=TEXT),
                                   hovertemplate='%{y}: %{x:.1%}<extra></extra>'))
            base_layout(fig, 360, yfmt=None).update_layout(hovermode='closest', showlegend=False)
            fig.update_xaxes(tickformat='.0%', gridcolor=GRID, showgrid=True, range=[0, max(core.max(), 0.01) * 1.25])
            fig.update_yaxes(autorange='reversed', gridcolor='rgba(0,0,0,0)')
            st.markdown('**Core por ETF** (peso na carteira total)')
            st.plotly_chart(fig, **FULL, config={'displayModeBar': False})

        t1 = pd.DataFrame({'Componente': [ETF_INFO[i][0] for i in a.index], 'Código': a.index,
                           'Classe': [ETF_INFO[i][1] for i in a.index], 'Peso': [pct(v) for v in a.values]})
        s1, s2, s3 = st.columns(3)
        s1.markdown(kpi('Core (ETFs)', pct(core.sum())), unsafe_allow_html=True)
        s2.markdown(kpi('Satélite', pct(a['SATELLITE'])), unsafe_allow_html=True)
        s3.markdown(kpi('Sem risco (T-bills)', pct(a['RF'])), unsafe_allow_html=True)
        stocks = meta.get('satellite_stocks', [])
        if stocks:
            st.markdown(f'**Ações do satélite** ({len(stocks)}, em partes iguais): ' + ', '.join(f'`{s}`' for s in stocks))
        with st.expander('Tabela da alocação'):
            st.dataframe(t1, hide_index=True, **FULL)

        st.markdown('##### Como a alocação mudou ao longo do tempo')
        W = weights[weights['profile'] == p].pivot(index='date', columns='item', values='weight').fillna(0)
        W['Sem risco'] = W.pop('RF').clip(lower=0) if 'RF' in W else 0
        grouped = pd.DataFrame({c: W[[i for i in W.columns if i in ETF_INFO and ETF_INFO[i][1] == c]].sum(axis=1)
                                for c in ['Ações', 'Obrigações', 'Ativos reais']})
        grouped['Satélite'] = W.get('SATELLITE', 0)
        grouped['Sem risco'] = W['Sem risco']
        fig = go.Figure()
        for c in grouped.columns:
            fig.add_trace(go.Scatter(x=L(grouped.index), y=L(grouped[c]), name=c, mode='lines', stackgroup='one',
                                     line=dict(width=0.5, color=CLASS_COLOR[c]),
                                     hovertemplate='%{y:.1%}<extra>' + c + '</extra>'))
        st.plotly_chart(base_layout(fig, 340, yfmt='.0%'), **FULL, config={'displayModeBar': False})
        st.caption('Pesos na carteira total no início de cada mês. Acima de 100% = parte do core financiada com empréstimo.')

    with tab4:
        st.markdown(f'##### Os três perfis, {period}')
        rows = []
        for q in PROFILES:
            mq = metrics(R[f'strat_{q}_{version}'], R[f'bench_{q}'], R['rf'])
            mbq = metrics(R[f'bench_{q}'], R[f'bench_{q}'], R['rf'])
            rows.append({'Perfil': PROFILE_PT[q] + (' ◀ o teu' if q == p else ''), 'Benchmark': bench_label(meta, q).split(' ')[1],
                         'Retorno anual': pct(mq['Retorno anual']), 'Ret. benchmark': pct(mbq['Retorno anual']),
                         'Volatilidade': pct(mq['Volatilidade anual']), 'Sharpe': num(mq['Sharpe']),
                         'Sharpe benchmark': num(mbq['Sharpe']), 'Information ratio': num(mq['Information ratio']),
                         'Máx. drawdown': pct(mq['Máx. drawdown']),
                         'Turnover mensal': pct(turnover.loc[sel, f'{q}_{version}'].mean())})
        st.dataframe(pd.DataFrame(rows), hide_index=True, **FULL)
        fig = go.Figure()
        for q in PROFILES:
            w = wealth_index(R[f'strat_{q}_{version}'])
            fig.add_trace(go.Scatter(x=L(w.index), y=L(w), name=PROFILE_PT[q], mode='lines',
                                     line=dict(color=PROFILE_COLOR[q], width=3 if q == p else 1.6),
                                     opacity=1 if q == p else 0.7,
                                     hovertemplate='%{y:.2f} €<extra>' + PROFILE_PT[q] + '</extra>'))
        st.plotly_chart(base_layout(fig, 360, ytitle='Valor de 1 € investido'), **FULL,
                        config={'displayModeBar': False})
        st.markdown('Mudar de perfil:')
        cols = st.columns(3)
        for i, q in enumerate(PROFILES):
            if cols[i].button(PROFILE_PT[q], disabled=(q == p), **FULL, key=f'switch_{q}'):
                st.session_state.final = q
                st.session_state.changed = q != sug
                st.rerun()


def reset():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


def sidebar(meta):
    with st.sidebar:
        st.markdown('<div class="eyebrow">Percurso</div>', unsafe_allow_html=True)
        step = st.session_state.step
        steps = [('quiz', '1 · Questionário'), ('suggest', '2 · Perfil sugerido'), ('dashboard', '3 · A tua carteira')]
        order = [s for s, _ in steps]
        for s, label in steps:
            done = order.index(s) < order.index(step)
            cur = s == step
            color = NEON_CYAN if cur else (TEXT if done else MUTED)
            mark = '●' if cur else ('✓' if done else '○')
            st.markdown(f'<div style="color:{color};margin:0.25rem 0">{mark} {label}</div>', unsafe_allow_html=True)
        st.write('')
        if step != 'quiz' and st.button('Recomeçar', **FULL):
            reset()
        st.divider()
        st.markdown('<div class="eyebrow">A estratégia</div>', unsafe_allow_html=True)
        macro_txt = ' com 2 regras macro (inflação, curva de rendimentos)' if meta.get('macro') else ''
        st.markdown(
            '<div class="small"><b>Core:</b> 8 ETFs, carteira tangente de Markowitz (60 meses, médias encolhidas, '
            f'máx. 40% por ETF){macro_txt}.<br><br>'
            '<b>Perfil:</b> mistura com T-bills até à volatilidade do benchmark (CML).<br><br>'
            '<b>Satélite:</b> 10 small caps do S&P 600 com maior momentum 6-1.</div>', unsafe_allow_html=True)
        st.divider()
        st.markdown(f'<div class="small">Dados até {pd.Timestamp(meta["last_return_month"]):%m/%Y} · '
                    f'exportados em {meta.get("generated_at", "?")}.<br>Isto não é aconselhamento financeiro.</div>',
                    unsafe_allow_html=True)


def main():
    st.set_page_config(page_title='Perfil de investidor · Financial Modeling', page_icon='📈', layout='wide')
    st.markdown(CSS, unsafe_allow_html=True)
    try:
        returns, turnover, weights, allocation, meta = load_data()
    except FileNotFoundError as e:
        st.error(f'Faltam os dados da app em data/ ({e.filename}). Ver o README: correr a célula F.4 do notebook.')
        st.stop()
    if meta.get('synthetic'):
        st.markdown('<div class="warn">⚠️ DADOS SINTÉTICOS DE TESTE: estes números não são resultados do backtest. '
                    'Substituir a pasta data/ pelos ficheiros exportados do notebook (célula F.4).</div>',
                    unsafe_allow_html=True)
    st.session_state.setdefault('step', 'quiz')
    sidebar(meta)
    if st.session_state.step == 'quiz':
        screen_quiz()
    elif st.session_state.step == 'suggest':
        screen_suggest()
    else:
        screen_dashboard(returns, turnover, weights, allocation, meta)


if __name__ == '__main__':
    main()
