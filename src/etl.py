def check_and_run_etl(mode='auto'):
    return {'status': 'skip', 'reason': 'DEMO mode'}

def run_etl_process():
    return {'rows_loaded': 0, 'status': 'manual_demo'}

def refresh_dataset(run_type='manual'):
    # 返回模擬的更新結果
    return {
        'rows_loaded': 15234, 
        'date_from': '2025-12-18', 
        'date_to': '2026-03-27',
        'status': 'success'
    }
