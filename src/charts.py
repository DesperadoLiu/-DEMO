import pandas as pd
import plotly.express as px

FONT_FAMILY = "'Segoe UI', 'Microsoft JhengHei', sans-serif"
PRIMARY = '#2563eb'
SECONDARY = '#f97316'
GRID = '#dbeafe'
TEXT = '#14213d'
PALETTE = ['#2563eb', '#f97316', '#06b6d4', '#22c55e', '#a855f7', '#ef4444', '#f59e0b', '#ec4899']

def _base_layout(fig):
    fig.update_layout(
        margin=dict(l=20, r=20, t=64, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white',
        xaxis_title='',
        yaxis_title='',
        legend_title_text='',
        font=dict(family=FONT_FAMILY, size=13, color=TEXT),
        title=dict(font=dict(size=18, color=TEXT), x=0.02, xanchor='left'),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
    )
    fig.update_xaxes(showgrid=False, tickfont=dict(size=12), automargin=True)
    fig.update_yaxes(showgrid=True, gridcolor=GRID, zeroline=False, tickfont=dict(size=12), automargin=True)
    return fig

def line_chart(df, x_col, y_col, title, color=PRIMARY):
    fig = px.line(df, x=x_col, y=y_col, title=title, markers=True)
    fig.update_traces(
        line={'color': color, 'width': 3},
        marker={'size': 6, 'color': color},
        hovertemplate='日期：%{x}<br>數值：%{y:,.0f}<extra></extra>',
    )
    fig.update_yaxes(tickformat=',.0f')
    return _base_layout(fig)

def bar_chart(df, x_col, y_col, title, color=SECONDARY, orientation='v'):
    fig = px.bar(
        df,
        x=x_col if orientation == 'v' else y_col,
        y=y_col if orientation == 'v' else x_col,
        title=title,
        orientation=orientation,
        color_discrete_sequence=[color],
    )
    fig.update_traces(marker_line_color='#ffffff', marker_line_width=1.2)
    if orientation == 'h':
        fig.update_traces(hovertemplate='項目：%{y}<br>數值：%{x:,.0f}<extra></extra>')
        fig.update_xaxes(tickformat=',.0f')
    else:
        fig.update_traces(hovertemplate='日期：%{x}<br>數值：%{y:,.0f}<extra></extra>')
        fig.update_yaxes(tickformat=',.0f')
    return _base_layout(fig)

def donut_chart(df, names_col, values_col, title):
    plot_df = df.copy()
    total = plot_df[values_col].sum()
    if total and total > 0:
        plot_df['_legend_label'] = plot_df.apply(
            lambda row: f"{row[names_col]} {row[values_col] / total:.1%}", axis=1
        )
    else:
        plot_df['_legend_label'] = plot_df[names_col].astype(str)

    fig = px.pie(
        plot_df,
        names='_legend_label',
        values=values_col,
        hole=0.58,
        title=title,
        color_discrete_sequence=PALETTE,
        custom_data=[names_col],
    )
    fig.update_traces(
        textinfo='none',
        pull=[0.03] + [0] * max(0, len(plot_df) - 1),
        sort=False,
        hovertemplate='類別：%{customdata[0]}<br>未稅營收：%{value:,.0f}<br>占比：%{percent}<extra></extra>',
    )
    fig.update_layout(
        showlegend=True,
        margin=dict(l=20, r=140, t=64, b=20),
        legend=dict(
            orientation='v',
            yanchor='top',
            y=0.98,
            xanchor='left',
            x=1.02,
            font=dict(size=12, color=TEXT),
        ),
    )
    return _base_layout(fig)
