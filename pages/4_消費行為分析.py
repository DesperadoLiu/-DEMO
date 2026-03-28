import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.charts import bar_chart, donut_chart
from src.filters import render_sidebar_filters
from src.session_manager import touch_current_page
from src.metrics import get_overview_metrics_for_filters, get_period_comparison
from src.services import get_bundle_pair_rankings, get_mix_anomaly_heatmap, get_mix_change_waterfall, get_mix_daily_trend, get_mix_summary, get_payment_by_dimension, get_txn_payment_cross_matrix, get_txn_type_by_dimension, get_weekday_weekend_summary
from src.ui import alert_panel, apply_page_style, change_text, change_tone, content_gap, render_export_buttons, render_kpi_card, section_title

touch_current_page('pages/4_消費行為分析.py')

FONT_FAMILY = "'Segoe UI', 'Microsoft JhengHei', sans-serif"
TEXT_COLOR = '#14213d'
GRID_COLOR = '#dbeafe'
TXN_COLORS = ['#2563eb', '#f97316', '#06b6d4', '#22c55e']
PAYMENT_COLORS = ['#a855f7', '#2563eb', '#f97316', '#ec4899', '#22c55e']


def _fmt_metric(value, digits=0):
    if value is None or pd.isna(value):
        return '-'
    return f'{value:,.{digits}f}'



def _prepare_stacked_mix_data(df: pd.DataFrame, top_n: int = 4) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=['biz_date', 'mix_value', 'net_sales_value', 'txn_count', 'share_rate'])

    working = df.copy()
    working['mix_value'] = working['mix_value'].fillna('').astype(str).str.strip()
    working['mix_value'] = working['mix_value'].replace({'': '未分類', '?': '未分類', '??': '未分類', 'nan': '未分類', 'None': '未分類'})

    top_labels = (
        working.groupby('mix_value', as_index=False)['net_sales_value']
        .sum()
        .sort_values('net_sales_value', ascending=False)
        .head(top_n)['mix_value']
        .tolist()
    )
    working['mix_bucket'] = working['mix_value'].where(working['mix_value'].isin(top_labels), '其他')
    grouped = working.groupby(['biz_date', 'mix_bucket'], as_index=False)[['net_sales_value', 'txn_count']].sum()
    totals = grouped.groupby('biz_date', as_index=False)['net_sales_value'].sum().rename(columns={'net_sales_value': 'total_sales'})
    grouped = grouped.merge(totals, on='biz_date', how='left')
    grouped['share_rate'] = grouped['net_sales_value'] / grouped['total_sales'].replace(0, pd.NA)
    return grouped.rename(columns={'mix_bucket': 'mix_value'}).sort_values(['biz_date', 'mix_value'])


def _stacked_mix_chart(df: pd.DataFrame, title: str, color_map: dict[str, str] | None = None) -> go.Figure:
    order = (
        df.groupby('mix_value', as_index=False)['net_sales_value']
        .sum()
        .sort_values('net_sales_value', ascending=False)['mix_value']
        .tolist()
    )
    fallback_colors = ['#2563eb', '#f97316', '#06b6d4', '#22c55e', '#a855f7', '#ec4899', '#94a3b8']
    color_map = color_map or {}

    fig = go.Figure()
    for idx, label in enumerate(order):
        subset = df[df['mix_value'] == label].copy()
        fig.add_bar(
            x=subset['biz_date'].astype(str),
            y=subset['share_rate'],
            name=label,
            marker=dict(color=color_map.get(label, fallback_colors[idx % len(fallback_colors)])),
            customdata=subset[['net_sales_value', 'txn_count']].to_numpy(),
            hovertemplate='日期：%{x}<br>類別：' + label + '<br>未稅營收占比：%{y:.1%}<br>未稅營收：%{customdata[0]:,.0f}<br>交易筆數：%{customdata[1]:,.0f}<extra></extra>',
        )

    fig.update_layout(
        title=dict(text=title, font=dict(size=18, color=TEXT_COLOR), x=0.02, xanchor='left'),
        barmode='stack',
        barnorm='fraction',
        margin=dict(l=20, r=20, t=64, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white',
        xaxis_title='',
        yaxis_title='',
        font=dict(family=FONT_FAMILY, size=13, color=TEXT_COLOR),
        legend_title_text='',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
    )
    fig.update_xaxes(showgrid=False, tickangle=-35, tickfont=dict(size=12), automargin=True)
    fig.update_yaxes(showgrid=True, gridcolor=GRID_COLOR, zeroline=False, tickfont=dict(size=12), automargin=True, tickformat='.0%')
    return fig


def _mix_waterfall_chart(waterfall_df: pd.DataFrame, base_label: str) -> go.Figure:
    ordered = waterfall_df.copy()
    ordered['net_sales_change'] = ordered['net_sales_change'].fillna(0)
    ordered = ordered[ordered['net_sales_change'] != 0].copy()
    ordered = pd.concat([
        ordered[ordered['net_sales_change'] > 0].sort_values('net_sales_change', ascending=False),
        ordered[ordered['net_sales_change'] < 0].sort_values('net_sales_change', ascending=True),
    ], ignore_index=True)

    latest_date = str(ordered['latest_date'].iloc[0])
    prior_date = str(ordered['prior_date'].iloc[0])
    total_current = float(ordered['total_current_net_sales'].iloc[0])
    total_prior = float(ordered['total_prior_net_sales'].iloc[0])
    total_delta = total_current - total_prior
    shown_delta = float(ordered['net_sales_change'].sum())
    other_delta = total_delta - shown_delta

    labels = [f'{prior_date} 未稅營收'] + ordered['label'].tolist()
    measures = ['absolute'] + ['relative'] * len(ordered)
    values = [total_prior] + ordered['net_sales_change'].tolist()
    texts = [f'{total_prior:,.0f}'] + [f'{value:+,.0f}' for value in ordered['net_sales_change']]

    if abs(other_delta) >= 1:
        labels.append('其他類型')
        measures.append('relative')
        values.append(other_delta)
        texts.append(f'{other_delta:+,.0f}')

    labels.append(f'{latest_date} 未稅營收')
    measures.append('total')
    values.append(total_current)
    texts.append(f'{total_current:,.0f}')

    fig = go.Figure(go.Waterfall(
        orientation='v',
        measure=measures,
        x=labels,
        y=values,
        text=texts,
        textposition='outside',
        connector={'line': {'color': '#94a3b8', 'width': 1.2}},
        increasing={'marker': {'color': '#22c55e'}},
        decreasing={'marker': {'color': '#ef4444'}},
        totals={'marker': {'color': '#2563eb'}},
        hovertemplate=f'{base_label}：%{{x}}<br>金額：%{{y:,.0f}}<extra></extra>',
        cliponaxis=False,
    ))
    fig.update_layout(
        margin=dict(l=20, r=20, t=20, b=24),
        paper_bgcolor='white',
        plot_bgcolor='white',
        showlegend=False,
        font=dict(family=FONT_FAMILY, size=12, color=TEXT_COLOR),
    )
    fig.update_xaxes(showgrid=False, tickangle=-20, automargin=True)
    fig.update_yaxes(showgrid=True, gridcolor=GRID_COLOR, zeroline=False, tickformat=',.0f', automargin=True)
    return fig


def _mix_waterfall_summary(waterfall_df: pd.DataFrame) -> str:
    if waterfall_df is None or waterfall_df.empty:
        return '目前資料不足，暫時無法判讀未稅營收變化來源。'

    latest_date = str(waterfall_df['latest_date'].iloc[0])
    prior_date = str(waterfall_df['prior_date'].iloc[0])
    total_current = float(waterfall_df['total_current_net_sales'].iloc[0])
    total_prior = float(waterfall_df['total_prior_net_sales'].iloc[0])
    total_delta = total_current - total_prior
    mover = waterfall_df.reindex(waterfall_df['net_sales_change'].abs().sort_values(ascending=False).index).iloc[0]
    direction = '拉升' if mover['net_sales_change'] >= 0 else '拖累'
    return (
        f'這張圖比較 {latest_date} 與 {prior_date} 的未稅營收差異；'
        f'整體變動為 {total_delta:+,.0f}，影響最大的是 {mover["label"]}，'
        f'共 {direction} {abs(float(mover["net_sales_change"])):,.0f}。'
    )


def _mix_anomaly_chart(df: pd.DataFrame, title: str) -> go.Figure:
    working = df.copy()
    working['deviation_display'] = working['deviation_rate'].clip(-0.4, 0.4)
    label_order = (
        working.groupby('label', as_index=False)['net_sales_value']
        .sum()
        .sort_values('net_sales_value', ascending=False)['label']
        .tolist()
    )
    date_order = sorted(working['biz_date'].astype(str).unique())

    pivot_dev = working.pivot(index='label', columns='biz_date', values='deviation_display').reindex(index=label_order, columns=date_order)
    pivot_raw = working.pivot(index='label', columns='biz_date', values='deviation_rate').reindex(index=label_order, columns=date_order)
    pivot_sales = working.pivot(index='label', columns='biz_date', values='net_sales_value').reindex(index=label_order, columns=date_order)
    pivot_avg = working.pivot(index='label', columns='biz_date', values='avg_net_sales').reindex(index=label_order, columns=date_order)

    hover_text = []
    for label in pivot_dev.index:
        row_text = []
        for biz_date in pivot_dev.columns:
            raw_value = pivot_raw.loc[label, biz_date]
            sales_value = pivot_sales.loc[label, biz_date]
            avg_value = pivot_avg.loc[label, biz_date]
            if pd.isna(raw_value):
                row_text.append(f'類型：{label}<br>日期：{biz_date}<br>無資料')
            else:
                row_text.append(
                    f'類型：{label}<br>日期：{biz_date}<br>當日未稅營收：{sales_value:,.0f}<br>近 7 天基準：{avg_value:,.0f}<br>相對基準：{raw_value:+.1%}'
                )
        hover_text.append(row_text)

    fig = go.Figure(go.Heatmap(
        z=pivot_dev.values,
        x=list(pivot_dev.columns),
        y=list(pivot_dev.index),
        colorscale=[[0.0, '#ef4444'], [0.5, '#fff7ed'], [1.0, '#22c55e']],
        zmin=-0.4,
        zmax=0.4,
        zmid=0,
        text=hover_text,
        hoverinfo='text',
        colorbar=dict(title='相對基準', tickformat='.0%'),
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=18, color=TEXT_COLOR), x=0.02, xanchor='left'),
        margin=dict(l=20, r=20, t=64, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(family=FONT_FAMILY, size=13, color=TEXT_COLOR),
        height=max(320, 48 * len(label_order) + 120),
    )
    fig.update_xaxes(showgrid=False, tickangle=-35, automargin=True)
    fig.update_yaxes(showgrid=False, automargin=True)
    return fig


def _mix_anomaly_summary(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return '目前資料不足，暫時無法判讀交易型態或付款別異常。'

    weak = df[df['deviation_rate'] <= -0.10].copy()
    strong = df[df['deviation_rate'] >= 0.10].copy()
    messages = []

    if not weak.empty:
        weakest = weak.sort_values(['deviation_rate', 'biz_date']).iloc[0]
        messages.append(f'最近偏弱最明顯的是 {weakest["label"]}，在 {weakest["biz_date"]} 低於基準 {abs(float(weakest["deviation_rate"])):.0%}')
    if not strong.empty:
        strongest = strong.sort_values(['deviation_rate', 'biz_date'], ascending=[False, False]).iloc[0]
        messages.append(f'最近拉升最明顯的是 {strongest["label"]}，在 {strongest["biz_date"]} 高於基準 {float(strongest["deviation_rate"]):.0%}')

    if not messages:
        return '近 14 天各類型多數表現接近自己的短期基準，尚未出現明顯異常。'
    return '觀察重點：' + '；'.join(messages) + '。'



def _bundle_matrix_data(df: pd.DataFrame, top_items: int = 8) -> pd.DataFrame:
    columns = ['item_a', 'item_b', 'pair_txn_count', 'pair_rate']
    if df is None or df.empty:
        return pd.DataFrame(columns=columns)
    working = df.copy()
    working['item_name_a'] = working['item_name_a'].fillna('').astype(str).str.strip()
    working['item_name_b'] = working['item_name_b'].fillna('').astype(str).str.strip()
    working = working[(working['item_name_a'] != '') & (working['item_name_b'] != '')].copy()
    if working.empty:
        return pd.DataFrame(columns=columns)

    item_strength = pd.concat([
        working[['item_name_a', 'pair_rate', 'pair_txn_count']].rename(columns={'item_name_a': 'item_name'}),
        working[['item_name_b', 'pair_rate', 'pair_txn_count']].rename(columns={'item_name_b': 'item_name'}),
    ], ignore_index=True)
    item_strength['pair_rate'] = item_strength['pair_rate'].fillna(0.0)
    item_strength['pair_txn_count'] = item_strength['pair_txn_count'].fillna(0.0)
    ranked_items = (
        item_strength.groupby('item_name', as_index=False)[['pair_rate', 'pair_txn_count']]
        .sum()
        .sort_values(['pair_rate', 'pair_txn_count', 'item_name'], ascending=[False, False, True])
    )
    top_names = ranked_items['item_name'].head(top_items).tolist()

    matrix_rows = []
    for row_name in top_names:
        for col_name in top_names:
            if row_name == col_name:
                matrix_rows.append({'item_a': row_name, 'item_b': col_name, 'pair_txn_count': 0, 'pair_rate': 0.0})
                continue
            match = working[((working['item_name_a'] == row_name) & (working['item_name_b'] == col_name)) | ((working['item_name_a'] == col_name) & (working['item_name_b'] == row_name))]
            if match.empty:
                pair_txn_count = 0
                pair_rate = 0.0
            else:
                pair_txn_count = float(match['pair_txn_count'].iloc[0])
                pair_rate = float(match['pair_rate'].iloc[0]) if pd.notna(match['pair_rate'].iloc[0]) else 0.0
            matrix_rows.append({'item_a': row_name, 'item_b': col_name, 'pair_txn_count': pair_txn_count, 'pair_rate': pair_rate})
    return pd.DataFrame(matrix_rows, columns=columns)

def _bundle_matrix_chart(df: pd.DataFrame) -> go.Figure:
    if df is None or df.empty:
        return go.Figure()
    pivot_value = df.pivot(index='item_a', columns='item_b', values='pair_rate').fillna(0)
    pivot_count = df.pivot(index='item_a', columns='item_b', values='pair_txn_count').fillna(0)
    zmax = float(pivot_value.values.max()) if pivot_value.size else 0.0
    zmax = max(0.01, zmax)

    hover_text = []
    for row_label in pivot_value.index:
        hover_row = []
        for col_label in pivot_value.columns:
            rate_value = pivot_value.loc[row_label, col_label]
            count_value = pivot_count.loc[row_label, col_label]
            if row_label == col_label:
                hover_row.append(f'商品: {row_label}<br>此格僅作為對角線占位')
            else:
                hover_row.append(f'商品組合: {row_label} + {col_label}<br>共同出現交易數: {count_value:,.0f}<br>關聯強度: {rate_value:.1%}')
        hover_text.append(hover_row)

    text_values = pivot_value.applymap(lambda value: '' if value <= 0 else f'{value:.0%}')

    fig = go.Figure(go.Heatmap(
        z=pivot_value.values,
        x=list(pivot_value.columns),
        y=list(pivot_value.index),
        text=text_values.values,
        texttemplate='%{text}',
        hovertext=hover_text,
        hovertemplate='%{hovertext}<extra></extra>',
        textfont={'size': 11},
        colorscale=[[0.0, '#f8fafc'], [0.18, '#dbeafe'], [0.45, '#93c5fd'], [0.72, '#3b82f6'], [1.0, '#1e3a8a']],
        zmin=0,
        zmax=zmax,
        colorbar=dict(title='關聯強度', tickformat='.0%'),
        xgap=2,
        ygap=2,
    ))
    fig.update_layout(
        title=dict(text='搭購關聯矩陣', font=dict(size=18, color=TEXT_COLOR), x=0.02, xanchor='left'),
        margin=dict(l=20, r=20, t=64, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(family=FONT_FAMILY, size=13, color=TEXT_COLOR),
        height=max(420, 48 * len(pivot_value.index) + 140),
    )
    fig.update_xaxes(showgrid=False, tickangle=-35, automargin=True, side='top')
    fig.update_yaxes(showgrid=False, automargin=True, autorange='reversed')
    return fig

def _bundle_matrix_summary(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return '目前資料不足，暫時無法判讀商品之間的搭購關聯。'
    working = df[df['item_a'] != df['item_b']].copy()
    if working.empty:
        return '目前資料不足，暫時無法判讀商品之間的搭購關聯。'
    top_row = working.sort_values(['pair_rate', 'pair_txn_count'], ascending=[False, False]).iloc[0]
    return f"目前關聯最強的組合是 {top_row['item_a']} + {top_row['item_b']}，關聯強度約為 {float(top_row['pair_rate']):.1%}。"


def _bundle_ranking_chart(df: pd.DataFrame) -> go.Figure:
    plot_df = df.sort_values(['pair_txn_count', 'pair_net_sales'], ascending=[True, True]).copy()
    fig = go.Figure(go.Bar(
        x=plot_df['pair_txn_count'],
        y=plot_df['pair_label'],
        orientation='h',
        marker=dict(color='#2563eb'),
        text=[f"{int(v):,} 筆" for v in plot_df['pair_txn_count']],
        textposition='outside',
        customdata=plot_df[['pair_rate', 'pair_net_sales', 'pair_qty', 'multi_item_txn_count']].to_numpy(),
        hovertemplate="搭購組合：%{y}<br>共同出現交易數：%{x:,.0f}<br>多商品交易覆蓋率：%{customdata[0]:.1%}<br>組合未稅營收：%{customdata[1]:,.0f}<br>組合銷量：%{customdata[2]:,.0f}<br>可搭購交易母體：%{customdata[3]:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text='熱門搭購排行 Top 10', font=dict(size=18, color=TEXT_COLOR), x=0.02, xanchor='left'),
        margin=dict(l=20, r=30, t=64, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(family=FONT_FAMILY, size=13, color=TEXT_COLOR),
        height=max(360, 52 * len(plot_df) + 120),
    )
    fig.update_xaxes(showgrid=True, gridcolor=GRID_COLOR, zeroline=False, tickformat=',.0f', automargin=True)
    fig.update_yaxes(showgrid=False, automargin=True)
    return fig


def _bundle_ranking_summary(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return '目前資料不足，暫時無法判讀商品搭購關係。'
    top_row = df.sort_values(['pair_txn_count', 'pair_net_sales'], ascending=[False, False]).iloc[0]
    pair_rate = 0 if pd.isna(top_row['pair_rate']) else float(top_row['pair_rate'])
    return (
        f"目前最常一起被買的組合是 {top_row['pair_label']}，"
        f"共同出現在 {int(top_row['pair_txn_count']):,} 筆交易中，占可搭購交易 {pair_rate:.1%}；"
        f"這組合計帶出未稅營收 {float(top_row['pair_net_sales']):,.0f}。"
    )


def _structure_mix_summary(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return '目前資料不足，暫時無法判讀市場結構變化。'

    ordered_dates = sorted(df['biz_date'].astype(str).unique())
    latest_date = ordered_dates[-1]
    first_date = ordered_dates[0]

    latest = df[df['biz_date'].astype(str) == latest_date].sort_values('share_rate', ascending=False)
    first = df[df['biz_date'].astype(str) == first_date][['mix_value', 'share_rate']].rename(columns={'share_rate': 'start_share'})
    compare = latest.merge(first, on='mix_value', how='left')
    compare['share_change'] = compare['share_rate'] - compare['start_share'].fillna(0)
    top_mix = latest.iloc[0]
    mover = compare.reindex(compare['share_change'].abs().sort_values(ascending=False).index).iloc[0]

    return (
        f"最新一天以 {top_mix['mix_value']} 占比最高，約 {top_mix['share_rate']:.0%}；"
        f"近 {len(ordered_dates)} 天結構變化最大的是 {mover['mix_value']}，"
        f"占比較起點 {mover['share_change']:+.0%}。"
    )


def _txn_payment_cross_summary(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return '目前資料不足，暫時無法判讀交易型態與付款結構的交叉關係。'
    top_row = df.sort_values(['share_in_txn', 'net_sales_value'], ascending=[False, False]).iloc[0]
    return (
        f"目前最明顯的組合是 {top_row['txn_type']} 主要搭配 {top_row['payment_type']}，"
        f"在該交易型態內約占 {float(top_row['share_in_txn']):.0%}；"
        f"這個組合合計未稅營收約 {float(top_row['net_sales_value']):,.0f}。"
    )


def _txn_payment_cross_chart(df: pd.DataFrame) -> go.Figure:
    if df is None or df.empty:
        return go.Figure()
    pivot_share = df.pivot(index='txn_type', columns='payment_type', values='share_in_txn').fillna(0)
    pivot_sales = df.pivot(index='txn_type', columns='payment_type', values='net_sales_value').fillna(0)
    pivot_txn = df.pivot(index='txn_type', columns='payment_type', values='txn_count').fillna(0)
    pivot_overall = df.pivot(index='txn_type', columns='payment_type', values='share_overall').fillna(0)

    hover_text = []
    for txn_label in pivot_share.index:
        hover_row = []
        for payment_label in pivot_share.columns:
            hover_row.append(
                f'交易型態: {txn_label}<br>'
                f'付款別: {payment_label}<br>'
                f'交易型態內占比: {pivot_share.loc[txn_label, payment_label]:.1%}<br>'
                f'整體未稅營收占比: {pivot_overall.loc[txn_label, payment_label]:.1%}<br>'
                f'未稅營收: {pivot_sales.loc[txn_label, payment_label]:,.0f}<br>'
                f'交易筆數: {pivot_txn.loc[txn_label, payment_label]:,.0f}'
            )
        hover_text.append(hover_row)

    text_values = pivot_share.applymap(lambda value: '' if value <= 0 else f'{value:.0%}')
    zmax = float(pivot_share.values.max()) if pivot_share.size else 0.0
    zmax = max(0.01, zmax)

    fig = go.Figure(go.Heatmap(
        z=pivot_share.values,
        x=list(pivot_share.columns),
        y=list(pivot_share.index),
        text=text_values.values,
        texttemplate='%{text}',
        hovertext=hover_text,
        hovertemplate='%{hovertext}<extra></extra>',
        textfont={'size': 11},
        colorscale=[[0.0, '#fff7ed'], [0.2, '#fed7aa'], [0.5, '#fb923c'], [0.75, '#ea580c'], [1.0, '#9a3412']],
        zmin=0,
        zmax=zmax,
        colorbar=dict(title='交易型態內占比', tickformat='.0%'),
        xgap=2,
        ygap=2,
    ))
    fig.update_layout(
        title=dict(text='交易型態 vs 支付結構交叉矩陣', font=dict(size=18, color=TEXT_COLOR), x=0.02, xanchor='left'),
        margin=dict(l=20, r=20, t=64, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(family=FONT_FAMILY, size=13, color=TEXT_COLOR),
        height=max(360, 52 * len(pivot_share.index) + 120),
    )
    fig.update_xaxes(showgrid=False, tickangle=-30, automargin=True, side='top')
    fig.update_yaxes(showgrid=False, automargin=True, autorange='reversed')
    return fig



apply_page_style()
filters = render_sidebar_filters(page_key='marketing')

st.title('消費行為分析')
st.caption('掌握交易型態、付款別與平假日結構變化，辨識顧客消費偏好與消費情境差異。')
st.info('提醒：本頁需要進行消費行為相關跑表運算，首次載入或變更篩選條件後可能需要稍候數秒，這屬於正常處理時間。')

metrics = get_overview_metrics_for_filters(filters)
comparison = get_period_comparison(filters)
summary_txn = get_mix_summary('txn_type', filters=filters, limit=10).sort_values('net_sales_value', ascending=False)
summary_payment = get_mix_summary('payment_type', filters=filters, limit=12).sort_values('net_sales_value', ascending=False)
trend_txn = get_mix_daily_trend('txn_type', filters=filters, limit=30)
trend_payment = get_mix_daily_trend('payment_type', filters=filters, limit=30)
waterfall_txn = get_mix_change_waterfall('txn_type', filters=filters, limit=6)
waterfall_payment = get_mix_change_waterfall('payment_type', filters=filters, limit=6)
anomaly_txn = get_mix_anomaly_heatmap('txn_type', filters=filters, days=14, baseline_days=7, top_n=6)
anomaly_payment = get_mix_anomaly_heatmap('payment_type', filters=filters, days=14, baseline_days=7, top_n=6)
bundle_rank = get_bundle_pair_rankings(filters=filters, limit=10)
bundle_matrix = _bundle_matrix_data(bundle_rank, top_items=8)
txn_payment_cross = get_txn_payment_cross_matrix(filters=filters, top_txn=6, top_payment=6)
weekday_weekend = get_weekday_weekend_summary(filters=filters)
payment_by_store = get_payment_by_dimension('store', filters=filters, limit=20).sort_values('net_sales_value', ascending=False)
txn_by_store = get_txn_type_by_dimension('store', filters=filters, limit=20).sort_values('net_sales_value', ascending=False)

# 準備結構分析數據 (Ensure they are defined even if previous calls return None)
structure_txn = _prepare_stacked_mix_data(trend_txn, top_n=4) if not (trend_txn is None or trend_txn.empty) else pd.DataFrame()
structure_payment = _prepare_stacked_mix_data(trend_payment, top_n=5) if not (trend_payment is None or trend_payment.empty) else pd.DataFrame()


content_gap('sm')
main_cards = [
    ('行銷未稅營收', _fmt_metric(metrics.get('net_sales_value') if metrics else None), '目前篩選條件下', 'neutral'),
    ('行銷交易筆數', _fmt_metric(metrics.get('txn_count') if metrics else None), '目前篩選條件下', 'neutral'),
    ('行銷筆單價', _fmt_metric(metrics.get('avg_ticket') if metrics else None, 1), '目前篩選條件下', 'neutral'),
    ('行銷銷量', _fmt_metric(metrics.get('sales_qty') if metrics else None), '目前篩選條件下', 'neutral'),
    ('較上週同日', '-' if comparison.get('wow') is None else f"{comparison.get('wow'):+.1%}", change_text(comparison.get('wow'), '上週同日', comparison.get('wow_date')), change_tone(comparison.get('wow'))),
    ('較上月同期', '-' if comparison.get('mom') is None else f"{comparison.get('mom'):+.1%}", change_text(comparison.get('mom'), '上月同期', comparison.get('mom_date')), change_tone(comparison.get('mom'))),
    ('較上季同期', '-' if comparison.get('qoq') is None else f"{comparison.get('qoq'):+.1%}", change_text(comparison.get('qoq'), '上季同期', comparison.get('qoq_date')), change_tone(comparison.get('qoq'))),
]
for variant, card_group in [('core', main_cards[:4]), ('compare', main_cards[4:])]:
    row_cols = st.columns(4)
    for col, (label, value, subtext, tone) in zip(row_cols, card_group):
        with col:
            render_kpi_card(label, value, subtext, tone, variant=variant)
    content_gap('sm')

content_gap('md')
section_title('近 30 天趨勢')
if trend_txn.empty:
    st.info('目前查無交易型態趨勢資料。')
else:
    top_txn = summary_txn.head(4)['mix_value'].tolist() if not summary_txn.empty else []
    plot_df = trend_txn[trend_txn['mix_value'].isin(top_txn)].copy()
    fig = px.line(
        plot_df,
        x='biz_date',
        y='net_sales_value',
        color='mix_value',
        title='近 30 天交易型態未稅營收趨勢',
        color_discrete_sequence=TXN_COLORS,
    )
    fig.update_traces(
        line={'width': 3},
        marker={'size': 6},
        mode='lines+markers',
        hovertemplate='日期：%{x}<br>交易型態：%{fullData.name}<br>未稅營收：%{y:,.0f}<extra></extra>',
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=64, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white',
        xaxis_title='',
        yaxis_title='',
        font=dict(family=FONT_FAMILY, size=13, color=TEXT_COLOR),
        title=dict(font=dict(size=18, color=TEXT_COLOR), x=0.02, xanchor='left'),
        legend_title_text='',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
    )
    fig.update_xaxes(showgrid=False, tickfont=dict(size=12), automargin=True)
    fig.update_yaxes(showgrid=True, gridcolor=GRID_COLOR, zeroline=False, tickfont=dict(size=12), automargin=True, tickformat=',.0f')
    st.plotly_chart(fig, use_container_width=True)

if trend_payment.empty:
    st.info('目前查無付款別趨勢資料。')
else:
    top_pay = summary_payment.head(5)['mix_value'].tolist() if not summary_payment.empty else []
    plot_df = trend_payment[trend_payment['mix_value'].isin(top_pay)].copy()
    fig = px.line(
        plot_df,
        x='biz_date',
        y='net_sales_value',
        color='mix_value',
        title='近 30 天付款別未稅營收趨勢',
        color_discrete_sequence=PAYMENT_COLORS,
    )
    fig.update_traces(
        line={'width': 3},
        marker={'size': 6},
        mode='lines+markers',
        hovertemplate='日期：%{x}<br>付款別：%{fullData.name}<br>未稅營收：%{y:,.0f}<extra></extra>',
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=64, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white',
        xaxis_title='',
        yaxis_title='',
        font=dict(family=FONT_FAMILY, size=13, color=TEXT_COLOR),
        title=dict(font=dict(size=18, color=TEXT_COLOR), x=0.02, xanchor='left'),
        legend_title_text='',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
    )
    fig.update_xaxes(showgrid=False, tickfont=dict(size=12), automargin=True)
    fig.update_yaxes(showgrid=True, gridcolor=GRID_COLOR, zeroline=False, tickfont=dict(size=12), automargin=True, tickformat=',.0f')
    st.plotly_chart(fig, use_container_width=True)

section_title('市場結構變化堆疊圖')
st.caption('這一區改看各類型的未稅營收占比變化，幫助判斷交易型態與付款別的市場重心是否正在移動。')
st.info('閱讀方式：先看每一天哪一塊最大，代表當天市場主力；再看色塊是逐漸變厚還是變薄，就能判斷該類型在市場中的相對份額是擴大還是縮小。若某類型未稅營收未必大增，但占比持續上升，通常代表它相對其他類型更被市場接受。')
if structure_txn.empty:
    st.info('目前查無交易型態結構變化資料。')
else:
    st.caption(_structure_mix_summary(structure_txn))
    txn_color_map = {'外帶': '#2563eb', '內用': '#22c55e', '外送': '#f97316', '外送平台': '#a855f7', '其他': '#94a3b8', '未分類': '#06b6d4'}
    st.plotly_chart(_stacked_mix_chart(structure_txn, '近 30 天交易型態市場結構變化', txn_color_map), use_container_width=True)

if structure_payment.empty:
    st.info('目前查無付款別結構變化資料。')
else:
    st.caption(_structure_mix_summary(structure_payment))
    payment_color_map = {'LINE Pay': '#10b981', '街口支付': '#2563eb', '信用卡': '#f97316', '現金': '#64748b', '其他': '#94a3b8', '未分類': '#06b6d4'}
    st.plotly_chart(_stacked_mix_chart(structure_payment, '近 30 天付款別市場結構變化', payment_color_map), use_container_width=True)

section_title('未稅營收變化來源瀑布圖')
st.caption('這一區把最新一天相較上週同日的未稅營收差異，拆成各交易型態與付款別的拉升或拖累來源。')
st.info('閱讀方式：左邊藍柱是上週同日未稅營收，右邊藍柱是最新未稅營收；中間綠柱代表帶來成長的類型，紅柱代表拖累未稅營收的類型。先看總未稅營收差多少，再看中間哪幾個類型影響最大，就能快速知道這波變化是誰造成。')
if waterfall_txn.empty:
    st.info('目前查無交易型態未稅營收變化來源資料。')
else:
    st.caption(_mix_waterfall_summary(waterfall_txn))
    st.plotly_chart(_mix_waterfall_chart(waterfall_txn, '交易型態'), use_container_width=True)

if waterfall_payment.empty:
    st.info('目前查無付款別未稅營收變化來源資料。')
else:
    st.caption(_mix_waterfall_summary(waterfall_payment))
    st.plotly_chart(_mix_waterfall_chart(waterfall_payment, '付款別'), use_container_width=True)

section_title('交易型態 / 支付結構異常提醒圖')
st.caption('這一區用近 14 天熱力圖提醒哪些交易型態或付款別明顯高於或低於自己的短期基準。')
st.info('閱讀方式：每一列代表一種交易型態或付款別，每一欄代表一天；偏紅表示低於自己近 7 天基準，偏綠表示高於基準，顏色越深代表異常越明顯。這張圖不是看誰未稅營收最大，而是看誰最近突然轉弱或轉強。')
if anomaly_txn.empty:
    st.info('目前查無交易型態異常提醒資料。')
else:
    st.caption(_mix_anomaly_summary(anomaly_txn))
    st.plotly_chart(_mix_anomaly_chart(anomaly_txn, '近 14 天交易型態異常提醒'), use_container_width=True)

if anomaly_payment.empty:
    st.info('目前查無付款別異常提醒資料。')
else:
    st.caption(_mix_anomaly_summary(anomaly_payment))
    st.plotly_chart(_mix_anomaly_chart(anomaly_payment, '近 14 天付款別異常提醒'), use_container_width=True)

section_title('交易型態 vs 支付結構交叉矩陣')
st.caption('這一區把交易型態與付款別放在同一張矩陣裡，幫助判斷每種消費情境主要依賴哪些支付方式。')
st.info('閱讀方式：每一列代表一種交易型態，每一欄代表一種付款別；顏色越深，表示該付款別在這個交易型態中的占比越高。先看每一列最深的格子，就能知道該交易型態最常被用什麼方式付款；再搭配滑鼠提示中的整體未稅營收占比，判斷這是局部結構特徵，還是整體市場的重要組合。')
if txn_payment_cross.empty:
    st.info('目前查無可用的交易型態與付款結構交叉資料。')
else:
    st.caption(_txn_payment_cross_summary(txn_payment_cross))
    st.plotly_chart(_txn_payment_cross_chart(txn_payment_cross), use_container_width=True)

section_title('熱門搭購排行')
st.caption('這一區找出同一筆交易裡最常一起出現的商品組合，幫助判斷哪些商品適合做套餐、加購或聯合陳列。')
st.info('閱讀方式：先看排行最前面的組合，代表最常被一起買；再看滑鼠提示中的多商品交易覆蓋率，判斷這組搭購是少數高額交易帶動，還是普遍存在於大量消費情境。')
if bundle_rank.empty:
    st.info('目前查無可用的熱門搭購資料。')
else:
    st.caption(_bundle_ranking_summary(bundle_rank))
    st.plotly_chart(_bundle_ranking_chart(bundle_rank), use_container_width=True)

section_title('搭購關聯矩陣')
st.caption('這一區把熱門搭購商品放進矩陣，幫助判斷哪些商品彼此關聯最強，適合進一步設計套餐、加價購或聯合曝光。')
st.info('閱讀方式：先看顏色最深的格子，代表兩個商品一起出現的關聯較強；再搭配滑鼠提示中的共同出現交易數與關聯強度，判斷這組搭配是少量高強度，還是同時具備高頻與高關聯。對角線只是占位，不代表商品會和自己搭購。')
if bundle_matrix.empty:
    st.info('目前查無可用的搭購關聯矩陣資料。')
else:
    st.caption(_bundle_matrix_summary(bundle_matrix))
    st.plotly_chart(_bundle_matrix_chart(bundle_matrix), use_container_width=True)





