import requests
import os
import gzip
import shutil
from datetime import datetime

# 設定下載目標
DATA_SOURCES = {
    "Options": "https://www.taifex.com.tw/data_gov/taifex_open_data.asp?data_name=OptionsTimeAndSalesData",
    "Futures": "https://www.taifex.com.tw/data_gov/taifex_open_data.asp?data_name=TimeAndSalesData"
}

def download_and_compress():
    today_str = datetime.now().strftime("%Y%m%d")
    os.makedirs('data', exist_ok=True)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
    }

    downloaded_files = []

    for name, url in DATA_SOURCES.items():
        filename = f"{name}_{today_str}.csv"
        filepath = os.path.join('data', filename)
        gz_filepath = f"{filepath}.gz"

        print(f"正在下載 {name}...")
        response = requests.get(url, headers=headers, timeout=60)
        
        # 檢查內容是否有效 (期交所沒開盤時可能回傳空或錯誤網頁)
        if response.status_code == 200 and len(response.content) > 1000:
            # 先存成臨時 CSV
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            # 進行 Gzip 壓縮
            with open(filepath, 'rb') as f_in:
                with gzip.open(gz_filepath, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # 刪除原始大檔案
            os.remove(filepath)
            downloaded_files.append(gz_filepath)
            print(f"成功壓縮: {gz_filepath}")
        else:
            print(f"{name} 下載失敗或今日無資料。")

    return downloaded_files

if __name__ == "__main__":
    files = download_and_compress()
    if not files:
        print("今日無任何數據更新。")