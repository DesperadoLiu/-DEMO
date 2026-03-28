from datetime import timedelta
from html import escape

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.charts import PALETTE, bar_chart, donut_chart
from src.filters import render_sidebar_filters
from src.session_manager import touch_current_page
from src.metrics import get_period_comparison
from src.services import get_item_change_waterfall, get_item_code_rankings, get_item_prefix_by_dimension, get_item_prefix_daily_trend, get_item_prefix_rankings, get_item_net_sales_qty_quadrant, get_store_item_matrix, get_item_price_band_distribution
from src.ui import alert_panel, apply_page_style, change_text, change_tone, content_gap, render_export_buttons, render_kpi_card, section_title, status_panel

touch_current_page('pages/3_商品表現分析.py')

FONT_FAMILY = "'Segoe UI', 'Microsoft JhengHei', sans-serif"
TEXT_COLOR = '#4b3425'
GRID_COLOR = '#efe4d6'
PRODUCT_COLORS = ['#c65d07', '#f08c00', '#2f6f6f', '#7a9e7e', '#b86f52']


def _fmt_metric(value, digits=0):
    if value is None or pd.isna(value):
        return '-'
    return f'{value:,.{digits}f}'


def _product_period_comparison(prefix_trend: pd.DataFrame) -> dict:
    if prefix_trend is None or prefix_trend.empty:
        return {'wow': None, 'mom': None, 'qoq': None}

    daily = (
        prefix_trend.groupby('biz_date', as_index=False)['net_sales_value']
        .sum()
        .sort_values('biz_date')
        .copy()
    )
    if len(daily) < 2:
        return {'wow': None, 'mom': None, 'qoq': None}

    daily['biz_date'] = pd.to_datetime(daily['biz_date'])
    latest = daily.iloc[-1]
    latest_date = latest['biz_date']
    current = float(latest['net_sales_value'])

    def pick_comp(delta_days: int):
        target = latest_date - timedelta(days=delta_days)
        row = daily.loc[daily['biz_date'] == target]
        if row.empty:
            return None, None
        prior = float(row.iloc[0]['net_sales_value'])
        target_date_str = row.iloc[0]['biz_date'].strftime('%Y-%m-%d')
        if prior == 0:
            return None, target_date_str
        return (current - prior) / prior, target_date_str

    wow_v, wow_d = pick_comp(7)
    mom_v, mom_d = pick_comp(28)
    qoq_v, qoq_d = pick_comp(91)

    return {
        'wow': wow_v, 'wow_date': wow_d,
        'mom': mom_v, 'mom_date': mom_d,
        'qoq': qoq_v, 'qoq_date': qoq_d,
    }

def _render_wrapped_donut_legend(df: pd.DataFrame, names_col: str, values_col: str):
    legend_df = df.copy()
    total = legend_df[values_col].sum()
    items = []
    for idx, row in enumerate(legend_df.itertuples(index=False)):
        name = getattr(row, names_col)
        value = getattr(row, values_col)
        label = f'{name} {value / total:.1%}' if total else str(name)
        color = PALETTE[idx % len(PALETTE)]
        items.append(
            f"<div style='display:flex;align-items:center;gap:10px;min-width:180px;'>"
            f"<span style='width:14px;height:14px;background:{color};border-radius:3px;display:inline-block;flex:0 0 auto;'></span>"
            f"<span style='font-size:14px;color:{TEXT_COLOR};line-height:1.3;'>{escape(str(label))}</span>"
            f"</div>"
        )
    st.markdown(
        "<div style='display:flex;flex-wrap:wrap;gap:10px 24px;margin:0 0 10px 0;'>" + ''.join(items) + "</div>",
        unsafe_allow_html=True,
    )

def _prepare_product_structure_data(df: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=['biz_date', 'item_prefix', 'net_sales_value', 'share_rate'])

    working = df.copy()
    working['item_prefix'] = working['item_prefix'].fillna('').astype(str).str.strip()
    working['item_prefix'] = working['item_prefix'].replace({'': '未分類', '?': '未分類', '??': '未分類', 'nan': '未分類', 'None': '未分類'})

    top_labels = (
        working.groupby('item_prefix', as_index=False)['net_sales_value']
        .sum()
        .sort_values('net_sales_value', ascending=False)
        .head(top_n)['item_prefix']
        .tolist()
    )
    working['bucket'] = working['item_prefix'].where(working['item_prefix'].isin(top_labels), '其他')
    grouped = working.groupby(['biz_date', 'bucket'], as_index=False)['net_sales_value'].sum()
    totals = grouped.groupby('biz_date', as_index=False)['net_sales_value'].sum().rename(columns={'net_sales_value': 'total_sales'})
    grouped = grouped.merge(totals, on='biz_date', how='left')
    grouped['share_rate'] = grouped['net_sales_value'] / grouped['total_sales']
    return grouped.rename(columns={'bucket': 'item_prefix'}).sort_values(['biz_date', 'item_prefix'])


def _product_structure_stacked_chart(df: pd.DataFrame) -> go.Figure:
    order = (
        df.groupby('item_prefix', as_index=False)['net_sales_value']
        .sum()
        .sort_values('net_sales_value', ascending=False)['item_prefix']
        .tolist()
    )
    colors = {
        '魯肉飯系列': '#c65d07',
        '便當系列': '#f08c00',
        '小菜系列': '#2f6f6f',
        '湯品系列': '#7a9e7e',
        '嫩豆腐系列': '#b86f52',
        '其他': '#94a3b8',
        '未分類': '#06b6d4',
    }
    fig = go.Figure()
    for label in order:
        subset = df[df['item_prefix'] == label].copy()
        fig.add_bar(
            x=subset['biz_date'].astype(str),
            y=subset['share_rate'],
            name=label,
            marker=dict(color=colors.get(label, '#64748b')),
            customdata=subset[['net_sales_value']].to_numpy(),
            hovertemplate='日期：%{x}<br>餐點屬性碼：' + label + '<br>未稅營收占比：%{y:.1%}<br>未稅營收：%{customdata[0]:,.0f}<extra></extra>',
        )
    fig.update_layout(
        barmode='stack',
        barnorm='fraction',
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(family=FONT_FAMILY, size=12, color=TEXT_COLOR),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
    )
    fig.update_xaxes(showgrid=False, tickangle=-35, automargin=True)
    fig.update_yaxes(showgrid=True, gridcolor=GRID_COLOR, zeroline=False, tickformat='.0%', automargin=True)
    return fig


def _product_sales_qty_quadrant_chart(df: pd.DataFrame) -> go.Figure:
    working = df.copy()
    working['quadrant'] = working.apply(
        lambda row: '明星商品' if pd.notna(row['qty_change_rate']) and pd.notna(row['sales_change_rate']) and row['qty_change_rate'] >= 0 and row['sales_change_rate'] >= 0
        else '問題商品' if pd.notna(row['qty_change_rate']) and pd.notna(row['sales_change_rate']) and row['qty_change_rate'] >= 0 and row['sales_change_rate'] < 0
        else '金牛商品' if pd.notna(row['qty_change_rate']) and pd.notna(row['sales_change_rate']) and row['qty_change_rate'] < 0 and row['sales_change_rate'] >= 0
        else '瘦狗商品',
        axis=1,
    )
    colors = {
        '明星商品': '#22c55e',
        '問題商品': '#f59e0b',
        '金牛商品': '#2563eb',
        '瘦狗商品': '#ef4444',
    }

    # Cap change rates at +/- 500% for display purpose so chart scale is readable
    # but keep original values in customdata for Tooltip
    working['display_qty_rate'] = working['qty_change_rate'].clip(-5.0, 5.0)
    working['display_sales_rate'] = working['sales_change_rate'].clip(-5.0, 5.0)

    fig = go.Figure()
    for quadrant_name, subset in working.groupby('quadrant'):
        fig.add_scatter(
            x=subset['display_qty_rate'],
            y=subset['display_sales_rate'],
            mode='markers+text',
            name=quadrant_name,
            text=subset['item_code'],
            textposition='top center',
            marker=dict(
                size=subset['current_net_sales'].fillna(0).clip(lower=1).pow(0.5) / 6 + 12,
                color=colors.get(quadrant_name, '#64748b'),
                line=dict(color='#ffffff', width=1.2),
                opacity=0.84,
            ),
            customdata=subset[['item_name', 'item_prefix', 'current_net_sales', 'prior_net_sales', 'current_sales_qty', 'prior_sales_qty', 'qty_change_rate', 'sales_change_rate']].to_numpy(),
            hovertemplate='品號：%{text}<br>品名：%{customdata[0]}<br>餐點屬性碼：%{customdata[1]}<br>銷量變化：%{customdata[6]:+.1%}<br>未稅營收變化：%{customdata[7]:+.1%}<br>最新未稅營收：%{customdata[2]:,.0f}<br>上週同日未稅營收：%{customdata[3]:,.0f}<br>最新銷量：%{customdata[4]:,.0f}<br>上週同日銷量：%{customdata[5]:,.0f}<extra></extra>',
        )
    fig.add_hline(y=0, line=dict(color='#94a3b8', width=1.2, dash='dash'))
    fig.add_vline(x=0, line=dict(color='#94a3b8', width=1.2, dash='dash'))
    fig.add_annotation(x=0.02, y=0.98, xref='paper', yref='paper', text='金牛商品', showarrow=False, font=dict(size=12, color='#1d4ed8'))
    fig.add_annotation(x=0.98, y=0.98, xref='paper', yref='paper', text='明星商品', showarrow=False, xanchor='right', font=dict(size=12, color='#166534'))
    fig.add_annotation(x=0.02, y=0.02, xref='paper', yref='paper', text='瘦狗商品', showarrow=False, yanchor='bottom', font=dict(size=12, color='#b91c1c'))
    fig.add_annotation(x=0.98, y=0.02, xref='paper', yref='paper', text='問題商品', showarrow=False, xanchor='right', yanchor='bottom', font=dict(size=12, color='#92400e'))
    fig.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(family=FONT_FAMILY, size=12, color=TEXT_COLOR),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        height=560,
    )
    fig.update_xaxes(title='銷量變化 vs 上週同日', tickformat='.0%', showgrid=True, gridcolor=GRID_COLOR, zeroline=False)
    fig.update_yaxes(title='未稅營收變化 vs 上週同日', tickformat='.0%', showgrid=True, gridcolor=GRID_COLOR, zeroline=False)
    return fig


def _store_item_matrix_chart(df: pd.DataFrame) -> go.Figure:
    if df is None or df.empty:
        return go.Figure()

    item_meta = (
        df.groupby(['item_code', 'item_name', 'item_prefix'], as_index=False)['net_sales_value']
        .sum()
        .sort_values('net_sales_value', ascending=False)
    )
    item_order = item_meta['item_code'].tolist()
    item_name_map = dict(zip(item_meta['item_code'], item_meta['item_name']))
    item_prefix_map = dict(zip(item_meta['item_code'], item_meta['item_prefix']))
    store_order = (
        df.groupby('store_label', as_index=False)['store_total_net_sales']
        .max()
        .sort_values('store_total_net_sales', ascending=False)['store_label']
        .tolist()
    )

    share_pivot = (
        df.pivot_table(index='store_label', columns='item_code', values='share_rate', aggfunc='max')
        .reindex(index=store_order, columns=item_order)
        .fillna(0)
    )
    sales_pivot = (
        df.pivot_table(index='store_label', columns='item_code', values='net_sales_value', aggfunc='max')
        .reindex(index=store_order, columns=item_order)
        .fillna(0)
    )
    store_total_pivot = (
        df.pivot_table(index='store_label', columns='item_code', values='store_total_net_sales', aggfunc='max')
        .reindex(index=store_order, columns=item_order)
        .fillna(0)
    )

    customdata = []
    for store_label in store_order:
        row = []
        for item_code in item_order:
            row.append([
                item_prefix_map.get(item_code, '未分類'),
                item_prefix_map.get(item_code, '???'),
                float(sales_pivot.loc[store_label, item_code]),
                float(store_total_pivot.loc[store_label, item_code]),
            ])
        customdata.append(row)

    zmax = max(float(share_pivot.to_numpy().max()), 0.01)
    fig = go.Figure(
        data=go.Heatmap(
            x=item_order,
            y=store_order,
            z=share_pivot.to_numpy(),
            customdata=customdata,
            colorscale=[
                [0.0, '#fff7ed'],
                [0.45, '#fb923c'],
                [1.0, '#7c2d12'],
            ],
            zmin=0,
            colorbar=dict(title='未稅營收占比', tickformat='.0%'),
            hovertemplate='門市：%{y}<br>品號：%{x}<br>品名：%{customdata[0]}<br>餐點屬性碼：%{customdata[1]}<br>門市內未稅營收占比：%{z:.1%}<br>商品未稅營收：%{customdata[2]:,.0f}<br>門市商品總未稅營收：%{customdata[3]:,.0f}<extra></extra>',
        )
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(family=FONT_FAMILY, size=12, color=TEXT_COLOR),
        height=max(420, 56 * len(store_order) + 120),
    )
    fig.update_xaxes(title='', tickangle=-28, showgrid=False)
    fig.update_yaxes(title='', showgrid=False, autorange='reversed')
    return fig


def _product_price_band_chart(df: pd.DataFrame) -> go.Figure:
    colors = ['#fef3c7', '#fde68a', '#fdba74', '#fb923c', '#f97316', '#ea580c', '#9a3412']
    fig = go.Figure()
    fig.add_bar(
        x=df['price_band'],
        y=df['net_sales_value'],
        name='未稅營收',
        marker=dict(color=colors[: len(df)], line=dict(color='#ffffff', width=1)),
        text=df['net_sales_share'].map(lambda value: f'{value:.1%}'),
        textposition='outside',
        customdata=df[['sales_qty', 'txn_count', 'item_count', 'avg_unit_price', 'net_sales_share']].to_numpy(),
        hovertemplate='價格帶：%{x}<br>未稅營收：%{y:,.0f}<br>未稅營收占比：%{customdata[4]:.1%}<br>銷量：%{customdata[0]:,.0f}<br>交易筆數：%{customdata[1]:,.0f}<br>商品數：%{customdata[2]:,.0f}<br>平均售價：%{customdata[3]:,.1f}<extra></extra>',
    )
    fig.add_scatter(
        x=df['price_band'],
        y=df['sales_qty'],
        name='銷量',
        mode='lines+markers+text',
        yaxis='y2',
        line=dict(color='#7c2d12', width=3),
        marker=dict(color='#7c2d12', size=9, line=dict(color='#ffffff', width=1.2)),
        text=df['sales_qty'].map(lambda value: f'{value:,.0f}'),
        textposition='top center',
        hovertemplate='價格帶：%{x}<br>銷量：%{y:,.0f}<extra></extra>',
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(family=FONT_FAMILY, size=12, color=TEXT_COLOR),
        uniformtext_minsize=10,
        uniformtext_mode='hide',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        yaxis2=dict(title='銷量', overlaying='y', side='right', showgrid=False, zeroline=False, tickformat=',.0f'),
    )
    fig.update_xaxes(title='')
    fig.update_yaxes(title='未稅營收', showgrid=True, gridcolor=GRID_COLOR, zeroline=False, tickformat=',.0f')
    return fig


def _product_waterfall_chart(waterfall_df: pd.DataFrame) -> go.Figure:
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

    labels = [f'{prior_date} 商品未稅營收'] + ordered['label'].tolist()
    measures = ['absolute'] + ['relative'] * len(ordered)
    values = [total_prior] + ordered['net_sales_change'].tolist()
    texts = [f'{total_prior:,.0f}'] + [f'{value:+,.0f}' for value in ordered['net_sales_change']]
    customdata = [[
        '整體商品',
        '整體商品',
        total_current,
        total_prior,
        (total_delta / total_prior) if total_prior else None,
        latest_date,
        prior_date,
    ]]

    for row in ordered.itertuples(index=False):
        change_rate = ((row.current_net_sales - row.prior_net_sales) / row.prior_net_sales) if row.prior_net_sales else None
        customdata.append([
            getattr(row, 'item_name', 'N/A'),
            getattr(row, 'item_prefix', 'N/A'),
            row.current_net_sales,
            row.prior_net_sales,
            change_rate,
            latest_date,
            prior_date,
        ])

    if abs(other_delta) >= 1:
        labels.append('其他商品')
        measures.append('relative')
        values.append(other_delta)
        texts.append(f'{other_delta:+,.0f}')
        other_current = max(total_current - float(ordered['current_net_sales'].sum()), 0)
        other_prior = max(total_prior - float(ordered['prior_net_sales'].sum()), 0)
        other_rate = ((other_current - other_prior) / other_prior) if other_prior else None
        customdata.append([
            '其他商品合計',
            '其他分類',
            other_current,
            other_prior,
            other_rate,
            latest_date,
            prior_date,
        ])

    labels.append(f'{latest_date} 商品未稅營收')
    measures.append('total')
    values.append(total_current)
    texts.append(f'{total_current:,.0f}')
    customdata.append([
        '整體商品',
        '整體商品',
        total_current,
        total_prior,
        (total_delta / total_prior) if total_prior else None,
        latest_date,
        prior_date,
    ])

    fig = go.Figure(go.Waterfall(
        orientation='v',
        measure=measures,
        x=labels,
        y=values,
        text=texts,
        textposition='outside',
        customdata=customdata,
        connector={'line': {'color': '#d6d3d1', 'width': 1.2}},
        increasing={'marker': {'color': '#2f855a'}},
        decreasing={'marker': {'color': '#c53030'}},
        totals={'marker': {'color': '#2b6cb0'}},
        hovertemplate='品名：%{customdata[0]}<br>餐點屬性碼：%{customdata[1]}<br>%{customdata[5]} 未稅營收：%{customdata[2]:,.0f}<br>%{customdata[6]} 未稅營收：%{customdata[3]:,.0f}<br>變化金額：%{y:+,.0f}<br>變化率：%{customdata[4]:+.1%}<extra></extra>',
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


apply_page_style()
filters = render_sidebar_filters(page_key='product')

st.title('商品表現分析')
st.caption('聚焦商品排名、結構組成與表現差異，協助掌握主力商品與品類變化。')
st.info('提醒：本頁需要進行商品相關跑表運算，首次載入或變更篩選條件後可能需要稍候數秒，這屬於正常處理時間。')

prefix_export = get_item_prefix_rankings(filters=filters, limit=20).sort_values('net_sales_value', ascending=False)
item_export = get_item_code_rankings(filters=filters, limit=20).sort_values('net_sales_value', ascending=False)
prefix_rank = prefix_export
item_rank = item_export
# Expand date range for trend data to allow 91-day comparison regardless of sidebar filter
trend_filters = filters.copy() if filters else {}
if 'date_range' in trend_filters and isinstance(trend_filters['date_range'], (list, tuple)) and len(trend_filters['date_range']) == 2:
    start, end = trend_filters['date_range']
    # Ensure start is at least 100 days before end to cover QoQ (91 days)
    trend_filters['date_range'] = (min(start, end - timedelta(days=100)), end)

prefix_trend = get_item_prefix_daily_trend(filters=trend_filters, limit=120)
division_export = get_item_prefix_by_dimension('division', filters=filters, limit=20).sort_values('net_sales_value', ascending=False)
store_export = get_item_prefix_by_dimension('store', filters=filters, limit=20).sort_values('net_sales_value', ascending=False)
waterfall_df = get_item_change_waterfall(filters=filters, limit=8)
quadrant_df = get_item_net_sales_qty_quadrant(filters=filters, limit=20)
store_item_matrix_df = get_store_item_matrix(filters=filters, store_limit=10, item_limit=8)
price_band_df = get_item_price_band_distribution(filters=filters)

if prefix_rank.empty:
    prefix_metrics = None
    comparison = {'wow': None, 'mom': None, 'qoq': None}
else:
    total_sales = prefix_rank['net_sales_value'].sum()
    total_qty = prefix_rank['sales_qty'].sum()
    total_txn = prefix_rank['txn_count'].sum()
    prefix_metrics = {
        'net_sales_value': total_sales,
        'sales_qty': total_qty,
        'txn_count': total_txn,
        'avg_ticket': total_sales / total_txn if total_txn else None,
        'prefix_count': prefix_rank['mix_value'].nunique(),
    }
    comparison = _product_period_comparison(prefix_trend)

structure_df = _prepare_product_structure_data(prefix_trend, top_n=5)

content_gap('sm')
main_cards = [
    ('餐點屬性碼數', _fmt_metric(prefix_metrics.get('prefix_count') if prefix_metrics else None), '目前篩選條件下', 'neutral'),
    ('商品未稅營收', _fmt_metric(prefix_metrics.get('net_sales_value') if prefix_metrics else None), '目前篩選條件下', 'neutral'),
    ('商品交易筆數', _fmt_metric(prefix_metrics.get('txn_count') if prefix_metrics else None), '目前篩選條件下', 'neutral'),
    ('商品筆單價', _fmt_metric(prefix_metrics.get('avg_ticket') if prefix_metrics else None, 1), '目前篩選條件下', 'neutral'),
    ('商品銷量', _fmt_metric(prefix_metrics.get('sales_qty') if prefix_metrics else None), '目前篩選條件下', 'neutral'),
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
section_title('餐點屬性碼分析')
if prefix_rank.empty:
    st.info('目前查無餐點屬性碼資料。')
else:
    _render_wrapped_donut_legend(prefix_rank.head(10), 'mix_value', 'net_sales_value')
    donut_fig = donut_chart(prefix_rank.head(10), 'mix_value', 'net_sales_value', '餐點屬性碼未稅營收占比')
    donut_fig.update_layout(
        showlegend=False,
        margin=dict(l=20, r=20, t=72, b=40),
    )
    st.plotly_chart(donut_fig, use_container_width=True)

if prefix_trend.empty:
    st.info('目前查無餐點屬性碼趨勢資料。')
else:
    top_prefixes = prefix_rank.head(5)['mix_value'].tolist()
    # Only show last 30 days in chart for readability
    recent_dates = sorted(prefix_trend['biz_date'].unique())[-30:]
    trend_plot = prefix_trend[
        (prefix_trend['item_prefix'].isin(top_prefixes)) & 
        (prefix_trend['biz_date'].isin(recent_dates))
    ].copy()
    if trend_plot.empty:
        st.info('目前查無主要餐點屬性碼趨勢資料。')
    else:
        fig = px.line(
            trend_plot,
            x='biz_date',
            y='net_sales_value',
            color='item_prefix',
            title='近 30 天餐點屬性碼未稅營收趨勢',
            color_discrete_sequence=PRODUCT_COLORS,
        )
        fig.update_traces(
            line={'width': 3},
            marker={'size': 6},
            mode='lines+markers',
            hovertemplate='日期：%{x}<br>餐點屬性碼：%{fullData.name}<br>未稅營收：%{y:,.0f}<extra></extra>',
        )
        fig.update_layout(
            margin=dict(l=20, r=20, t=100, b=20),
            paper_bgcolor='white',
            plot_bgcolor='white',
            xaxis_title='',
            yaxis_title='',
            font=dict(family=FONT_FAMILY, size=13, color=TEXT_COLOR),
            title=dict(font=dict(size=18, color=TEXT_COLOR), x=0.02, xanchor='left', y=0.96),
            legend_title_text='',
            legend=dict(orientation='h', yanchor='bottom', y=1.10, xanchor='right', x=1),
        )
        fig.update_xaxes(showgrid=False, tickfont=dict(size=12), automargin=True)
        fig.update_yaxes(showgrid=True, gridcolor=GRID_COLOR, zeroline=False, tickfont=dict(size=12), automargin=True, tickformat=',.0f')
        st.plotly_chart(fig, use_container_width=True)
section_title('商品組合結構堆疊圖')
if structure_df.empty:
    st.info('目前查無商品組合結構資料。')
else:
    st.caption('這張圖看的是近 30 天各餐點屬性碼的未稅營收占比變化，方便快速判斷商品組合是否正在偏移。')
    status_panel('閱讀方式：每一根柱體代表一天，柱內不同顏色代表不同餐點屬性碼，整根柱體固定是 100%。如果某個顏色逐漸變厚，代表該屬性碼對整體商品未稅營收的占比正在提高；若逐漸變薄，表示商品結構正在被其他類別取代。')
    st.caption('建議先觀察前 5 大餐點屬性碼與「其他」的變化，再回頭對照瀑布圖與四象限圖，就能分辨是整體商品結構改變，還是少數單品短期波動。')
    st.plotly_chart(_product_structure_stacked_chart(structure_df), use_container_width=True, key='product-structure-stacked-chart')

section_title('商品銷售變化瀑布圖')
if waterfall_df.empty:
    st.info('目前查無商品銷售變化瀑布圖資料。')
else:
    latest_date = waterfall_df['latest_date'].iloc[0]
    prior_date = waterfall_df['prior_date'].iloc[0]
    st.caption(f'比較基準：{latest_date} vs {prior_date}，拆解這段期間主要拉升與拖累商品未稅營收的品號。')
    status_panel('閱讀方式：請由左到右看。最左邊藍色柱體是比較起點，也就是上週同日的商品未稅營收；中間綠色柱體代表拉升未稅營收的商品，紅色柱體代表拖累未稅營收的商品；最右邊藍色柱體是最新結果。若看到單一紅柱特別長，通常就是本期最值得優先追蹤的商品。')
    st.caption('這張圖不是看商品排名，而是看「誰造成變化」。建議先看紅綠柱最長的前幾項，再搭配下方熱門品號與屬性趨勢一起判斷，是短期波動、檔期結束，還是真的開始轉弱。')
    st.plotly_chart(_product_waterfall_chart(waterfall_df), use_container_width=True, key='product-waterfall-chart')

section_title('商品成長 / 衰退四象限圖')
if quadrant_df.empty:
    st.info('目前查無商品成長 / 衰退四象限資料。')
else:
    latest_date = quadrant_df['latest_date'].iloc[0]
    prior_date = quadrant_df['prior_date'].iloc[0]
    st.caption(f'比較基準：{latest_date} vs {prior_date}。每個點代表 1 個商品；點越大，代表該商品最新未稅營收越高。')
    status_panel('閱讀方式：右上角是「明星商品」，代表成長動能和未稅營收表現都強；左上角是「金牛商品」，代表成長放緩但仍能穩定撐住未稅營收；右下角是「問題商品」，代表有成長訊號但還沒把未稅營收真正帶上來；左下角是「瘦狗商品」，代表量與未稅營收同步轉弱，通常要優先檢討。')
    st.caption('建議先看左下角且點又大的「瘦狗商品」，通常就是這期最值得優先追蹤的弱勢商品；再看右下角的「問題商品」，確認它是不是有成長機會但尚未轉成真正的明星。滑鼠移到點上，可看品名、屬性碼、最新未稅營收、上週同日未稅營收、最新銷量與變化率。')
    st.plotly_chart(_product_sales_qty_quadrant_chart(quadrant_df), use_container_width=True, key='product-sales-qty-quadrant')

section_title('門市 × 商品矩陣熱力圖')
if store_item_matrix_df.empty:
    st.info('目前查無門市 × 商品矩陣資料。')
else:
    st.caption('這張圖用前 10 大門市與前 8 大商品做交叉比較，顏色代表該商品在該門市商品未稅營收中的占比。')
    status_panel('閱讀方式：橫軸是商品，縱軸是門市，顏色越深代表這個商品在該門市的未稅營收占比越高。先橫向看同一列，可判斷該門市是否過度依賴少數商品；再直向看同一欄，可找出哪些商品只在特定門市賣得特別強。')
    st.caption('建議先找深色特別集中的格子，通常代表單店強項或區域差異；如果同一商品在多數門市都偏淡，可能代表它雖然有賣，但不是帶動整體商品結構的主力。滑鼠移上去可看門市內未稅營收占比、商品未稅營收與該門市商品總未稅營收。')
    st.plotly_chart(_store_item_matrix_chart(store_item_matrix_df), use_container_width=True, key='store-item-matrix-chart')

section_title('價格帶分布圖')
if price_band_df.empty:
    st.info('目前查無價格帶分布資料。')
else:
    st.caption('這張圖依商品平均售價分成不同價格帶，幫助快速判斷目前未稅營收是由低價量體還是高價帶商品在支撐。')
    status_panel('閱讀方式：從左到右看不同價格帶的未稅營收高低，柱體越高代表該價格帶貢獻的未稅營收越大；柱上百分比是未稅營收占比。若某個價格帶未稅營收高但商品數不多，通常表示少數強勢商品在撐；若商品數多但未稅營收占比不高，則代表該價格帶品項分散、但單品帶動力有限。')
    st.caption('建議先看最高的 1 到 2 個價格帶，再用滑鼠確認它們的銷量、交易筆數、商品數與平均售價。這樣可以分辨目前成長是來自高價商品結構，還是來自低價帶的大量出貨。')
    st.plotly_chart(_product_price_band_chart(price_band_df), use_container_width=True, key='product-price-band-chart')

section_title('排行與差異')
content_gap('sm')
row2_left, row2_right = st.columns(2)
with row2_left:
    st.markdown('### 餐點屬性碼排行')
    if prefix_export.empty:
        st.info('目前查無餐點屬性碼排行。')
    else:
        show_prefix = prefix_export.copy()
        show_prefix = show_prefix.rename(columns={
            'mix_value': '項目',
            'net_sales_value': '未稅營收',
            'txn_count': '交易筆數',
            'sales_qty': '銷量'
        })
        for col_name in ['未稅營收', '交易筆數', '銷量']:
            show_prefix[col_name] = show_prefix[col_name].map(lambda x: f'{x:,.0f}')
        st.dataframe(show_prefix, use_container_width=True, hide_index=True)
with row2_right:
    st.markdown('### 熱門品號 Top 20')
    if item_export.empty:
        st.info('目前查無品號排行資料。')
    else:
        show_item = item_export.copy()
        show_item = show_item.rename(columns={
            'mix_value': '品號名稱',
            'net_sales_value': '未稅營收',
            'txn_count': '交易筆數',
            'sales_qty': '銷量'
        })
        for col_name in ['未稅營收', '交易筆數', '銷量']:
            show_item[col_name] = show_item[col_name].map(lambda x: f'{x:,.0f}')
        st.dataframe(show_item, use_container_width=True, hide_index=True)

row3_left, row3_right = st.columns(2)
with row3_left:
    if division_export.empty:
        st.info('目前查無處別商品結構資料。')
    else:
        top_division = division_export.copy()
        top_division['label_prefix'] = top_division['label'] + ' / ' + top_division['item_prefix']
        top_division = top_division.head(10).sort_values('net_sales_value')
        st.plotly_chart(bar_chart(top_division, 'label_prefix', 'net_sales_value', '處別餐點屬性碼排行', orientation='h'), use_container_width=True)
with row3_right:
    if store_export.empty:
        st.info('目前查無門市商品結構資料。')
    else:
        top_store = store_export.copy()
        top_store['label_prefix'] = top_store['label'] + ' / ' + top_store['item_prefix']
        top_store = top_store.head(10).sort_values('net_sales_value')
        st.plotly_chart(bar_chart(top_store, 'label_prefix', 'net_sales_value', '門市餐點屬性碼排行', orientation='h'), use_container_width=True)

section_title('商品明細分析表')
if item_export.empty:
    st.info('目前查無商品明細分析表。')
else:
    detail = item_export.rename(columns={
        'net_sales_value': '未稅營收',
        'txn_count': '交易筆數',
        'sales_qty': '銷量',
        'mix_value': '餐點屬性碼'
    })
    for col_name in ['未稅營收', '交易筆數', '銷量']:
        if col_name in detail.columns:
            detail[col_name] = detail[col_name].map(lambda x: f'{x:,.0f}')
    st.dataframe(detail, use_container_width=True, hide_index=True)


















