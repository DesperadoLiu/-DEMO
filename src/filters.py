from __future__ import annotations
import streamlit as st
from src.services import get_filter_dimension_options, get_store_filter_options
from src.utils import default_date_range

PAGE_PRESETS = {
    'overview': {'lookback_days': 100, 'label': '預設期間：近 100 天'},
    'supervisor': {'lookback_days': 30, 'label': '預設期間：近 30 天'},
    'product': {'lookback_days': 30, 'label': '預設期間：近 30 天'},
    'marketing': {'lookback_days': 30, 'label': '預設期間：近 30 天'},
}

def _widget_key(page_key: str, field_name: str) -> str:
    return f'{page_key}_{field_name}'

def render_sidebar_filters(page_key: str = 'overview'):
    preset = PAGE_PRESETS.get(page_key, PAGE_PRESETS['overview'])

    st.sidebar.header('篩選條件')
    st.sidebar.caption(preset['label'])

    options = get_store_filter_options()
    dim_options = get_filter_dimension_options()

    start_date, end_date = default_date_range(preset['lookback_days'])
    
    # stlite has some issues with date_input in older versions, but 0.71.0 should be fine.
    date_range = st.sidebar.date_input(
        '統計期間',
        value=(start_date, end_date),
        format='YYYY-MM-DD',
        key=_widget_key(page_key, 'date_range'),
    )

    city_options = sorted(options['city_name'].dropna().unique().tolist()) if not options.empty else []
    division_options = sorted(options['division_name'].dropna().unique().tolist()) if not options.empty else []
    region_options = sorted(options['region_name'].dropna().unique().tolist()) if not options.empty else []
    store_type_options = sorted(options['store_type'].dropna().unique().tolist()) if not options.empty else []

    selected_cities = st.sidebar.multiselect('縣市', city_options, key=_widget_key(page_key, 'cities'))
    selected_divisions = st.sidebar.multiselect('處別', division_options, key=_widget_key(page_key, 'divisions'))
    selected_regions = st.sidebar.multiselect('轄區', region_options, key=_widget_key(page_key, 'regions'))
    selected_store_types = st.sidebar.multiselect('營業型態', store_type_options, key=_widget_key(page_key, 'store_types'))

    filtered = options.copy()
    if selected_cities:
        filtered = filtered[filtered['city_name'].isin(selected_cities)]
    if selected_divisions:
        filtered = filtered[filtered['division_name'].isin(selected_divisions)]
    if selected_regions:
        filtered = filtered[filtered['region_name'].isin(selected_regions)]
    if selected_store_types:
        filtered = filtered[filtered['store_type'].isin(selected_store_types)]

    if filtered.empty:
        store_options = []
    else:
        labels = filtered.assign(store_label=lambda df: df['store_id'] + ' ' + df['store_name'])['store_label'].dropna().tolist()
        store_options = sorted(labels)

    selected_stores = st.sidebar.multiselect('門市', store_options, key=_widget_key(page_key, 'stores'))
    txn_types = st.sidebar.multiselect('交易型態', dim_options.get('txn_type', []), key=_widget_key(page_key, 'txn_types'))
    payment_types = st.sidebar.multiselect('支付方式', dim_options.get('payment_type', []), key=_widget_key(page_key, 'payment_types'))
    item_prefixes = st.sidebar.multiselect('餐點屬性碼', dim_options.get('item_prefix', []), key=_widget_key(page_key, 'item_prefixes'))

    st.sidebar.divider()
    all_item_codes = sorted(dim_options.get('item_code', []))
    excluded_items = st.sidebar.multiselect('🔴 排除商品品號', all_item_codes, key=_widget_key(page_key, 'excluded_items'), help='選取後將此商品的數據從所有圖表中移除')

    return {
        'date_range': date_range,
        'cities': selected_cities,
        'divisions': selected_divisions,
        'regions': selected_regions,
        'store_types': selected_store_types,
        'stores': selected_stores,
        'txn_types': txn_types,
        'payment_types': payment_types,
        'item_prefixes': item_prefixes,
        'excluded_items': excluded_items,
    }
