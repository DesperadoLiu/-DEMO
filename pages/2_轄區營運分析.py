import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from html import escape

from src.filters import render_sidebar_filters
from src.session_manager import touch_current_page
from src.metrics import get_overview_metrics_for_filters, get_period_comparison
from src.services import (
    get_daily_trend,
    get_recent_daily_table,
    get_store_anomaly_heatmap,
    get_store_contribution_rankings,
    get_store_customer_ticket_quadrant,
    get_store_growth_rankings,
    get_store_mix_structure_trend,
    get_store_risk_matrix,
)
from src.ui import apply_page_style, change_text, change_tone, content_gap, render_export_buttons, render_kpi_card, section_title, status_panel

touch_current_page('pages/2_轄區營運分析.py')


HEATMAP_DAYS = 21
HEATMAP_STORE_LIMIT = 12
PRIORITY_LIMIT = 4


def _fmt_metric(value, digits=0):
    if value is None or pd.isna(value):
        return '-'
    return f'{value:,.{digits}f}'


def _apply_supervisor_page_style():
    st.markdown(
        """
        <style>
        .supervisor-priority-card {
            border-radius: 20px;
            border: 1px solid #dbe7ff;
            background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
            box-shadow: 0 14px 30px rgba(37, 99, 235, 0.08);
            padding: 1rem 1rem 0.95rem 1rem;
            min-height: 320px;
        }
        .supervisor-priority-card.critical {
            border-color: #fca5a5;
            background: linear-gradient(180deg, #fff7f7 0%, #fee2e2 100%);
            box-shadow: 0 16px 32px rgba(220, 38, 38, 0.12);
        }
        .supervisor-priority-card.warning {
            border-color: #fdba74;
            background: linear-gradient(180deg, #fffaf5 0%, #ffedd5 100%);
            box-shadow: 0 16px 32px rgba(234, 88, 12, 0.10);
        }
        .supervisor-priority-card.stable {
            border-color: #bfdbfe;
        }
        .supervisor-priority-badge {
            display: inline-block;
            padding: 0.28rem 0.56rem;
            border-radius: 999px;
            font-size: 0.8rem;
            font-weight: 800;
            margin-bottom: 0.7rem;
        }
        .supervisor-priority-card.critical .supervisor-priority-badge {
            background: #b91c1c;
            color: #ffffff;
        }
        .supervisor-priority-card.warning .supervisor-priority-badge {
            background: #c2410c;
            color: #ffffff;
        }
        .supervisor-priority-card.stable .supervisor-priority-badge {
            background: #dbeafe;
            color: #1d4ed8;
        }
        .supervisor-priority-title {
            color: #0f172a;
            font-size: 1.05rem;
            font-weight: 900;
            line-height: 1.35;
            margin-bottom: 0.2rem;
        }
        .supervisor-priority-score {
            color: #475569;
            font-size: 0.84rem;
            font-weight: 700;
            margin-bottom: 0.7rem;
        }
        .supervisor-priority-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.55rem;
            margin: 0.7rem 0 0.85rem 0;
        }
        .supervisor-priority-metric {
            border-radius: 14px;
            background: rgba(255, 255, 255, 0.88);
            border: 1px solid rgba(203, 213, 225, 0.75);
            padding: 0.55rem 0.65rem;
        }
        .supervisor-priority-label {
            color: #64748b;
            font-size: 0.72rem;
            font-weight: 700;
            margin-bottom: 0.18rem;
        }
        .supervisor-priority-value {
            color: #0f172a;
            font-size: 1.02rem;
            font-weight: 900;
            line-height: 1.1;
        }
        .supervisor-priority-reason {
            color: #1e293b;
            font-size: 0.88rem;
            line-height: 1.55;
            margin-top: 0.35rem;
        }
        .supervisor-priority-action {
            margin-top: 0.85rem;
            border-radius: 14px;
            background: rgba(255, 255, 255, 0.92);
            border: 1px dashed #cbd5e1;
            padding: 0.7rem 0.8rem;
            color: #0f172a;
            font-size: 0.88rem;
            line-height: 1.5;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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

def _build_sync_anomaly_calendar_df(heatmap_df: pd.DataFrame) -> pd.DataFrame:
    if heatmap_df is None or heatmap_df.empty:
        return pd.DataFrame(columns=['biz_date', 'weak_store_count', 'strong_store_count', 'observed_store_count', 'weak_ratio', 'week_label', 'weekday_label', 'weekday_num', 'date_label'])

    working = heatmap_df.copy()
    working['biz_date'] = pd.to_datetime(working['biz_date'])
    daily = (
        working.groupby('biz_date')
        .agg(
            weak_store_count=('deviation_rate', lambda s: int((s <= -0.10).sum())),
            strong_store_count=('deviation_rate', lambda s: int((s >= 0.10).sum())),
            observed_store_count=('label', 'nunique'),
        )
        .reset_index()
        .sort_values('biz_date')
    )
    daily['weak_ratio'] = daily['weak_store_count'] / daily['observed_store_count'].replace(0, pd.NA)
    daily['week_start'] = daily['biz_date'] - pd.to_timedelta(daily['biz_date'].dt.weekday, unit='D')
    daily['week_label'] = daily['week_start'].dt.strftime('%m/%d 週')
    daily['weekday_num'] = daily['biz_date'].dt.weekday
    weekday_map = {0: '週一', 1: '週二', 2: '週三', 3: '週四', 4: '週五', 5: '週六', 6: '週日'}
    daily['weekday_label'] = daily['weekday_num'].map(weekday_map)
    daily['date_label'] = daily['biz_date'].dt.strftime('%Y-%m-%d')
    return daily



def _sync_anomaly_calendar_summary(calendar_df: pd.DataFrame) -> str:
    if calendar_df is None or calendar_df.empty:
        return '目前資料不足，暫時無法判讀轄區同步異常。'

    peak = calendar_df.sort_values(['weak_store_count', 'weak_ratio', 'biz_date'], ascending=[False, False, False]).iloc[0]
    strong_peak = calendar_df.sort_values(['strong_store_count', 'biz_date'], ascending=[False, False]).iloc[0]
    sync_days = int((calendar_df['weak_store_count'] >= 3).sum())

    if int(peak['weak_store_count']) <= 1:
        return '近期間多數日期僅零星門市偏弱，尚未看到明顯的多店同步異常。'

    messages = [f"同步偏弱最明顯：{peak['date_label']} 有 {int(peak['weak_store_count'])} 家門市同時低於自身平均 10% 以上"]
    if sync_days >= 2:
        messages.append(f'近 {len(calendar_df)} 天共有 {sync_days} 天出現 3 家以上門市同步偏弱')
    if int(strong_peak['strong_store_count']) >= 2:
        messages.append(f"同步拉升最多：{strong_peak['date_label']} 有 {int(strong_peak['strong_store_count'])} 家門市同步高於自身平均 10% 以上")
    return '觀察重點：' + '；'.join(messages) + '。'

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

def _store_sync_anomaly_calendar_chart(calendar_df: pd.DataFrame) -> go.Figure:
    weekday_order = ['週一', '週二', '週三', '週四', '週五', '週六', '週日']
    week_order = calendar_df['week_label'].drop_duplicates().tolist()
    lookup = {
        (row['weekday_label'], row['week_label']): row
        for _, row in calendar_df.iterrows()
    }

    z_values = []
    text_values = []
    custom_values = []
    alert_x = []
    alert_y = []
    alert_text = []
    for weekday in weekday_order:
        z_row = []
        text_row = []
        custom_row = []
        for week_label in week_order:
            row = lookup.get((weekday, week_label))
            if row is None:
                z_row.append(None)
                text_row.append('')
                custom_row.append(['', 0, 0, 0])
            else:
                weak_count = int(row['weak_store_count'])
                weak_ratio = float(row['weak_ratio']) if pd.notna(row['weak_ratio']) else 0.0
                z_row.append(weak_count)
                text_row.append(f"{pd.to_datetime(row['biz_date']).day}<br>{weak_count}家" if weak_count > 0 else f"{pd.to_datetime(row['biz_date']).day}")
                custom_row.append([
                    row['date_label'],
                    int(row['strong_store_count']),
                    int(row['observed_store_count']),
                    weak_ratio,
                ])
                if weak_count >= 3 or weak_ratio >= 0.30:
                    alert_x.append(week_label)
                    alert_y.append(weekday)
                    alert_text.append('警示')
        z_values.append(z_row)
        text_values.append(text_row)
        custom_values.append(custom_row)

    fig = go.Figure()
    fig.add_trace(go.Heatmap(
        z=z_values,
        x=week_order,
        y=weekday_order,
        text=text_values,
        texttemplate='%{text}',
        textfont=dict(size=11, color='#0f172a'),
        customdata=custom_values,
        hovertemplate='日期：%{customdata[0]}<br>同步偏弱：%{z} 家<br>同步拉升：%{customdata[1]} 家<br>納入門市：%{customdata[2]} 家<br>偏弱占比：%{customdata[3]:.0%}<extra></extra>',
        colorscale=[[0.0, '#fff7ed'], [0.3, '#fdba74'], [0.6, '#fb923c'], [1.0, '#dc2626']],
        zmin=0,
        zmax=max(3, int(calendar_df['weak_store_count'].max())),
        xgap=8,
        ygap=8,
        hoverongaps=False,
        colorbar=dict(title='同步偏弱門市數'),
    ))
    if alert_x:
        fig.add_trace(go.Scatter(
            x=alert_x,
            y=alert_y,
            mode='markers+text',
            text=alert_text,
            textposition='top center',
            marker=dict(symbol='diamond', size=14, color='#7f1d1d', line=dict(color='#ffffff', width=1.2)),
            hoverinfo='skip',
            showlegend=False,
        ))
    fig.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(family="'Segoe UI', 'Microsoft JhengHei', sans-serif", size=12, color='#14213d'),
        height=400,
        annotations=[
            dict(
                x=1,
                y=1.16,
                xref='paper',
                yref='paper',
                xanchor='right',
                showarrow=False,
                text='警示門檻：同步偏弱 3 家以上，或偏弱占比達 30%',
                font=dict(size=12, color='#7f1d1d'),
                bgcolor='#fee2e2',
                bordercolor='#fecaca',
                borderwidth=1,
                borderpad=6,
            )
        ],
    )
    fig.update_xaxes(title='週次', side='top', showgrid=False, tickangle=0)
    fig.update_yaxes(title='', showgrid=False, autorange='reversed')
    return fig



def _sync_alert_badge_text(calendar_df: pd.DataFrame) -> str:
    if calendar_df is None or calendar_df.empty:
        return '目前沒有可判讀的同步異常警示。'

    alert_days = calendar_df[(calendar_df['weak_store_count'] >= 3) | (calendar_df['weak_ratio'] >= 0.30)].copy()
    if alert_days.empty:
        return '近期間尚未出現明顯的多店同步警示日。'

    latest_alert = alert_days.sort_values('biz_date').iloc[-1]
    return f"最近警示日：{latest_alert['date_label']}，共有 {int(latest_alert['weak_store_count'])} 家門市同步偏弱，占當日納入門市 {latest_alert['weak_ratio']:.0%}。"



def _structure_mix_summary(structure_df: pd.DataFrame) -> str:
    if structure_df is None or structure_df.empty:
        return '目前資料不足，暫時無法判讀異常門市的結構變化。'

    ordered_dates = sorted(structure_df['biz_date'].astype(str).unique())
    latest_date = ordered_dates[-1]
    first_date = ordered_dates[0]
    latest = structure_df[structure_df['biz_date'].astype(str) == latest_date].sort_values('share_rate', ascending=False)
    first = structure_df[structure_df['biz_date'].astype(str) == first_date][['mix_value', 'share_rate']].rename(columns={'share_rate': 'start_share'})
    compare = latest.merge(first, on='mix_value', how='left')
    compare['share_change'] = compare['share_rate'] - compare['start_share'].fillna(0)
    top_mix = latest.iloc[0]
    mover = compare.reindex(compare['share_change'].abs().sort_values(ascending=False).index).iloc[0]
    return f"觀察重點：最新一天以 {top_mix['mix_value']} 占比最高，約 {top_mix['share_rate']:.0%}；近 {len(ordered_dates)} 天變化最大的是 {mover['mix_value']}，占比較起點 {mover['share_change']:+.0%}。"



def _store_structure_change_chart(structure_df: pd.DataFrame) -> go.Figure:
    working = structure_df.copy().sort_values(['biz_date', 'net_sales_value'], ascending=[True, False])
    ordered_dates = working['biz_date'].astype(str).drop_duplicates().tolist()
    mix_order = (
        working.groupby('mix_value')['net_sales_value']
        .sum()
        .sort_values(ascending=False)
        .index.tolist()
    )
    color_map = {
        '內用': '#2563eb',
        '外帶': '#f97316',
        '外送': '#10b981',
        '其他': '#94a3b8',
    }

    fig = go.Figure()
    for mix_value in mix_order:
        subset = working[working['mix_value'] == mix_value].copy()
        subset['biz_date'] = subset['biz_date'].astype(str)
        fig.add_scatter(
            x=subset['biz_date'],
            y=subset['share_rate'],
            mode='lines',
            stackgroup='one',
            name=mix_value,
            line=dict(width=0.8, color=color_map.get(mix_value, '#64748b')),
            hovertemplate='日期：%{x}<br>型態：' + mix_value + '<br>未稅營收占比：%{y:.0%}<br>未稅營收：%{customdata[0]:,.0f}<br>交易筆數：%{customdata[1]:,.0f}<extra></extra>',
            customdata=subset[['net_sales_value', 'txn_count']].to_numpy(),
        )
    fig.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(family="'Segoe UI', 'Microsoft JhengHei', sans-serif", size=12, color='#14213d'),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        height=420,
    )
    fig.update_xaxes(title='日期', showgrid=False, tickangle=-35, categoryorder='array', categoryarray=ordered_dates)
    fig.update_yaxes(title='未稅營收占比', tickformat='.0%', showgrid=True, gridcolor='#e2e8f0', zeroline=False)
    return fig
def _store_contribution_chart(df: pd.DataFrame) -> go.Figure:
    working = df.copy().sort_values('net_sales_change', ascending=True)
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
        hovertemplate='門市：%{y}<br>貢獻差額：%{x:+,.0f}<br>昨日未稅營收：%{customdata[0]:,.0f}<br>上週同日：%{customdata[1]:,.0f}<extra></extra>',
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
        title=dict(text='近 30 天轄區未稅營收 vs 交易筆數', font=dict(size=18, color='#14213d'), x=0.02, xanchor='left'),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        yaxis=dict(title='', showgrid=True, gridcolor='#dbeafe', zeroline=False, tickformat=',.0f'),
        yaxis2=dict(title='', overlaying='y', side='right', showgrid=False, zeroline=False, tickformat=',.0f'),
        xaxis=dict(title='', showgrid=False),
        bargap=0.25,
    )
    fig.update_xaxes(tickangle=-35, automargin=True)
    return fig



def _store_risk_matrix_chart(df: pd.DataFrame) -> go.Figure:
    working = df.copy()
    working['risk_zone'] = working.apply(
        lambda row: '高風險' if pd.notna(row['wow_growth']) and pd.notna(row['deviation_rate']) and row['wow_growth'] < 0 and row['deviation_rate'] < 0
        else '短期下滑' if pd.notna(row['wow_growth']) and row['wow_growth'] < 0
        else '低於常態' if pd.notna(row['deviation_rate']) and row['deviation_rate'] < 0
        else '相對穩定',
        axis=1,
    )
    colors = {
        '高風險': '#ef4444',
        '短期下滑': '#f97316',
        '低於常態': '#eab308',
        '相對穩定': '#22c55e',
    }

    fig = go.Figure()
    for zone, subset in working.groupby('risk_zone'):
        fig.add_scatter(
            x=subset['wow_growth'],
            y=subset['deviation_rate'],
            mode='markers+text',
            name=zone,
            text=subset['label'],
            textposition='top center',
            marker=dict(
                size=subset['current_net_sales'].fillna(0).clip(lower=1).pow(0.5) / 6 + 12,
                color=colors.get(zone, '#64748b'),
                line=dict(color='#ffffff', width=1.2),
                opacity=0.82,
            ),
            customdata=subset[['current_net_sales', 'prior_net_sales', 'avg_net_sales_21']].to_numpy(),
            hovertemplate='門市：%{text}<br>較上週同日：%{x:+.1%}<br>較近21天平均：%{y:+.1%}<br>昨日未稅營收：%{customdata[0]:,.0f}<br>上週同日：%{customdata[1]:,.0f}<br>近21天平均：%{customdata[2]:,.0f}<extra></extra>',
        )
    fig.add_hline(y=0, line=dict(color='#94a3b8', width=1.2, dash='dash'))
    fig.add_vline(x=0, line=dict(color='#94a3b8', width=1.2, dash='dash'))
    fig.add_annotation(x=0.02, y=0.98, xref='paper', yref='paper', text='高於常態 / 低於上週', showarrow=False, font=dict(size=12, color='#166534'))
    fig.add_annotation(x=0.98, y=0.98, xref='paper', yref='paper', text='高於常態 / 高於上週', showarrow=False, xanchor='right', font=dict(size=12, color='#1d4ed8'))
    fig.add_annotation(x=0.02, y=0.02, xref='paper', yref='paper', text='低於常態 / 低於上週', showarrow=False, yanchor='bottom', font=dict(size=12, color='#92400e'))
    fig.add_annotation(x=0.98, y=0.02, xref='paper', yref='paper', text='低於常態 / 高於上週', showarrow=False, xanchor='right', yanchor='bottom', font=dict(size=12, color='#b91c1c'))
    fig.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(family="'Segoe UI', 'Microsoft JhengHei', sans-serif", size=12, color='#14213d'),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        height=560,
    )
    fig.update_xaxes(title='較上週同日增減率', tickformat='.0%', showgrid=True, gridcolor='#e2e8f0', zeroline=False)
    fig.update_yaxes(title='較近 21 天平均差異', tickformat='.0%', showgrid=True, gridcolor='#e2e8f0', zeroline=False)
    return fig
def _store_customer_ticket_quadrant_chart(df: pd.DataFrame) -> go.Figure:
    working = df.copy()
    working['quadrant'] = working.apply(
        lambda row: '來客與客單同步成長' if pd.notna(row['txn_change_rate']) and pd.notna(row['ticket_change_rate']) and row['txn_change_rate'] >= 0 and row['ticket_change_rate'] >= 0
        else '來客成長、客單轉弱' if pd.notna(row['txn_change_rate']) and pd.notna(row['ticket_change_rate']) and row['txn_change_rate'] >= 0 and row['ticket_change_rate'] < 0
        else '來客轉弱、客單成長' if pd.notna(row['txn_change_rate']) and pd.notna(row['ticket_change_rate']) and row['txn_change_rate'] < 0 and row['ticket_change_rate'] >= 0
        else '來客與客單同步轉弱',
        axis=1,
    )
    colors = {
        '來客與客單同步成長': '#22c55e',
        '來客成長、客單轉弱': '#2563eb',
        '來客轉弱、客單成長': '#f59e0b',
        '來客與客單同步轉弱': '#ef4444',
    }

    fig = go.Figure()
    for quadrant_name, subset in working.groupby('quadrant'):
        fig.add_scatter(
            x=subset['txn_change_rate'],
            y=subset['ticket_change_rate'],
            mode='markers+text',
            name=quadrant_name,
            text=subset['label'],
            textposition='top center',
            marker=dict(
                size=subset['current_net_sales'].fillna(0).clip(lower=1).pow(0.5) / 6 + 12,
                color=colors.get(quadrant_name, '#64748b'),
                line=dict(color='#ffffff', width=1.2),
                opacity=0.82,
            ),
            customdata=subset[['current_net_sales', 'current_txn', 'prior_txn', 'current_avg_ticket', 'prior_avg_ticket']].to_numpy(),
            hovertemplate='門市：%{text}<br>來客數變化：%{x:+.1%}<br>客單價變化：%{y:+.1%}<br>昨日未稅營收：%{customdata[0]:,.0f}<br>昨日交易筆數：%{customdata[1]:,.0f}<br>上週同日交易筆數：%{customdata[2]:,.0f}<br>昨日客單價：%{customdata[3]:,.1f}<br>上週同日客單價：%{customdata[4]:,.1f}<extra></extra>',
        )
    fig.add_hline(y=0, line=dict(color='#94a3b8', width=1.2, dash='dash'))
    fig.add_vline(x=0, line=dict(color='#94a3b8', width=1.2, dash='dash'))
    fig.add_annotation(x=0.02, y=0.98, xref='paper', yref='paper', text='來客轉弱 / 客單成長', showarrow=False, font=dict(size=12, color='#166534'))
    fig.add_annotation(x=0.98, y=0.98, xref='paper', yref='paper', text='來客成長 / 客單成長', showarrow=False, xanchor='right', font=dict(size=12, color='#92400e'))
    fig.add_annotation(x=0.02, y=0.02, xref='paper', yref='paper', text='來客轉弱 / 客單轉弱', showarrow=False, yanchor='bottom', font=dict(size=12, color='#1d4ed8'))
    fig.add_annotation(x=0.98, y=0.02, xref='paper', yref='paper', text='來客成長 / 客單轉弱', showarrow=False, xanchor='right', yanchor='bottom', font=dict(size=12, color='#b91c1c'))
    fig.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(family="'Segoe UI', 'Microsoft JhengHei', sans-serif", size=12, color='#14213d'),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        height=560,
    )
    fig.update_xaxes(title='來客數變化 vs 上週同日', tickformat='.0%', showgrid=True, gridcolor='#e2e8f0', zeroline=False)
    fig.update_yaxes(title='客單價變化 vs 上週同日', tickformat='.0%', showgrid=True, gridcolor='#e2e8f0', zeroline=False)
    return fig
def _store_anomaly_streak_chart(df: pd.DataFrame) -> go.Figure:
    working = df.copy().sort_values(['weak_streak', 'weak_days_7', 'current_net_sales'], ascending=[True, True, True])
    colors = ['#ef4444' if value >= 3 else '#f97316' if value >= 2 else '#facc15' for value in working['weak_streak']]
    fig = go.Figure()
    fig.add_bar(
        x=working['weak_streak'],
        y=working['label'],
        orientation='h',
        marker=dict(color=colors, line=dict(color='#ffffff', width=1.2)),
        text=working.apply(lambda row: f"連續 {int(row['weak_streak'])} 天 / 近7天 {int(row['weak_days_7'])} 天", axis=1),
        textposition='outside',
        cliponaxis=False,
        customdata=working[['latest_deviation', 'current_net_sales']].to_numpy(),
        hovertemplate='門市：%{y}<br>連續偏弱：%{x} 天<br>近7天偏弱：%{text}<br>昨日相對平均：%{customdata[0]:+.1%}<br>昨日未稅營收：%{customdata[1]:,.0f}<extra></extra>',
    )
    fig.update_layout(
        margin=dict(l=20, r=60, t=20, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white',
        showlegend=False,
        font=dict(family="'Segoe UI', 'Microsoft JhengHei', sans-serif", size=12, color='#14213d'),
        height=max(320, 42 * len(working) + 120),
    )
    fig.update_xaxes(title='連續偏弱天數', showgrid=True, gridcolor='#e2e8f0', zeroline=False, tickformat=',.0f')
    fig.update_yaxes(showgrid=False, automargin=True)
    return fig

def _build_streak_ranking_df(heatmap_df: pd.DataFrame, limit: int = 8) -> pd.DataFrame:
    if heatmap_df is None or heatmap_df.empty:
        return pd.DataFrame(columns=['label', 'weak_streak', 'weak_days_7', 'latest_deviation', 'current_net_sales'])

    working = heatmap_df.copy()
    working['biz_date'] = pd.to_datetime(working['biz_date'])
    latest_date = working['biz_date'].max()
    recent_7_start = latest_date - pd.Timedelta(days=6)
    recent_7 = working[working['biz_date'] >= recent_7_start].copy()

    latest = (
        working[working['biz_date'] == latest_date][['label', 'deviation_rate', 'net_sales_value']]
        .rename(columns={'deviation_rate': 'latest_deviation', 'net_sales_value': 'current_net_sales'})
    )
    weak_days_7 = recent_7.groupby('label')['deviation_rate'].apply(lambda s: int((s <= -0.10).sum())).rename('weak_days_7')
    weak_streak = (
        recent_7.sort_values(['label', 'biz_date'])
        .groupby('label')['deviation_rate']
        .apply(lambda s: int((s.iloc[::-1] <= -0.10).cumprod().sum()))
        .rename('weak_streak')
    )

    summary = latest.merge(weak_days_7, on='label', how='left').merge(weak_streak, on='label', how='left')
    summary[['weak_days_7', 'weak_streak']] = summary[['weak_days_7', 'weak_streak']].fillna(0)
    summary = summary[(summary['weak_streak'] > 0) | (summary['weak_days_7'] > 0)].copy()
    summary = summary.sort_values(['weak_streak', 'weak_days_7', 'latest_deviation', 'current_net_sales'], ascending=[False, False, True, False]).head(limit)
    return summary
def _build_priority_suggestion(row: pd.Series) -> str:
    latest_deviation = row.get('latest_deviation')
    wow_growth = row.get('wow_growth')
    weak_streak = row.get('weak_streak', 0)
    if pd.notna(latest_deviation) and latest_deviation <= -0.15 and weak_streak >= 2:
        return '先確認店內來客、排班與商圈狀況，必要時今天就追蹤店長。'
    if pd.notna(wow_growth) and wow_growth <= -0.15:
        return '先比對上週同日活動、天氣與競品狀況，判斷是否為短期下滑。'
    return '列入今日追蹤名單，先看交易筆數與現場營運是否同步轉弱。'


def _build_priority_store_list(heatmap_df: pd.DataFrame, growth_df: pd.DataFrame, limit: int = PRIORITY_LIMIT) -> pd.DataFrame:
    if heatmap_df is None or heatmap_df.empty:
        return pd.DataFrame(columns=['label', 'priority_score'])

    working = heatmap_df.copy()
    working['biz_date'] = pd.to_datetime(working['biz_date'])
    latest_date = working['biz_date'].max()
    latest = working[working['biz_date'] == latest_date][['label', 'net_sales_value', 'avg_net_sales', 'deviation_rate']].copy()
    latest = latest.rename(columns={'net_sales_value': 'latest_net_sales', 'deviation_rate': 'latest_deviation'})

    recent_7_start = latest_date - pd.Timedelta(days=6)
    recent_7 = working[working['biz_date'] >= recent_7_start].copy()
    weak_7 = recent_7.groupby('label')['deviation_rate'].apply(lambda s: int((s <= -0.10).sum())).rename('weak_days_7')
    strong_7 = recent_7.groupby('label')['deviation_rate'].apply(lambda s: int((s >= 0.10).sum())).rename('strong_days_7')
    latest_streak = recent_7.sort_values(['label', 'biz_date']).groupby('label')['deviation_rate'].apply(
        lambda s: int((s.iloc[::-1] <= -0.10).cumprod().sum())
    ).rename('weak_streak')

    summary = latest.merge(weak_7, on='label', how='left').merge(strong_7, on='label', how='left').merge(latest_streak, on='label', how='left')
    summary[['weak_days_7', 'strong_days_7', 'weak_streak']] = summary[['weak_days_7', 'strong_days_7', 'weak_streak']].fillna(0)

    growth = growth_df.copy()
    if not growth.empty:
        growth = growth.rename(columns={'growth_rate': 'wow_growth'})[['label', 'current_net_sales', 'prior_net_sales', 'wow_growth']]
        summary = summary.merge(growth, on='label', how='left')
    else:
        summary['current_net_sales'] = pd.NA
        summary['prior_net_sales'] = pd.NA
        summary['wow_growth'] = pd.NA

    summary['priority_score'] = (
        summary['latest_deviation'].fillna(0).clip(upper=0).abs() * 100
        + summary['weak_days_7'] * 8
        + summary['weak_streak'] * 12
        + summary['wow_growth'].fillna(0).clip(upper=0).abs() * 60
    )
    summary['priority_level'] = summary['priority_score'].apply(
        lambda v: '立即處理' if v >= 35 else '優先追蹤' if v >= 20 else '持續觀察'
    )
    summary['suggestion'] = summary.apply(_build_priority_suggestion, axis=1)
    summary = summary.sort_values(['priority_score', 'latest_deviation'], ascending=[False, True]).head(limit)
    return summary


def _priority_reason_text(row: pd.Series) -> str:
    reasons = []
    latest_deviation = row.get('latest_deviation')
    wow_growth = row.get('wow_growth')
    weak_streak = row.get('weak_streak', 0)
    weak_days_7 = row.get('weak_days_7', 0)
    if pd.notna(latest_deviation) and latest_deviation <= -0.15:
        reasons.append('昨天表現明顯低於該店平常水位')
    if weak_streak >= 2:
        reasons.append(f'已連續 {int(weak_streak)} 天轉弱')
    if pd.notna(wow_growth) and wow_growth <= -0.15:
        reasons.append('與上週同日相比也在明顯下滑')
    if not reasons and weak_days_7 >= 2:
        reasons.append('近 7 天已多次出現偏弱訊號')
    if not reasons:
        return '目前屬於早期預警，建議先列入追蹤。'
    return '；'.join(reasons) + '。'


def _reason_diagnosis_text(priority_df: pd.DataFrame, trend_df: pd.DataFrame) -> str:
    if priority_df.empty:
        return '目前資料不足，暫時無法判讀異常原因。'

    weak_stores = int((priority_df['weak_streak'] >= 2).sum())
    deep_drop_stores = int((priority_df['latest_deviation'] <= -0.15).sum())
    wow_drops = int((priority_df['wow_growth'].fillna(0) <= -0.10).sum())
    trend_text = ''
    if trend_df is not None and not trend_df.empty and len(trend_df) >= 14:
        ordered = trend_df.sort_values('biz_date').tail(14).copy()
        recent_7_sales = ordered.tail(7)['net_sales_value'].mean()
        prior_7_sales = ordered.head(7)['net_sales_value'].mean()
        recent_7_txn = ordered.tail(7)['txn_count'].mean()
        prior_7_txn = ordered.head(7)['txn_count'].mean()
        sales_drop = pd.notna(prior_7_sales) and prior_7_sales not in (0, None) and recent_7_sales < prior_7_sales * 0.97
        txn_drop = pd.notna(prior_7_txn) and prior_7_txn not in (0, None) and recent_7_txn < prior_7_txn * 0.97
        if sales_drop and txn_drop:
            trend_text = '整體看起來比較像來客下滑，不只是一兩家店的客單問題。'
        elif sales_drop and not txn_drop:
            trend_text = '整體未稅營收轉弱，但交易筆數沒有同步下滑，較像客單價轉弱。'
        elif txn_drop and not sales_drop:
            trend_text = '交易筆數轉弱比未稅營收更明顯，建議優先確認來客與活動帶動。'

    if weak_stores >= 2:
        base_text = f'目前有 {weak_stores} 家優先門市已連續轉弱，代表今天不是單一偶發事件，區主管需要優先確認是否有區域共通因素。'
    elif deep_drop_stores >= 2:
        base_text = f'目前有 {deep_drop_stores} 家優先門市明顯低於各自正常水位，建議先確認商圈、天氣或活動是否同步影響。'
    elif wow_drops >= 2:
        base_text = '多家門市相較上週同日一起下滑，較像短期事件造成，不一定是單店營運失常。'
    else:
        top_store = priority_df.iloc[0]['label']
        base_text = f'目前異常較集中在 {top_store} 等少數門市，優先逐店確認現場營運、人力與商圈變化會比較有效。'

    return f'{base_text} {trend_text}'.strip()


def _priority_card_tone(row: pd.Series) -> str:
    if row['priority_level'] == '立即處理':
        return 'critical'
    if row['priority_level'] == '優先追蹤':
        return 'warning'
    return 'stable'


def _priority_kpis(priority_df: pd.DataFrame, contribution_df: pd.DataFrame, comparison: dict) -> list[tuple[str, str, str, str]]:
    watch_count = len(priority_df)
    streak_count = int((priority_df['weak_streak'] >= 2).sum()) if not priority_df.empty else 0
    latest_drag = '-'
    latest_lift = '-'
    if contribution_df is not None and not contribution_df.empty:
        drag = contribution_df.sort_values('net_sales_change').head(1)
        lift = contribution_df.sort_values('net_sales_change', ascending=False).head(1)
        if not drag.empty:
            latest_drag = drag.iloc[0]['label']
        if not lift.empty:
            latest_lift = lift.iloc[0]['label']
    spread_text = '有擴散跡象' if streak_count >= 2 else '目前集中少數門市'
    return [
        ('今日待關注門市', f'{watch_count}', '依異常分數排序', 'neutral'),
        ('連續轉弱門市', f'{streak_count}', '連續 2 天以上偏弱', 'neutral'),
        ('最大拖累門市', latest_drag, '昨日 vs 上週同日', 'negative'),
        ('最大拉升門市', latest_lift, '昨日 vs 上週同日', 'positive'),
        ('轄區昨日 vs 上週同日', '-' if comparison.get('wow') is None else f"{comparison.get('wow'):+.1%}", change_text(comparison.get('wow'), '上週同日'), change_tone(comparison.get('wow'))),
        ('異常擴散狀態', spread_text, '看是否同日多店轉弱', 'negative' if streak_count >= 2 else 'neutral'),
    ]


def _render_priority_cards(priority_df: pd.DataFrame):
    if priority_df.empty:
        st.info('目前資料不足，暫時無法產出今日優先處理門市。')
        return

    cols = st.columns(len(priority_df))
    for col, (_, row) in zip(cols, priority_df.iterrows()):
        with col:
            safe_label = escape(str(row['label']))
            safe_level = escape(str(row['priority_level']))
            safe_reason = escape(_priority_reason_text(row))
            safe_action = escape(str(row['suggestion']))
            wow_text = '-' if pd.isna(row['wow_growth']) else f"{row['wow_growth']:+.1%}"
            card_html = f"""
            <div class="supervisor-priority-card {_priority_card_tone(row)}">
                <div class="supervisor-priority-badge">{safe_level}</div>
                <div class="supervisor-priority-title">{safe_label}</div>
                <div class="supervisor-priority-score">異常分數 {row['priority_score']:.1f}</div>
                <div class="supervisor-priority-grid">
                    <div class="supervisor-priority-metric">
                        <div class="supervisor-priority-label">昨日 vs 近21天平均</div>
                        <div class="supervisor-priority-value">{row['latest_deviation']:+.1%}</div>
                    </div>
                    <div class="supervisor-priority-metric">
                        <div class="supervisor-priority-label">昨日 vs 上週同日</div>
                        <div class="supervisor-priority-value">{wow_text}</div>
                    </div>
                    <div class="supervisor-priority-metric">
                        <div class="supervisor-priority-label">近7天偏弱天數</div>
                        <div class="supervisor-priority-value">{int(row['weak_days_7'])} 天</div>
                    </div>
                    <div class="supervisor-priority-metric">
                        <div class="supervisor-priority-label">連續轉弱</div>
                        <div class="supervisor-priority-value">{int(row['weak_streak'])} 天</div>
                    </div>
                </div>
                <div class="supervisor-priority-reason">判讀：{safe_reason}</div>
                <div class="supervisor-priority-action"><strong>建議先做：</strong>{safe_action}</div>
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)



apply_page_style()
_apply_supervisor_page_style()
filters = render_sidebar_filters(page_key='supervisor')

st.title('區域現況分析版')
st.caption('聚焦轄區內各門市的營運強弱、異常擴散與優先處理對象，協助快速判斷管理重點。')

metrics = get_overview_metrics_for_filters(filters)
comparison = get_period_comparison(filters)
trend = get_daily_trend(filters=filters, limit=30)
growth_best = get_store_growth_rankings(filters=filters, limit=10, worst=False).sort_values('growth_rate', ascending=False, na_position='last')
growth_worst = get_store_growth_rankings(filters=filters, limit=10, worst=True).sort_values('growth_rate', ascending=True, na_position='last')
recent_table = get_recent_daily_table(filters=filters, limit=30).sort_values('biz_date', ascending=False)
heatmap_df = get_store_anomaly_heatmap(filters=filters, days=HEATMAP_DAYS, store_limit=HEATMAP_STORE_LIMIT)
contribution_df = get_store_contribution_rankings(filters=filters, limit=5)
quadrant_df = get_store_customer_ticket_quadrant(filters=filters, limit=20)
risk_df = get_store_risk_matrix(filters=filters)
sync_calendar_df = _build_sync_anomaly_calendar_df(heatmap_df)
streak_df = _build_streak_ranking_df(heatmap_df, limit=8)
priority_df = _build_priority_store_list(heatmap_df, growth_worst, limit=PRIORITY_LIMIT)

# 準備匯出/顯示用的數據框
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

recent_export = recent_table.copy() if not recent_table.empty else pd.DataFrame()
if not recent_export.empty:
    recent_export = recent_export.rename(columns={
        'net_sales_value': '未稅營收',
        'txn_count': '交易筆數',
        'sales_qty': '銷量',
        'avg_ticket': '筆單價'
    })
structure_store_options = []
if not priority_df.empty:
    structure_store_options.extend(priority_df['label'].tolist())
if not growth_worst.empty:
    structure_store_options.extend(growth_worst['label'].tolist())
structure_store_options = list(dict.fromkeys([label for label in structure_store_options if pd.notna(label)]))
default_structure_store = structure_store_options[0] if structure_store_options else None
selected_structure_store = st.session_state.get('supervisor_structure_store', default_structure_store)
if selected_structure_store not in structure_store_options:
    selected_structure_store = default_structure_store
if selected_structure_store is not None:
    st.session_state['supervisor_structure_store'] = selected_structure_store
structure_df = get_store_mix_structure_trend(filters=filters, days=14) if selected_structure_store else pd.DataFrame()
reason_summary = _reason_diagnosis_text(priority_df, trend)


content_gap('sm')
section_title('今日優先處理門市')
st.caption('這一排是給區主管的第一眼答案。系統會綜合昨天是否低於自身平均、近 7 天偏弱次數、是否連續轉弱，以及較上週同日的衰退幅度，排出今天最該先處理的門市。')
st.caption('異常分數計算方式：1. 昨日低於近 21 天平均的幅度越大，分數越高。2. 近 7 天偏弱天數越多，分數越高。3. 連續轉弱天數越長，分數越高。4. 若昨日比上週同日再明顯下滑，會再加重分數。分數越高，不代表一定最差，而是代表今天越應該優先處理。')
status_panel('建議使用方式：先看卡片決定今天先追哪幾家，再看下方的異常原因判讀摘要，最後用熱力圖與拖累圖確認是單店問題還是區域共通問題。')
_render_priority_cards(priority_df)

content_gap('md')
section_title('異常原因判讀摘要')
status_panel(reason_summary)
st.caption('這段摘要會綜合優先門市的連續轉弱狀況，以及轄區近 14 天未稅營收與交易筆數變化，自動給你一個較接近現場管理語言的初步判讀。')

content_gap('sm')
kpis = _priority_kpis(priority_df, contribution_df, comparison)
for start in range(0, len(kpis), 3):
    row_cols = st.columns(3)
    for col, (label, value, subtext, tone) in zip(row_cols, kpis[start:start + 3]):
        with col:
            render_kpi_card(label, value, subtext, tone, variant='compare')
    content_gap('sm')

section_title('門市異常熱力圖')
if heatmap_df.empty:
    st.info('目前查無門市異常熱力圖資料。')
else:
    st.caption(f'顯示範圍：最近 {HEATMAP_DAYS} 天、累計未稅營收前 {HEATMAP_STORE_LIMIT} 家門市，並依這段期間累積未稅營收由高到低排序，讓你先看影響最大的門市。')
    status_panel(_heatmap_summary(heatmap_df))
    st.caption('閱讀方式：橫軸是日期、縱軸是門市。綠色越深代表表現高於該店近 21 天平均，紅色越深代表低於平均。')
    st.caption('先橫向看單店是否連續轉紅，再縱向看某一天是否很多店一起轉紅。橫向連紅通常是單店問題，縱向多店轉紅則較可能是天氣、商圈或活動影響。')
    st.caption('滑鼠移到格子上可看到當日未稅營收、近 21 天平均與差異幅度，方便快速確認問題深度。')
    st.plotly_chart(_store_heatmap_chart(heatmap_df), use_container_width=True, key='supervisor-heatmap-chart')

section_title('轄區同步異常日曆圖')
if sync_calendar_df.empty:
    st.info('目前查無轄區同步異常日曆圖資料。')
else:
    st.caption('這張圖看的是「哪一天很多門市一起轉弱」，不是看單一門市掉多少。顏色越深，代表當天同步偏弱的門市越多。')
    status_panel(_sync_anomaly_calendar_summary(sync_calendar_df))
    status_panel(_sync_alert_badge_text(sync_calendar_df))
    st.caption('閱讀方式：先找顏色最深、且有「警示」標記的日期，代表那天較像區域性事件；如果只是零星幾天或只有 1 家店偏弱，通常較像單店問題。')
    st.caption('每格上方的數字是日期、下方是同步偏弱門市數。建議搭配上方門市異常熱力圖一起看：日曆圖先看哪幾天出事，熱力圖再看是哪些店一起出事。')
    st.caption('滑鼠移到格子上，可看當天同步偏弱家數、同步拉升家數、納入門市數與偏弱占比，方便判斷異常是否有擴散。')
    st.plotly_chart(_store_sync_anomaly_calendar_chart(sync_calendar_df), use_container_width=True, key='supervisor-sync-anomaly-calendar')

section_title('異常門市結構變化圖')
if not structure_store_options:
    st.info('目前查無可切換的異常門市結構變化資料。')
elif structure_df.empty:
    st.info('目前查無異常門市結構變化資料。')
else:
    selector_cols = st.columns([1.2, 2.8])
    with selector_cols[0]:
        st.selectbox(
            '切換門市',
            structure_store_options,
            index=structure_store_options.index(selected_structure_store) if selected_structure_store in structure_store_options else 0,
            key='supervisor_structure_store',
            help='預設先看異常分數較高的門市，也可切換到其他待追蹤門市。',
        )
    with selector_cols[1]:
        st.caption('可在優先處理門市與需要立即追蹤門市之間切換，查看不同門市近 14 天的交易型態占比變化。')
    focus_label = structure_df['store_label'].iloc[0]
    st.caption(f'目前聚焦門市：{focus_label}。這張圖用來看這家店的交易型態是否正在改變，不是只看總未稅營收高低。')
    status_panel(_structure_mix_summary(structure_df))
    st.caption('閱讀方式：先看最新一天哪個型態占比最高，再看近 14 天哪一塊面積變化最大。若外送占比上升、內用占比下降，通常表示來客結構或商圈需求有明顯改變。')
    st.caption('建議先切換比較異常分數前幾名的門市，看看它們是不是出現同樣的結構偏移；若很多家都往同一方向變，較可能是區域共通現象。')
    st.caption('滑鼠移到區塊上，可看當日該型態的未稅營收占比、未稅營收與交易筆數。這張圖適合搭配來客數 vs 客單價四象限圖一起看，確認是結構轉變還是單純來客下滑。')
    st.plotly_chart(_store_structure_change_chart(structure_df), use_container_width=True, key='supervisor-structure-change-chart')

section_title('門市異常持續天數排行')
if streak_df.empty:
    st.info('目前查無門市異常持續天數資料。')
else:
    st.caption('這張圖專門看「異常持續多久」，不是看一天掉多少。橫條越長，代表該店已連續更多天低於自己的正常水位。')
    st.caption('閱讀方式：先看最上方幾家店，這些是最不像單日失常、最值得區主管主動追的門市。若連續偏弱天數高，而且近 7 天偏弱次數也高，代表問題較可能已持續一段時間。')
    st.caption('建議搭配上方熱力圖一起看：熱力圖看異常分布，這張排行看異常拖多久。滑鼠移到長條上，可看昨日相對平均差異與昨日未稅營收。')
    st.plotly_chart(_store_anomaly_streak_chart(streak_df), use_container_width=True, key='supervisor-streak-ranking-chart')
section_title('誰在拖累，誰在拉升')
if contribution_df.empty:
    st.info('目前查無拖累 / 拉升門市資料。')
else:
    latest_date = contribution_df['latest_date'].iloc[0]
    prior_date = contribution_df['prior_date'].iloc[0]
    st.caption(f'比較基準：{latest_date} vs {prior_date}。這張圖不是看增減率，而是看每家門市對整體轄區未稅營收的影響金額。')
    st.caption('先看左側紅色長條，知道今天誰在拖累轄區；再看右側綠色長條，知道哪些門市正在撐住整體表現。')
    st.plotly_chart(_store_contribution_chart(contribution_df), use_container_width=True, key='supervisor-contribution-chart')

section_title('轄區未稅營收 vs 交易筆數')
if trend.empty:
    st.info('目前查無轄區未稅營收與交易筆數資料。')
else:
    st.caption('藍色柱體看每日未稅營收，橘色折線看交易筆數。若兩者一起下滑，通常是來客減少；若交易筆數持平但未稅營收下滑，則較可能是客單價轉弱。')
    st.plotly_chart(_sales_txn_dual_axis_chart(trend), use_container_width=True, key='supervisor-sales-txn-chart')


section_title('門市風險矩陣圖')
if risk_df.empty:
    st.info('目前查無門市風險矩陣資料。')
else:
    latest_date = risk_df['latest_date'].iloc[0]
    prior_date = risk_df['prior_date'].iloc[0]
    st.caption(f'比較基準：{latest_date} vs {prior_date}。每個點代表 1 家門市；點越大，代表該店昨日未稅營收越高，也就是對轄區影響越大。')
    st.caption('閱讀方式：橫軸看較上週同日的變化，越往左表示短期下滑越明顯；縱軸看較近 21 天平均的差異，越往下表示目前表現越低於常態。')
    st.caption('最值得先追的通常在左下角，代表「短期也在掉、平常水位也守不住」。如果點又大，表示不只異常，對轄區影響也更大。')
    st.caption('建議先看左下角且點大的門市，再看是集中在少數幾家，還是整個區域很多店一起往左下移動。滑鼠移到點上，可看昨日未稅營收、上週同日與近 21 天平均。')
    st.plotly_chart(_store_risk_matrix_chart(risk_df), use_container_width=True, key='supervisor-risk-matrix-chart')

section_title('來客數 vs 客單價四象限圖')
if quadrant_df.empty:
    st.info('目前查無來客數與客單價四象限資料。')
else:
    latest_date = quadrant_df['latest_date'].iloc[0]
    prior_date = quadrant_df['prior_date'].iloc[0]
    st.caption(f'比較基準：{latest_date} vs {prior_date}。每個點代表 1 家門市；點越大，代表該店昨日未稅營收越高。')
    st.caption('閱讀方式：右上角代表來客與客單同步成長；左下角代表來客與客單同步轉弱，是最需要優先處理的區域。右下角代表來客掉但客單撐住，較像來客問題；左上角代表來客有成長但客單轉弱，較像商品組合或加購轉弱。')
    st.caption('先找左下角且點又大的門市，通常就是對轄區影響最大、也最值得今天先追的門市。滑鼠移到點上，可看昨日與上週同日的來客數、客單價與未稅營收。')
    st.plotly_chart(_store_customer_ticket_quadrant_chart(quadrant_df), use_container_width=True, key='supervisor-customer-ticket-quadrant')
section_title('需要立即追蹤門市')
st.caption('這裡列的是相較上週同日衰退最明顯的門市，可搭配上方熱力圖交叉判斷，是短期下滑還是已經連續轉弱。')
row_cols = st.columns(2)
with row_cols[0]:
    st.markdown('### 需要立即追蹤')
    if growth_worst_export.empty:
        st.info('目前查無衰退排行資料。')
    else:
        worst = growth_worst_export.copy()
        for col_name in ['昨日未稅營收', '上週同日未稅營收']:
            worst[col_name] = worst[col_name].map(lambda x: '-' if pd.isna(x) else f'{x:,.0f}')
        worst['增減率'] = worst['增減率'].map(lambda x: '-' if pd.isna(x) else f'{x:.1%}')
        st.dataframe(worst, use_container_width=True, hide_index=True)
with row_cols[1]:
    st.markdown('### 近期拉升門市')
    if growth_best_export.empty:
        st.info('目前查無成長排行資料。')
    else:
        best = growth_best_export.copy()
        for col_name in ['昨日未稅營收', '上週同日未稅營收']:
            best[col_name] = best[col_name].map(lambda x: '-' if pd.isna(x) else f'{x:,.0f}')
        best['增減率'] = best['增減率'].map(lambda x: '-' if pd.isna(x) else f'{x:.1%}')
        st.dataframe(best, use_container_width=True, hide_index=True)

section_title('待追蹤門市明細')
st.caption('若要往下交辦或逐店確認，可在這裡看最近 30 天轄區日摘要。這一區是補充資料，不是今天決策的第一眼。')
if recent_export.empty:
    st.info('目前查無近 30 日摘要資料。')
else:
    summary = recent_export.copy()
    for col_name in ['未稅營收', '交易筆數', '銷量']:
        summary[col_name] = summary[col_name].map(lambda x: f'{x:,.0f}')
    summary['筆單價'] = summary['筆單價'].map(lambda x: '-' if pd.isna(x) else f'{x:,.1f}')
    st.dataframe(summary, use_container_width=True, hide_index=True)



