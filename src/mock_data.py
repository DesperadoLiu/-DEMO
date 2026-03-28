from __future__ import annotations
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# --- 模擬數據生成核心 ---

def generate_base_data(days=120):
    """產生指定天數的原始模擬數據，包含維度：日期、門市、產品線、交易型態、支付方式"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    
    cities = ['台北市', '新北市', '桃園市', '台中市', '台南市', '高雄市']
    divisions = ['北一區', '北二區', '中區', '南區']
    store_types = ['直營店', '加盟店']
    
    stores = []
    for i in range(1, 13): # 縮減門市數量以提升效能
        city = cities[i % len(cities)]
        div = divisions[i % len(divisions)]
        stype = '直營店' if i % 3 == 0 else '加盟店'
        stores.append({
            'store_id': f'{1000 + i}',
            'store_name': f'展示門市 {chr(64+i)}',
            'city_name': city,
            'division_name': div,
            'region_name': f'{city}某區',
            'store_type': stype,
            'latitude': 25.0 + random.uniform(-0.3, 0.3),
            'longitude': 121.5 + random.uniform(-0.3, 0.3)
        })
    df_stores = pd.DataFrame(stores)
    
    item_prefixes = ['魯肉飯系列', '便當系列', '小菜系列', '湯品系列', '嫩豆腐系列']
    txn_types = ['內用', '外帶', '外送平台']
    payment_types = ['現金', '信用卡', 'Line Pay', '街口支付']
    
    data = []
    for date in dates:
        # 趨勢與週期性
        days_passed = (date - start_date).days
        trend = 1.0 + (days_passed / days) * 0.15 
        dow_factor = 1.3 if date.weekday() >= 5 else 1.0
        
        for store in stores:
            # 門市基礎業績
            base_sales = random.uniform(30000, 60000) * trend * dow_factor
            
            # 依產品線拆解
            for prefix in item_prefixes:
                weight = {'魯肉飯系列': 0.3, '便當系列': 0.3, '小菜系列': 0.15, '湯品系列': 0.15, '嫩豆腐系列': 0.1}.get(prefix, 0.2)
                p_sales = base_sales * weight * random.uniform(0.9, 1.1)
                
                # 依交易型態拆解
                for t_type in txn_types:
                    t_weight = {'內用': 0.3, '外帶': 0.5, '外送平台': 0.2}.get(t_type, 0.3)
                    t_sales = p_sales * t_weight * random.uniform(0.95, 1.05)
                    
                    # 依支付方式拆解
                    for p_type in payment_types:
                        p_weight = {'現金': 0.4, '信用卡': 0.3, 'Line Pay': 0.2, '街口支付': 0.1}.get(p_type, 0.25)
                        final_sales = t_sales * p_weight * random.uniform(0.98, 1.02)
                        
                        qty = int(final_sales / random.uniform(80, 150))
                        txns = max(1, int(qty * random.uniform(0.7, 0.95)))
                        
                        if final_sales > 10:
                            data.append({
                                'biz_date': date.strftime('%Y-%m-%d'),
                                'store_id': store['store_id'],
                                'item_prefix': prefix,
                                'txn_type': t_type,
                                'payment_type': p_type,
                                'net_sales_value': final_sales,
                                'sales_qty': qty,
                                'txn_count': txns
                            })
                            
    return pd.DataFrame(data), df_stores

# 初始化單例
RAW_DATA, DIM_STORES = generate_base_data()

# --- 服務接口模擬 ---

def get_last_etl_status(*args, **kwargs):
    return {
        'end_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'status': 'success',
        'date_from': RAW_DATA['biz_date'].min(),
        'date_to': RAW_DATA['biz_date'].max(),
        'rows_loaded': len(RAW_DATA)
    }

def get_store_filter_options(*args, **kwargs):
    return DIM_STORES

def get_filter_dimension_options(*args, **kwargs):
    return {
        "txn_type": RAW_DATA['txn_type'].unique().tolist(),
        "payment_type": RAW_DATA['payment_type'].unique().tolist(),
        "item_prefix": RAW_DATA['item_prefix'].unique().tolist(),
        "item_code": []
    }

def _apply_filters(df, filters):
    if not filters: return df
    res = df.copy()
    if 'date_range' in filters and filters['date_range']:
        start, end = filters['date_range']
        res = res[(res['biz_date'] >= str(start)) & (res['biz_date'] <= str(end))]
    if 'city' in filters and filters['city']:
        stores = DIM_STORES[DIM_STORES['city_name'].isin(filters['city'])]['store_id']
        res = res[res['store_id'].isin(stores)]
    if 'division' in filters and filters['division']:
        stores = DIM_STORES[DIM_STORES['division_name'].isin(filters['division'])]['store_id']
        res = res[res['store_id'].isin(stores)]
    if 'store' in filters and filters['store']:
        # Extract ID from "ID Name" string
        s_ids = [s.split(' ')[0] for s in filters['store']]
        res = res[res['store_id'].isin(s_ids)]
    return res

def get_overview_metrics(filters=None, *args, **kwargs):
    return get_overview_metrics_for_filters(filters)

def get_overview_metrics_for_filters(filters=None, *args, **kwargs):
    df = _apply_filters(RAW_DATA, filters)
    if df.empty: return None
    latest_date = df['biz_date'].max()
    latest_df = df[df['biz_date'] == latest_date]
    return {
        'net_sales_value': latest_df['net_sales_value'].sum(),
        'txn_count': latest_df['txn_count'].sum(),
        'sales_qty': latest_df['sales_qty'].sum(),
        'avg_ticket': latest_df['net_sales_value'].sum() / latest_df['txn_count'].sum() if latest_df['txn_count'].sum() > 0 else 0
    }

def get_period_comparison(filters=None, *args, **kwargs):
    df = _apply_filters(RAW_DATA, filters)
    if df.empty: return {}
    latest_date = df['biz_date'].max()
    latest_dt = datetime.strptime(latest_date, '%Y-%m-%d')
    
    def get_sales(target_dt):
        d_str = target_dt.strftime('%Y-%m-%d')
        return df[df['biz_date'] == d_str]['net_sales_value'].sum()

    current = get_sales(latest_dt)
    wow = get_sales(latest_dt - timedelta(days=7))
    mom = get_sales(latest_dt - timedelta(days=28))
    qoq = get_sales(latest_dt - timedelta(days=91))

    return {
        'latest_date': latest_date,
        'wow_date': (latest_dt - timedelta(days=7)).strftime('%Y-%m-%d'),
        'mom_date': (latest_dt - timedelta(days=28)).strftime('%Y-%m-%d'),
        'qoq_date': (latest_dt - timedelta(days=91)).strftime('%Y-%m-%d'),
        'wow': (current - wow) / wow if wow > 0 else 0,
        'mom': (current - mom) / mom if mom > 0 else 0,
        'qoq': (current - qoq) / qoq if qoq > 0 else 0,
    }

def get_daily_trend(filters=None, limit=100, *args, **kwargs):
    df = _apply_filters(RAW_DATA, filters)
    res = df.groupby('biz_date').agg({'net_sales_value':'sum', 'txn_count':'sum', 'sales_qty':'sum'}).reset_index()
    return res.tail(limit)

def get_mix_summary(mix_type, filters=None, limit=10, *args, **kwargs):
    df = _apply_filters(RAW_DATA, filters)
    if mix_type not in df.columns: return pd.DataFrame()
    res = df.groupby(mix_type).agg({'net_sales_value':'sum', 'txn_count':'sum', 'sales_qty':'sum'}).reset_index()
    return res.rename(columns={mix_type: 'mix_value'}).sort_values('net_sales_value', ascending=False).head(limit)

def get_mix_daily_trend(mix_type, filters=None, limit=30, *args, **kwargs):
    df = _apply_filters(RAW_DATA, filters)
    if mix_type not in df.columns: return pd.DataFrame()
    dates = sorted(df['biz_date'].unique())[-limit:]
    sub = df[df['biz_date'].isin(dates)]
    res = sub.groupby(['biz_date', mix_type]).agg({'net_sales_value':'sum', 'txn_count':'sum'}).reset_index()
    res['mix_value'] = res[mix_type]
    return res

def get_group_rankings(group_by, filters=None, limit=10, *args, **kwargs):
    df = _apply_filters(RAW_DATA, filters)
    df_merged = df.merge(DIM_STORES, on='store_id')
    
    if group_by == 'store':
        label_col = 'label'
        df_merged['label'] = df_merged['store_id'] + ' ' + df_merged['store_name']
    elif group_by == 'city':
        label_col = 'city_name'
    else:
        label_col = 'division_name'
        
    res = df_merged.groupby(label_col).agg({'net_sales_value':'sum', 'txn_count':'sum'}).reset_index().rename(columns={label_col: 'label'})
    res['avg_ticket'] = res['net_sales_value'] / res['txn_count']
    return res.sort_values('net_sales_value', ascending=False).head(limit)

def get_store_growth_rankings(filters=None, limit=10, worst=False, *args, **kwargs):
    df = _apply_filters(RAW_DATA, filters)
    latest_date = df['biz_date'].max()
    prior_date = (datetime.strptime(latest_date, '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d')
    
    c = df[df['biz_date'] == latest_date].groupby('store_id')['net_sales_value'].sum().reset_index()
    p = df[df['biz_date'] == prior_date].groupby('store_id')['net_sales_value'].sum().reset_index()
    
    res = c.merge(p, on='store_id', suffixes=('_c', '_p'))
    res = res.merge(DIM_STORES, on='store_id')
    res['label'] = res['store_id'] + ' ' + res['store_name']
    res['current_net_sales'] = res['net_sales_value_c']
    res['prior_net_sales'] = res['net_sales_value_p']
    res['growth_rate'] = (res['net_sales_value_c'] - res['net_sales_value_p']) / res['net_sales_value_p']
    return res.sort_values('growth_rate', ascending=worst).head(limit)

def get_store_contribution_rankings(filters=None, limit=5, *args, **kwargs):
    res = get_store_growth_rankings(filters, limit=30)
    res['net_sales_change'] = res['current_net_sales'] - res['prior_net_sales']
    res['total_current_net_sales'] = res['current_net_sales'].sum()
    res['total_prior_net_sales'] = res['prior_net_sales'].sum()
    res['latest_date'] = RAW_DATA['biz_date'].max()
    res['prior_date'] = (datetime.strptime(res['latest_date'].iloc[0], '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d')
    return res.sort_values('net_sales_change', ascending=False).head(limit)

def get_store_change_waterfall(filters=None, limit=8, *args, **kwargs):
    return get_store_contribution_rankings(filters, limit)

def get_store_anomaly_heatmap(filters=None, days=21, store_limit=12, *args, **kwargs):
    df = _apply_filters(RAW_DATA, filters)
    recent_dates = sorted(df['biz_date'].unique())[-days:]
    top_stores = get_group_rankings('store', filters, limit=store_limit)['label'].tolist()
    s_ids = [s.split(' ')[0] for s in top_stores]
    
    sub = df[df['biz_date'].isin(recent_dates) & df['store_id'].isin(s_ids)]
    res = sub.groupby(['biz_date', 'store_id']).agg({'net_sales_value':'sum'}).reset_index()
    
    # Calculate rolling avg for anomaly
    res = res.merge(DIM_STORES[['store_id', 'store_name']], on='store_id')
    res['label'] = res['store_id'] + ' ' + res['store_name']
    
    # Simple mock deviation
    res['avg_net_sales'] = res.groupby('store_id')['net_sales_value'].transform('mean')
    res['deviation_rate'] = (res['net_sales_value'] - res['avg_net_sales']) / res['avg_net_sales']
    return res

def get_recent_daily_table(filters=None, days=7, limit=None, *args, **kwargs):
    df = _apply_filters(RAW_DATA, filters)
    limit = limit or days
    dates = sorted(df['biz_date'].unique())[-limit:]
    sub = df[df['biz_date'].isin(dates)]
    
    res = sub.groupby(['biz_date', 'store_id']).agg({
        'net_sales_value': 'sum',
        'txn_count': 'sum',
        'sales_qty': 'sum'
    }).reset_index()
    
    res['avg_ticket'] = res['net_sales_value'] / res['txn_count'].replace(0, np.nan)
    res = res.merge(DIM_STORES, on='store_id', how='left')
    res['label'] = res['store_id'] + ' ' + res['store_name'].fillna('')
    return res

def get_store_mix_structure_trend(filters=None, days=30, *args, **kwargs):
    res = get_mix_daily_trend('txn_type', filters, days)
    if not res.empty:
        # Calculate daily share rate
        daily_total = res.groupby('biz_date')['net_sales_value'].transform('sum')
        res['share_rate'] = res['net_sales_value'] / daily_total
        res['store_label'] = filters.get('store', ['所有門市'])[0] if filters else '所有門市'
    return res

def get_store_risk_matrix(filters=None, *args, **kwargs):
    df = _apply_filters(RAW_DATA, filters)
    latest_date = df['biz_date'].max()
    c = df[df['biz_date'] == latest_date].groupby('store_id')['net_sales_value'].sum().reset_index()
    p_date = (datetime.strptime(latest_date, '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d')
    p = df[df['biz_date'] == p_date].groupby('store_id')['net_sales_value'].sum().reset_index()
    
    res = c.merge(p, on='store_id', suffixes=('_c', '_p'))
    res = res.merge(DIM_STORES, on='store_id')
    res['label'] = res['store_id'] + ' ' + res['store_name']
    res['wow_growth'] = (res['net_sales_value_c'] - res['net_sales_value_p']) / res['net_sales_value_p']
    res['current_net_sales'] = res['net_sales_value_c']
    res['prior_net_sales'] = res['net_sales_value_p']
    res['avg_net_sales_21'] = res['current_net_sales'] * random.uniform(0.9, 1.1)
    res['deviation_rate'] = (res['current_net_sales'] - res['avg_net_sales_21']) / res['avg_net_sales_21']
    res['latest_date'] = latest_date
    res['prior_date'] = p_date
    return res

def get_store_customer_ticket_quadrant(filters=None, limit=20, *args, **kwargs):
    df = _apply_filters(RAW_DATA, filters)
    latest_date = df['biz_date'].max()
    p_date = (datetime.strptime(latest_date, '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d')
    
    c = df[df['biz_date'] == latest_date].groupby('store_id').agg({'net_sales_value':'sum', 'txn_count':'sum'}).reset_index()
    p = df[df['biz_date'] == p_date].groupby('store_id').agg({'net_sales_value':'sum', 'txn_count':'sum'}).reset_index()
    
    res = c.merge(p, on='store_id', suffixes=('_c', '_p'))
    res = res.merge(DIM_STORES, on='store_id')
    res['label'] = res['store_id'] + ' ' + res['store_name']
    res['current_net_sales'] = res['net_sales_value_c']
    res['current_txn'] = res['txn_count_c']
    res['prior_txn'] = res['txn_count_p']
    res['current_avg_ticket'] = res['net_sales_value_c'] / res['txn_count_c']
    res['prior_avg_ticket'] = res['net_sales_value_p'] / res['txn_count_p']
    res['txn_change_rate'] = (res['txn_count_c'] - res['txn_count_p']) / res['txn_count_p']
    res['ticket_change_rate'] = (res['current_avg_ticket'] - res['prior_avg_ticket']) / res['prior_avg_ticket']
    res['latest_date'] = latest_date
    res['prior_date'] = p_date
    return res

def get_item_change_waterfall(filters=None, limit=8, *args, **kwargs):
    df = _apply_filters(RAW_DATA, filters)
    latest_date = df['biz_date'].max()
    p_date = (datetime.strptime(latest_date, '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d')
    
    c = df[df['biz_date'] == latest_date].groupby('item_prefix')['net_sales_value'].sum().reset_index()
    p = df[df['biz_date'] == p_date].groupby('item_prefix')['net_sales_value'].sum().reset_index()
    
    res = c.merge(p, on='item_prefix', suffixes=('_c', '_p'))
    res['label'] = res['item_prefix']
    res['item_name'] = res['item_prefix']
    res['net_sales_change'] = res['net_sales_value_c'] - res['net_sales_value_p']
    res['current_net_sales'] = res['net_sales_value_c']
    res['prior_net_sales'] = res['net_sales_value_p']
    res['total_current_net_sales'] = res['current_net_sales'].sum()
    res['total_prior_net_sales'] = res['prior_net_sales'].sum()
    res['latest_date'] = latest_date
    res['prior_date'] = p_date
    return res.sort_values('net_sales_change', ascending=False).head(limit)

def get_item_code_rankings(filters=None, limit=20, *args, **kwargs):
    return get_mix_summary('item_prefix', filters, limit)

def get_item_prefix_rankings(filters=None, limit=20, *args, **kwargs):
    return get_mix_summary('item_prefix', filters, limit)

def get_item_prefix_by_dimension(dimension, filters=None, limit=20, *args, **kwargs):
    df = _apply_filters(RAW_DATA, filters)
    df = df.merge(DIM_STORES, on='store_id')
    dim_col = 'division_name' if dimension == 'division' else 'store_id'
    
    res = df.groupby([dim_col, 'item_prefix']).agg({'net_sales_value':'sum'}).reset_index()
    if dimension == 'store':
        res = res.merge(DIM_STORES[['store_id', 'store_name']], on='store_id')
        res['label'] = res['store_id'] + ' ' + res['store_name']
    else:
        res = res.rename(columns={dim_col: 'label'})
        
    return res.sort_values('net_sales_value', ascending=False).head(limit)

def get_item_prefix_daily_trend(filters=None, limit=30, *args, **kwargs):
    return get_mix_daily_trend('item_prefix', filters, limit)

def get_item_net_sales_qty_quadrant(filters=None, limit=20, *args, **kwargs):
    df = _apply_filters(RAW_DATA, filters)
    latest_date = df['biz_date'].max()
    p_date = (datetime.strptime(latest_date, '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d')
    
    c = df[df['biz_date'] == latest_date].groupby('item_prefix').agg({'net_sales_value':'sum', 'sales_qty':'sum'}).reset_index()
    p = df[df['biz_date'] == p_date].groupby('item_prefix').agg({'net_sales_value':'sum', 'sales_qty':'sum'}).reset_index()
    
    res = c.merge(p, on='item_prefix', suffixes=('_c', '_p'))
    res['item_code'] = res['item_prefix']
    res['item_name'] = res['item_prefix']
    res['current_net_sales'] = res['net_sales_value_c']
    res['prior_net_sales'] = res['net_sales_value_p']
    res['current_sales_qty'] = res['sales_qty_c']
    res['prior_sales_qty'] = res['sales_qty_p']
    res['qty_change_rate'] = (res['sales_qty_c'] - res['sales_qty_p']) / res['sales_qty_p']
    res['sales_change_rate'] = (res['net_sales_value_c'] - res['net_sales_value_p']) / res['net_sales_value_p']
    res['latest_date'] = latest_date
    res['prior_date'] = p_date
    return res.head(limit)

def get_store_item_matrix(filters=None, store_limit=10, item_limit=8, *args, **kwargs):
    df = _apply_filters(RAW_DATA, filters)
    top_stores = get_group_rankings('store', filters, limit=store_limit)['label'].tolist()
    s_ids = [s.split(' ')[0] for s in top_stores]
    top_items = get_mix_summary('item_prefix', filters, limit=item_limit)['mix_value'].tolist()
    
    sub = df[df['store_id'].isin(s_ids) & df['item_prefix'].isin(top_items)]
    res = sub.groupby(['store_id', 'item_prefix']).agg({'net_sales_value':'sum'}).reset_index()
    res = res.merge(DIM_STORES[['store_id', 'store_name']], on='store_id')
    res['store_label'] = res['store_id'] + ' ' + res['store_name']
    
    totals = res.groupby('store_label')['net_sales_value'].transform('sum')
    res['store_total_net_sales'] = totals
    res['share_rate'] = res['net_sales_value'] / totals
    res['item_code'] = res['item_prefix']
    res['item_name'] = res['item_prefix']
    return res

def get_item_price_band_distribution(filters=None, *args, **kwargs):
    # Mock price bands based on item prefixes
    df = get_mix_summary('item_prefix', filters)
    bands = ['< $80', '$80-$120', '$120-$160', '$160+']
    res = []
    for i, b in enumerate(bands):
        sales = df['net_sales_value'].sum() * random.uniform(0.1, 0.4)
        res.append({
            'price_band': b,
            'net_sales_value': sales,
            'sales_qty': sales / (70 + i*30),
            'txn_count': sales / 120,
            'item_count': random.randint(3, 10),
            'avg_unit_price': 70 + i*30,
            'net_sales_share': 0.25
        })
    return pd.DataFrame(res)

def get_bundle_pair_rankings(filters=None, limit=10, *args, **kwargs):
    # Simple mock for bundle pairings
    items = ['魯肉飯+排骨', '雞腿+控肉', '便當+豆腐', '金針湯+魯肉飯', '嫩豆腐+泡菜']
    res = []
    for pair in items:
        a, b = pair.split('+')
        sales = random.uniform(20000, 50000)
        res.append({
            'pair_label': pair, 'item_name_a': a, 'item_name_b': b,
            'pair_txn_count': random.randint(200, 800),
            'pair_net_sales': sales, 'pair_qty': sales/100,
            'multi_item_txn_count': 2000, 'pair_rate': random.uniform(0.05, 0.15)
        })
    return pd.DataFrame(res).sort_values('pair_txn_count', ascending=False).head(limit)

def get_mix_anomaly_heatmap(mix_type, filters=None, days=14, baseline_days=7, top_n=6, *args, **kwargs):
    df = _apply_filters(RAW_DATA, filters)
    recent_dates = sorted(df['biz_date'].unique())[-days:]
    top_mix = get_mix_summary(mix_type, filters, limit=top_n)['mix_value'].tolist()
    
    sub = df[df['biz_date'].isin(recent_dates) & df[mix_type].isin(top_mix)]
    res = sub.groupby(['biz_date', mix_type]).agg({'net_sales_value':'sum'}).reset_index().rename(columns={mix_type: 'label'})
    res['avg_net_sales'] = res.groupby('label')['net_sales_value'].transform('mean')
    res['deviation_rate'] = (res['net_sales_value'] - res['avg_net_sales']) / res['avg_net_sales']
    return res

def get_mix_change_waterfall(mix_type, filters=None, limit=6, *args, **kwargs):
    df = _apply_filters(RAW_DATA, filters)
    latest_date = df['biz_date'].max()
    p_date = (datetime.strptime(latest_date, '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d')
    
    c = df[df['biz_date'] == latest_date].groupby(mix_type)['net_sales_value'].sum().reset_index()
    p = df[df['biz_date'] == p_date].groupby(mix_type)['net_sales_value'].sum().reset_index()
    
    res = c.merge(p, on=mix_type, suffixes=('_c', '_p'))
    res = res.rename(columns={mix_type: 'label'})
    res['net_sales_change'] = res['net_sales_value_c'] - res['net_sales_value_p']
    res['current_net_sales'] = res['net_sales_value_c']
    res['prior_net_sales'] = res['net_sales_value_p']
    res['total_current_net_sales'] = res['current_net_sales'].sum()
    res['total_prior_net_sales'] = res['prior_net_sales'].sum()
    res['latest_date'] = latest_date
    res['prior_date'] = p_date
    return res.sort_values('net_sales_change', ascending=False).head(limit)

def get_payment_by_dimension(dimension, filters=None, limit=20, *args, **kwargs):
    return get_item_prefix_by_dimension(dimension, filters, limit) # Proxy

def get_txn_type_by_dimension(dimension, filters=None, limit=20, *args, **kwargs):
    return get_item_prefix_by_dimension(dimension, filters, limit) # Proxy

def get_txn_payment_cross_matrix(filters=None, top_txn=6, top_payment=6, *args, **kwargs):
    df = _apply_filters(RAW_DATA, filters)
    res = df.groupby(['txn_type', 'payment_type']).agg({'net_sales_value':'sum', 'txn_count':'sum'}).reset_index()
    
    total = res['net_sales_value'].sum()
    res['share_overall'] = res['net_sales_value'] / total
    txn_totals = res.groupby('txn_type')['net_sales_value'].transform('sum')
    res['share_in_txn'] = res['net_sales_value'] / txn_totals
    return res

def get_weekday_weekend_summary(filters=None, *args, **kwargs):
    df = _apply_filters(RAW_DATA, filters)
    df['is_weekend'] = pd.to_datetime(df['biz_date']).dt.weekday >= 5
    res = df.groupby('is_weekend').agg({'net_sales_value':'sum', 'txn_count':'sum'}).reset_index()
    res['day_type'] = res['is_weekend'].map({True: '假日', False: '平日'})
    res['avg_ticket'] = res['net_sales_value'] / res['txn_count']
    return res

def refresh_dataset(run_type='manual', *args, **kwargs):
    global RAW_DATA, DIM_STORES
    RAW_DATA, DIM_STORES = generate_base_data()
    return {
        'rows_loaded': len(RAW_DATA), 
        'date_from': RAW_DATA['biz_date'].min(), 
        'date_to': RAW_DATA['biz_date'].max(),
        'status': 'success'
    }

def calc_pct_change(current, prior):
    if prior is None or prior == 0: return 0
    return (current - prior) / prior
