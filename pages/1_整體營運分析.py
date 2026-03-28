import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from src.charts import bar_chart, donut_chart
from src.etl import refresh_dataset
from src.filters import render_sidebar_filters
from src.session_manager import touch_current_page
from src.metrics import get_overview_metrics_for_filters, get_period_comparison
from src.services import get_daily_trend, get_group_rankings, get_last_etl_status, get_mix_daily_trend, get_mix_summary, get_store_anomaly_heatmap, get_store_change_waterfall, get_store_contribution_rankings, get_store_growth_rankings
from src.ui import apply_page_style, change_text, change_tone, content_gap, render_export_buttons, render_kpi_card, section_title, status_panel


HEATMAP_DAYS = 21

touch_current_page('pages/1_整體營運分析.py')
HEATMAP_STORE_LIMIT = 12

def _fmt_metric(value, digits=0):
    if value is None or pd.isna(value):
        return '-'
    return f'{value:,.{digits}f}'


def _job_status_text(status: str | None) -> str:
    mapping = {
        'success': '成功',
        'failed': '失敗',
        'running': '執行中',
    }
    return mapping.get(str(status).lower(), status or '-')


def _comparison_dates_text(comparison: dict, key: str) -> str:
    latest_date = comparison.get('latest_date')
    compare_date = comparison.get(f'{key}_date')
    if not latest_date or not compare_date:
        return '比較基準：日期資料不足'
    return f'比較基準：{latest_date} vs {compare_date}'

def _trend_summary(trend_df: pd.DataFrame) -> str:
    if trend_df is None or trend_df.empty or len(trend_df) < 14:
        return '近 100 天資料不足，暫時無法判讀走強或走弱幅度。'

    ordered = trend_df.sort_values('biz_date').tail(28).copy()
    recent = ordered.tail(14)['net_sales_value'].mean()
    prior = ordered.head(14)['net_sales_value'].mean()
    if pd.isna(recent) or pd.isna(prior) or prior == 0:
        return '近 100 天資料不足，暫時無法判讀走強或走弱幅度。'

    delta_amt = recent - prior
    delta_pct = delta_amt / prior
    direction = '走強' if delta_amt >= 0 else '走弱'
    return f'近 14 天日均未稅營收 {recent:,.0f}，較前 14 天{direction} {abs(delta_pct):.1%}，幅度約 {abs(delta_amt):,.0f} / 日。'


def _trend_bar_chart(trend_df: pd.DataFrame) -> go.Figure:
    ordered = trend_df.sort_values('biz_date').copy()
    ordered['rolling_7'] = ordered['net_sales_value'].rolling(7, min_periods=3).mean()
    ordered['rolling_14'] = ordered['net_sales_value'].rolling(14, min_periods=7).mean()
    ordered['momentum_color'] = ordered.apply(
        lambda row: '#22c55e' if pd.notna(row['rolling_14']) and row['net_sales_value'] >= row['rolling_14'] else '#f97316',
        axis=1,
    )

    fig = go.Figure()
    fig.add_bar(
        x=ordered['biz_date'],
        y=ordered['net_sales_value'],
        marker=dict(color=ordered['momentum_color'], line=dict(color='#ffffff', width=0.8)),
        name='每日未稅營收',
        hovertemplate='日期：%{x}<br>未稅營收：%{y:,.0f}<extra></extra>',
    )
    fig.add_scatter(
        x=ordered['biz_date'],
        y=ordered['rolling_7'],
        mode='lines',
        line=dict(color='#2563eb', width=3),
        name='7 日均線',
        hovertemplate='日期：%{x}<br>7 日均線：%{y:,.0f}<extra></extra>',
    )
    fig.add_scatter(
        x=ordered['biz_date'],
        y=ordered['rolling_14'],
        mode='lines',
        line=dict(color='#a855f7', width=2, dash='dash'),
        name='14 日基準',
        hovertemplate='日期：%{x}<br>14 日基準：%{y:,.0f}<extra></extra>',
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=64, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white',
        xaxis_title='',
        yaxis_title='',
        font=dict(family="'Segoe UI', 'Microsoft JhengHei', sans-serif", size=13, color='#14213d'),
        title=dict(text='近 100 天未稅營收趨勢', font=dict(size=18, color='#14213d'), x=0.02, xanchor='left'),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
    )
    fig.update_xaxes(showgrid=False, tickfont=dict(size=12), automargin=True)
    fig.update_yaxes(showgrid=True, gridcolor='#dbeafe', zeroline=False, tickfont=dict(size=12), automargin=True, tickformat=',.0f')
    return fig

def _sales_txn_dual_axis_chart(trend_df: pd.DataFrame) -> go.Figure:
    ordered = trend_df.sort_values('biz_date').tail(30).copy()
    ordered['biz_date'] = ordered['biz_date'].astype(str)
    ordered['txn_trend'] = ordered['txn_count'].rolling(7, min_periods=3).mean()

    fig = go.Figure()
    fig.add_bar(
        x=ordered['biz_date'],
        y=ordered['net_sales_value'],
        name='每日未稅營收',
        marker=dict(color='#2563eb', line=dict(color='#ffffff', width=0.8)),
        hovertemplate='日期：%{x}<br>未稅營收：%{y:,.0f}<extra></extra>',
        yaxis='y',
    )
    fig.add_scatter(
        x=ordered['biz_date'],
        y=ordered['txn_count'],
        mode='lines+markers',
        name='交易筆數',
        line=dict(color='#f97316', width=2.5),
        marker=dict(size=6, color='#f97316'),
        hovertemplate='日期：%{x}<br>交易筆數：%{y:,.0f}<extra></extra>',
        yaxis='y2',
    )
    fig.add_scatter(
        x=ordered['biz_date'],
        y=ordered['txn_trend'],
        mode='lines',
        name='交易筆數 7 日均線',
        line=dict(color='#ef4444', width=2, dash='dot'),
        hovertemplate='日期：%{x}<br>交易筆數 7 日均線：%{y:,.0f}<extra></extra>',
        yaxis='y2',
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=64, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(family="'Segoe UI', 'Microsoft JhengHei', sans-serif", size=13, color='#14213d'),
        title=dict(text='近 30 天未稅營收 vs 交易筆數', font=dict(size=18, color='#14213d'), x=0.02, xanchor='left'),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        yaxis=dict(title='', showgrid=True, gridcolor='#dbeafe', zeroline=False, tickformat=',.0f'),
        yaxis2=dict(title='', overlaying='y', side='right', showgrid=False, zeroline=False, tickformat=',.0f'),
        xaxis=dict(title='', showgrid=False),
        bargap=0.25,
    )
    fig.update_xaxes(tickangle=-35, automargin=True)
    return fig





def _momentum_snapshot(trend_df: pd.DataFrame) -> dict | None:
    if trend_df is None or trend_df.empty or len(trend_df) < 28:
        return None

    ordered = trend_df.sort_values('biz_date').tail(28).copy()
    recent_7 = ordered.tail(7)['net_sales_value'].mean()
    prior_7 = ordered.iloc[-14:-7]['net_sales_value'].mean()
    recent_14 = ordered.tail(14)['net_sales_value'].mean()
    prior_14 = ordered.head(14)['net_sales_value'].mean()

    if pd.isna(recent_7) or pd.isna(prior_7) or pd.isna(recent_14) or pd.isna(prior_14) or prior_7 == 0 or prior_14 == 0:
        return None

    pct_7 = (recent_7 - prior_7) / prior_7
    pct_14 = (recent_14 - prior_14) / prior_14
    score = max(min((pct_7 * 0.6) + (pct_14 * 0.4), 0.30), -0.30)

    if score >= 0.03:
        direction = '走強'
    elif score <= -0.03:
        direction = '轉弱'
    else:
        direction = '持平'

    return {
        'recent_7': recent_7,
        'prior_7': prior_7,
        'recent_14': recent_14,
        'prior_14': prior_14,
        'pct_7': pct_7,
        'pct_14': pct_14,
        'score': score,
        'direction': direction,
    }

def _momentum_summary(trend_df: pd.DataFrame) -> str:
    snapshot = _momentum_snapshot(trend_df)
    if not snapshot:
        return '資料不足，暫時無法計算未稅營收動能。'
    return f"動能判讀：目前屬於{snapshot['direction']}。近 7 天日均未稅營收較前 7 天 {snapshot['pct_7']:+.1%}，近 14 天日均未稅營收較前 14 天 {snapshot['pct_14']:+.1%}。"

def _momentum_gauge_chart(trend_df: pd.DataFrame) -> go.Figure:
    snapshot = _momentum_snapshot(trend_df)
    score = 0 if not snapshot else snapshot['score'] * 100
    direction = '資料不足' if not snapshot else snapshot['direction']
    bar_color = "#22c55e" if score >= 3 else "#ef4444" if score <= -3 else "#f59e0b"

    fig = go.Figure(go.Indicator(
        mode='gauge+number+delta',
        value=score,
        number={'suffix': "%", 'valueformat': ".1f"},
        delta={'reference': 0, 'relative': False, 'valueformat': ".1f"},
        title={'text': f"<b>{direction}</b><br><span style=\"font-size:0.85em\">近 7 / 14 天動能綜合分數</span>"},
        gauge={
            'axis': {'range': [-30, 30], 'tickvals': [-30, -15, 0, 15, 30]},
            'bar': {'color': bar_color},
            'steps': [
                {'range': [-30, -8], 'color': '#fee2e2'},
                {'range': [-8, 8], 'color': '#fef3c7'},
                {'range': [8, 30], 'color': '#dcfce7'},
            ],
            'threshold': {'line': {'color': '#14213d', 'width': 3}, 'thickness': 0.8, 'value': score},
        },
    ))
    fig.update_layout(
        margin=dict(l=20, r=20, t=40, b=10),
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(family="'Segoe UI', 'Microsoft JhengHei', sans-serif", size=12, color='#14213d'),
        height=320,
    )
    return fig

def _waterfall_chart(waterfall_df: pd.DataFrame) -> go.Figure:
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
        labels.append('其他門市')
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
        hovertemplate='%{x}<br>金額：%{y:,.0f}<extra></extra>',
        cliponaxis=False,
    ))
    fig.update_layout(
        margin=dict(l=20, r=20, t=20, b=24),
        paper_bgcolor='white',
        plot_bgcolor='white',
        showlegend=False,
        font=dict(family="'Segoe UI', 'Microsoft JhengHei', sans-serif", size=12, color='#14213d'),
    )
    fig.update_xaxes(showgrid=False, tickangle=-20, automargin=True)
    fig.update_yaxes(showgrid=True, gridcolor='#dbeafe', zeroline=False, tickformat=',.0f', automargin=True)
    return fig



def _heatmap_summary(heatmap_df: pd.DataFrame) -> str:
    if heatmap_df is None or heatmap_df.empty:
        return '目前資料不足，暫時無法判讀門市異常。'

    working = heatmap_df.copy()
    recent_dates = sorted(working['biz_date'].astype(str).unique())[-7:]
    recent = working[working['biz_date'].astype(str).isin(recent_dates)].copy()
    weak = recent[recent['deviation_rate'] <= -0.10]
    strong = recent[recent['deviation_rate'] >= 0.10]

    messages = []
    if not weak.empty:
        weak_store = weak.groupby('label').size().sort_values(ascending=False)
        weak_day = weak.groupby('biz_date').size().sort_values(ascending=False)
        messages.append(f"近期偏弱最多：{weak_store.index[0]} 有 {int(weak_store.iloc[0])} 天低於自身平均 10% 以上")
        messages.append(f"同步偏弱最明顯：{str(weak_day.index[0])} 有 {int(weak_day.iloc[0])} 家門市偏弱")
    if not strong.empty:
        strong_store = strong.groupby('label').size().sort_values(ascending=False)
        messages.append(f"近期拉升最多：{strong_store.index[0]} 有 {int(strong_store.iloc[0])} 天高於自身平均 10% 以上")

    if not messages:
        return '近 7 天多數門市表現接近各自平均，未見明顯連續異常。'
    return '觀察重點：' + '；'.join(messages) + '。'


def _store_contribution_chart(df: pd.DataFrame) -> go.Figure:
    working = df.copy()
    working = working.sort_values('net_sales_change', ascending=True)
    colors = ['#ef4444' if value < 0 else '#22c55e' for value in working['net_sales_change']]
    fig = go.Figure()
    fig.add_bar(
        x=working['net_sales_change'],
        y=working['label'],
        orientation='h',
        marker=dict(color=colors, line=dict(color='#ffffff', width=1.2)),
        text=working['net_sales_change'].map(lambda v: f'{v:+,.0f}'),
        textposition='outside',
        cliponaxis=False,
        customdata=working[['current_net_sales', 'prior_net_sales']].to_numpy(),
        hovertemplate='門市：%{y}<br>貢獻差額：%{x:+,.0f}<br>最新未稅營收：%{customdata[0]:,.0f}<br>上週同日：%{customdata[1]:,.0f}<extra></extra>',
    )
    fig.update_layout(
        margin=dict(l=20, r=40, t=20, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white',
        showlegend=False,
        font=dict(family="'Segoe UI', 'Microsoft JhengHei', sans-serif", size=12, color='#14213d'),
        height=max(320, 40 * len(working) + 120),
    )
    fig.update_xaxes(showgrid=True, gridcolor='#dbeafe', zeroline=True, zerolinecolor='#94a3b8', tickformat=',.0f', automargin=True)
    fig.update_yaxes(showgrid=False, automargin=True)
    return fig


def _prepare_stacked_mix_data(df: pd.DataFrame, top_n: int = 4) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=['biz_date', 'mix_value', 'net_sales_value', 'share'])

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
    grouped = working.groupby(['biz_date', 'mix_bucket'], as_index=False)['net_sales_value'].sum()
    totals = grouped.groupby('biz_date', as_index=False)['net_sales_value'].sum().rename(columns={'net_sales_value': 'total_sales'})
    grouped = grouped.merge(totals, on='biz_date', how='left')
    grouped['share'] = grouped['net_sales_value'] / grouped['total_sales']
    return grouped.rename(columns={'mix_bucket': 'mix_value'}).sort_values(['biz_date', 'mix_value'])


def _stacked_mix_chart(df: pd.DataFrame) -> go.Figure:
    order = (
        df.groupby('mix_value', as_index=False)['net_sales_value']
        .sum()
        .sort_values('net_sales_value', ascending=False)['mix_value']
        .tolist()
    )
    colors = {
        '外帶': '#2563eb',
        '內用': '#22c55e',
        '外送': '#f97316',
        '外送平台': '#a855f7',
        '其他': '#94a3b8',
        '未分類': '#06b6d4',
    }
    fig = go.Figure()
    for label in order:
        subset = df[df['mix_value'] == label].copy()
        fig.add_bar(
            x=subset['biz_date'].astype(str),
            y=subset['share'],
            name=label,
            marker=dict(color=colors.get(label, '#64748b')),
            customdata=subset[['net_sales_value']].to_numpy(),
            hovertemplate='日期：%{x}<br>類別：' + label + '<br>占比：%{y:.1%}<br>未稅營收：%{customdata[0]:,.0f}<extra></extra>',
        )
    fig.update_layout(
        barmode='stack',
        barnorm='fraction',
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(family="'Segoe UI', 'Microsoft JhengHei', sans-serif", size=12, color='#14213d'),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
    )
    fig.update_xaxes(showgrid=False, tickangle=-35, automargin=True)
    fig.update_yaxes(showgrid=True, gridcolor='#dbeafe', zeroline=False, tickformat='.0%', automargin=True)
    return fig


def _store_heatmap_chart(heatmap_df: pd.DataFrame) -> go.Figure:
    working = heatmap_df.copy()
    working['biz_date'] = working['biz_date'].astype(str)
    working['deviation_display'] = working['deviation_rate'].clip(-0.4, 0.4)

    store_order = working.groupby('label')['net_sales_value'].sum().sort_values(ascending=False).index.tolist()
    date_order = sorted(working['biz_date'].unique())

    pivot_dev = working.pivot(index='label', columns='biz_date', values='deviation_display').reindex(index=store_order, columns=date_order)
    pivot_raw = working.pivot(index='label', columns='biz_date', values='deviation_rate').reindex(index=store_order, columns=date_order)
    pivot_sales = working.pivot(index='label', columns='biz_date', values='net_sales_value').reindex(index=store_order, columns=date_order)
    pivot_avg = working.pivot(index='label', columns='biz_date', values='avg_net_sales').reindex(index=store_order, columns=date_order)

    hover_text = []
    for store in pivot_dev.index:
        row_text = []
        for biz_date in pivot_dev.columns:
            raw_value = pivot_raw.loc[store, biz_date]
            sales_value = pivot_sales.loc[store, biz_date]
            avg_value = pivot_avg.loc[store, biz_date]
            if pd.isna(raw_value):
                row_text.append(f'門市：{store}<br>日期：{biz_date}<br>無資料')
            else:
                row_text.append(
                    f'門市：{store}<br>日期：{biz_date}<br>當日未稅營收：{sales_value:,.0f}<br>門市近 21 天平均：{avg_value:,.0f}<br>相對平均：{raw_value:+.1%}'
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
        colorbar=dict(title='相對平均', tickformat='.0%'),
    ))
    fig.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(family="'Segoe UI', 'Microsoft JhengHei', sans-serif", size=12, color='#14213d'),
        height=max(380, 42 * len(store_order) + 120),
    )
    fig.update_xaxes(showgrid=False, tickangle=-35, automargin=True)
    fig.update_yaxes(showgrid=False, automargin=True, autorange='reversed')
    return fig
def _prepare_mix_bar_data(df: pd.DataFrame, label_col: str = 'mix_value', value_col: str = 'net_sales_value', top_n: int = 6, empty_label: str = '未分類', other_label: str = '其他') -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=[label_col, value_col, 'share'])

    working = df[[label_col, value_col]].copy()
    working[label_col] = working[label_col].fillna('').astype(str).str.strip()
    working[label_col] = working[label_col].replace({'': '未分類', '?': '未分類', '??': '未分類', 'nan': '未分類', 'None': '未分類'})
    working = working.sort_values(value_col, ascending=False)
    if len(working) > top_n:
        top = working.head(top_n - 1).copy()
        other_value = working.iloc[top_n - 1:][value_col].sum()
        top = pd.concat([top, pd.DataFrame([{label_col: '其他', value_col: other_value}])], ignore_index=True)
        working = top

    total = working[value_col].sum()
    working['share'] = working[value_col] / total if total else 0
    return working.sort_values(value_col, ascending=True)


def _mix_bar_chart(df: pd.DataFrame) -> go.Figure:
    colors = ['#2563eb', '#f97316', '#06b6d4', '#22c55e', '#a855f7', '#ef4444']
    fig = go.Figure()
    fig.add_bar(
        x=df['share'],
        y=df['mix_value'],
        orientation='h',
        text=df['share'].map(lambda x: f'{x:.1%}'),
        textposition='outside',
        cliponaxis=False,
        marker=dict(color=colors[:len(df)], line=dict(color='#ffffff', width=1.2)),
        customdata=df[['net_sales_value']].to_numpy(),
        hovertemplate='項目：%{y}<br>占比：%{x:.1%}<br>未稅營收：%{customdata[0]:,.0f}<extra></extra>',
    )
    fig.update_layout(
        margin=dict(l=20, r=48, t=12, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white',
        xaxis_title='',
        yaxis_title='',
        showlegend=False,
        font=dict(family="'Segoe UI', 'Microsoft JhengHei', sans-serif", size=12, color='#14213d'),
    )
    fig.update_xaxes(showgrid=True, gridcolor='#dbeafe', zeroline=False, tickformat='.0%', automargin=True)
    fig.update_yaxes(showgrid=False, automargin=True, tickfont=dict(size=12))
    return fig



apply_page_style()
filters = render_sidebar_filters(page_key='overview')

st.title('營業現況分析版')
st.caption('整合最新營運表現、趨勢變化與門市異常訊號，快速掌握整體經營重點。')

top_left, top_right = st.columns([3, 1])
with top_right:
    if st.button('更新近 100 天資料', use_container_width=True):
        with st.spinner('正在更新近 100 天資料...'):
            try:
                result = refresh_dataset(run_type='manual')
                st.success(f"資料更新完成，共載入 {result['rows_loaded']:,} 筆資料，期間 {result['date_from']} ~ {result['date_to']}")
            except Exception as exc:
                st.error(f'資料更新失敗：{exc}')

status = get_last_etl_status()
with top_left:
    if status:
        status_panel(f"最近更新：{status['end_time']} | 狀態：{_job_status_text(status['status'])} | 資料期間：{status['date_from']} ~ {status['date_to']} | 筆數：{status['rows_loaded']:,}")
    else:
        st.warning('目前查無最近一次資料更新紀錄。')

metrics = get_overview_metrics_for_filters(filters)
comparison = get_period_comparison(filters)
trend = get_daily_trend(filters=filters)
mix_txn = get_mix_summary('txn_type', filters=filters, limit=10).sort_values('net_sales_value', ascending=False)
mix_payment = get_mix_summary('payment_type', filters=filters, limit=10).sort_values('net_sales_value', ascending=False)
mix_item = get_mix_summary('item_prefix', filters=filters, limit=12).sort_values('net_sales_value', ascending=False)
stacked_mix_txn = get_mix_daily_trend('txn_type', filters=filters, limit=30)
rank_store = get_group_rankings('store', filters=filters, limit=10).sort_values('net_sales_value', ascending=False)
growth_best = get_store_growth_rankings(filters=filters, limit=10, worst=False).sort_values('growth_rate', ascending=False, na_position='last')
growth_worst = get_store_growth_rankings(filters=filters, limit=10, worst=True).sort_values('growth_rate', ascending=True, na_position='last')
contribution_df = get_store_contribution_rankings(filters=filters, limit=5)
waterfall_df = get_store_change_waterfall(filters=filters, limit=8)
heatmap_df = get_store_anomaly_heatmap(filters=filters, days=HEATMAP_DAYS, store_limit=HEATMAP_STORE_LIMIT)

# 準備匯出/顯示用的數據框
store_export = rank_store.copy() if not rank_store.empty else pd.DataFrame()
if not store_export.empty:
    store_export = store_export.rename(columns={
        'label': '門市',
        'net_sales_value': '未稅營收',
        'txn_count': '交易筆數',
        'avg_ticket': '筆單價'
    })

growth_best_export = growth_best.copy() if not growth_best.empty else pd.DataFrame()
if not growth_best_export.empty:
    growth_best_export = growth_best_export.rename(columns={
        'label': '門市',
        'current_net_sales': '昨日未稅營收',
        'prior_net_sales': '上週同日未稅營收',
        'growth_rate': '增減率'
    })

growth_worst_export = growth_worst.copy() if not growth_worst.empty else pd.DataFrame()
if not growth_worst_export.empty:
    growth_worst_export = growth_worst_export.rename(columns={
        'label': '門市',
        'current_net_sales': '昨日未稅營收',
        'prior_net_sales': '上週同日未稅營收',
        'growth_rate': '增減率'
    })


content_gap('sm')
main_cards = [
    ('昨日未稅營收', _fmt_metric(metrics.get('net_sales_value') if metrics else None), '截至最新營業日', 'neutral'),
    ('昨日交易筆數', _fmt_metric(metrics.get('txn_count') if metrics else None), '截至最新營業日', 'neutral'),
    ('昨日筆單價', _fmt_metric(metrics.get('avg_ticket') if metrics else None, 1), '截至最新營業日', 'neutral'),
    ('昨日銷量', _fmt_metric(metrics.get('sales_qty') if metrics else None), '截至最新營業日', 'neutral'),
    ('與上週同星期相比', '-' if comparison.get('wow') is None else f"{comparison.get('wow'):+.1%}", _comparison_dates_text(comparison, 'wow'), change_tone(comparison.get('wow'))),
    ('與上月同期相比', '-' if comparison.get('mom') is None else f"{comparison.get('mom'):+.1%}", _comparison_dates_text(comparison, 'mom'), change_tone(comparison.get('mom'))),
    ('與上季同期相比', '-' if comparison.get('qoq') is None else f"{comparison.get('qoq'):+.1%}", _comparison_dates_text(comparison, 'qoq'), change_tone(comparison.get('qoq'))),
]
for variant, card_group in [('core', main_cards[:4]), ('compare', main_cards[4:])]:
    row_cols = st.columns(4)
    for col, (label, value, subtext, tone) in zip(row_cols, card_group):
        with col:
            render_kpi_card(label, value, subtext, tone, variant=variant)
    content_gap('sm')

content_gap('md')
section_title('營運趨勢')
status_panel(_trend_summary(trend))
st.caption('圖例說明：綠色柱體 = 高於 14 日基準，代表近期表現偏強；橘色柱體 = 低於 14 日基準，代表近期表現偏弱。')
if trend.empty:
    st.info('目前查無趨勢資料。')
else:
    st.plotly_chart(_trend_bar_chart(trend), use_container_width=True, key='overview-trend-chart')

section_title('未稅營收 vs 交易筆數雙軸圖')
if trend.empty:
    st.info('目前查無未稅營收與交易筆數比較資料。')
else:
    st.caption('閱讀方式：藍色柱體看每日未稅營收，橘色折線看交易筆數，紅色虛線看交易筆數近 7 日均線。若未稅營收下降且交易筆數也下降，通常代表來客減少；若交易筆數持平但未稅營收下降，則較可能是客單價轉弱。')
    st.plotly_chart(_sales_txn_dual_axis_chart(trend), use_container_width=True, key='overview-sales-txn-dual-axis')

section_title('未稅營收動能儀表圖')
if trend.empty or len(trend) < 28:
    st.info('目前資料不足，暫時無法顯示未稅營收動能儀表圖。')
else:
    status_panel(_momentum_summary(trend))
    st.caption('閱讀方式：這張儀表圖會綜合比較近 7 天與近 14 天的日均未稅營收，分別與各自的前一期相比。指針越偏右代表動能越強，越偏左代表動能越弱，接近 0 則代表大致持平。')
    st.plotly_chart(_momentum_gauge_chart(trend), use_container_width=True, key='overview-revenue-momentum-gauge')

section_title('未稅營收變化瀑布圖')
if waterfall_df.empty:
    st.info('目前查無未稅營收變化瀑布圖資料。')
else:
    latest_date = waterfall_df['latest_date'].iloc[0]
    prior_date = waterfall_df['prior_date'].iloc[0]
    st.caption(f'比較基準：{latest_date} vs {prior_date}，拆解主要拉升與拖累未稅營收的門市。')
    status_panel('閱讀方式：請由左到右看。藍色柱體代表比較起點與最新結果；綠色柱體代表拉升未稅營收；紅色柱體代表拖累未稅營收；「其他門市」代表未列入前幾名門市的合計影響。')
    st.plotly_chart(_waterfall_chart(waterfall_df), use_container_width=True, key='overview-waterfall-chart')

section_title('門市異常熱力圖')
if heatmap_df.empty:
    st.info('目前查無門市異常熱力圖資料。')
else:
    st.caption(f'顯示範圍：最近 {HEATMAP_DAYS} 天、累計未稅營收前 {HEATMAP_STORE_LIMIT} 家門市，並依這 {HEATMAP_DAYS} 天累積未稅營收由高到低排序，最高者排在最上方。之所以只顯示這幾家，是為了讓熱力圖維持可閱讀性，避免門市過多時每一列過薄、異常訊號被稀釋；未列入的其他門市不是沒有資料，而是暫時不在這張總覽圖的顯示名單中。')
    status_panel(_heatmap_summary(heatmap_df))
    st.caption('觀察重點更新方式：這段摘要會跟著目前篩選條件與最新資料自動重算，只要日期區間、縣市、處別或資料更新了，內容就會一起變動。')
    st.caption('閱讀方式：橫軸是日期、縱軸是門市。每一格都代表 1 家門市在 1 天的表現；綠色越深表示高於該門市近 21 天平均越多，紅色越深表示低於平均越多，接近淺色代表接近平均。建議先橫向看單一門市是否連續轉弱，再縱向看是否有同日多店同步異常。')
    st.plotly_chart(_store_heatmap_chart(heatmap_df), use_container_width=True, key='overview-heatmap-chart')

section_title('結構變化堆疊圖')
if stacked_mix_txn.empty:
    st.info('目前查無結構變化堆疊圖資料。')
else:
    stacked_txn_chart = _prepare_stacked_mix_data(stacked_mix_txn, top_n=4)
    st.caption('閱讀方式：這張圖看的是「佔比變化」，不是「絕對未稅營收」。每一天的直條都代表 100% 交易型態結構；如果某種顏色逐漸變厚，代表那種交易型態在結構中的佔比正在提升。')
    st.caption('圖表設定：顯示近 30 天、累計未稅營收前 4 大交易型態，其餘合併為「其他」。')
    st.plotly_chart(_stacked_mix_chart(stacked_txn_chart), use_container_width=True, key='overview-structure-stacked-chart')

section_title('結構分析')
row2_col1, row2_col2, row2_col3 = st.columns(3)
with row2_col1:
    st.markdown('### 交易型態占比')
    txn_chart_df = _prepare_mix_bar_data(mix_txn, top_n=5, empty_label='未分類交易型態', other_label='其他交易型態')
    if txn_chart_df.empty:
        st.info('目前查無交易型態資料。')
    else:
        st.plotly_chart(_mix_bar_chart(txn_chart_df), use_container_width=True)
with row2_col2:
    st.markdown('### 付款別占比')
    payment_chart_df = _prepare_mix_bar_data(mix_payment, top_n=6, empty_label='未分類付款', other_label='其他付款別')
    if payment_chart_df.empty:
        st.info('目前查無付款別資料。')
    else:
        st.plotly_chart(_mix_bar_chart(payment_chart_df), use_container_width=True)
with row2_col3:
    st.markdown('### 餐點屬性碼占比')
    item_chart_df = _prepare_mix_bar_data(mix_item, top_n=6, empty_label='未分類屬性', other_label='其他屬性碼')
    if item_chart_df.empty:
        st.info('目前查無餐點屬性資料。')
    else:
        st.plotly_chart(_mix_bar_chart(item_chart_df), use_container_width=True)
section_title('門市觀察')
row3_left, row3_right = st.columns(2)
with row3_left:
    st.markdown('### 門市排行')
    if rank_store.empty:
        st.info('目前查無門市排行資料。')
    else:
        show_rank = store_export.copy()
        for col_name in ['未稅營收', '交易筆數']:
            show_rank[col_name] = show_rank[col_name].map(lambda x: f'{x:,.0f}')
        show_rank['筆單價'] = show_rank['筆單價'].map(lambda x: '-' if pd.isna(x) else f'{x:,.1f}')
        st.dataframe(show_rank, use_container_width=True, hide_index=True)
with row3_right:
    if rank_store.empty:
        st.info('目前查無門市圖表資料。')
    else:
        top_store = rank_store.head(10).copy().sort_values('net_sales_value')
        st.plotly_chart(bar_chart(top_store, 'label', 'net_sales_value', '門市未稅營收排行 Top 10', orientation='h'), use_container_width=True)


section_title('Top/Bottom 門市貢獻圖')
if contribution_df.empty:
    st.info('目前查無 Top/Bottom 門市貢獻圖資料。')
else:
    latest_date = contribution_df['latest_date'].iloc[0]
    prior_date = contribution_df['prior_date'].iloc[0]
    st.caption(f'比較基準：{latest_date} vs {prior_date}。這張圖拆解對整體未稅營收影響最大的門市，區分哪些在拉升、哪些在拖累。')
    st.caption('閱讀方式：往右的綠色長條代表「拉升整體未稅營收」的門市，而且長條越長、拉升金額越多；往左的紅色長條代表「拖累整體未稅營收」的門市，而且長條越長、拖累幅度越明顯。這張圖看的是「貢獻金額」，不是「增減率」。')
    status_panel('快速判讀：先看右側綠棒，可知哪些門市是近期成長主力；再看左側紅棒，可知哪些門市正在拉低整體表現。若綠棒總量大於紅棒總量，代表整體貢獻偏正向；反之則代表拖累壓力較大。')
    st.plotly_chart(_store_contribution_chart(contribution_df), use_container_width=True, key='overview-store-contribution-chart')
section_title('異常門市')
row4_col1, row4_col2 = st.columns(2)
with row4_col1:
    st.markdown('### 成長前10門市')
    if growth_best.empty:
        st.info('目前查無成長排行資料。')
    else:
        best = growth_best_export.copy()
        for col_name in ['昨日未稅營收', '上週同日未稅營收']:
            best[col_name] = best[col_name].map(lambda x: '-' if pd.isna(x) else f'{x:,.0f}')
        best['增減率'] = best['增減率'].map(lambda x: '-' if pd.isna(x) else f'{x:.1%}')
        st.dataframe(best, use_container_width=True, hide_index=True)
with row4_col2:
    st.markdown('### 衰退前10門市')
    if growth_worst.empty:
        st.info('目前查無衰退排行資料。')
    else:
        worst = growth_worst_export.copy()
        for col_name in ['昨日未稅營收', '上週同日未稅營收']:
            worst[col_name] = worst[col_name].map(lambda x: '-' if pd.isna(x) else f'{x:,.0f}')
        worst['增減率'] = worst['增減率'].map(lambda x: '-' if pd.isna(x) else f'{x:.1%}')
        st.dataframe(worst, use_container_width=True, hide_index=True)




