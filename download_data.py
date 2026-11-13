import requests
import os
import gzip
import shutil
import time
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 設定下載目標
DATA_SOURCES = {
    "Options": "https://www.taifex.com.tw/data_gov/taifex_open_data.asp?data_name=OptionsTimeAndSalesData",
    "Futures": "https://www.taifex.com.tw/data_gov/taifex_open_data.asp?data_name=TimeAndSalesData"
}

def create_session() -> requests.Session:
    """建立帶有重試機制的 Session"""
    session = requests.Session()
    retry_strategy = Retry(
        total=5,
        backoff_factor=2,          # 2, 4, 8, 16, 32 秒
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Encoding": "identity",  # 避免某些伺服器壓縮問題
    })
    return session


def download_with_retry(session: requests.Session, url: str, filepath: str, max_attempts: int = 5) -> bool:
    """
    串流下載並寫入檔案，失敗自動重試。
    成功回傳 True，失敗回傳 False。
    """
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"  嘗試第 {attempt}/{max_attempts} 次...")
            # 使用 stream=True 避免一次把整個檔案載入記憶體
            with session.get(url, stream=True, timeout=(15, 180)) as response:
                response.raise_for_status()

                # 先寫到暫存檔，成功後再 rename，避免半成品
                tmp_path = filepath + ".tmp"
                total_size = 0
                with open(tmp_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=1024 * 256):  # 256KB
                        if chunk:
                            f.write(chunk)
                            total_size += len(chunk)

                # 基本完整性檢查
                if total_size < 1000:
                    print(f"  檔案太小 ({total_size} bytes)，可能今日無資料或下載失敗")
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                    return False

                # 簡單檢查是否為 CSV（前幾個 byte 不應該是 HTML）
                with open(tmp_path, "rb") as f:
                    head = f.read(200).decode("utf-8", errors="ignore").lower()
                    if "<html" in head or "<!doctype" in head:
                        print("  下載到的是網頁而非 CSV，可能被擋或今日無資料")
                        os.remove(tmp_path)
                        return False

                os.replace(tmp_path, filepath)
                print(f"  下載完成，大小約 {total_size / 1024 / 1024:.1f} MB")
                return True

        except (requests.exceptions.ChunkedEncodingError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.RequestException) as e:
            print(f"  第 {attempt} 次失敗: {type(e).__name__}: {e}")
            if os.path.exists(filepath + ".tmp"):
                try:
                    os.remove(filepath + ".tmp")
                except OSError:
                    pass
            if attempt < max_attempts:
                sleep_sec = min(2 ** attempt, 60)  # 最多等 60 秒
                print(f"  等待 {sleep_sec} 秒後重試...")
                time.sleep(sleep_sec)
            else:
                print(f"  已達最大重試次數，放棄此檔案")
                return False

    return False


def download_and_compress():
    today_str = datetime.now().strftime("%Y%m%d")
    os.makedirs("data", exist_ok=True)

    session = create_session()
    downloaded_files = []

    for name, url in DATA_SOURCES.items():
        filename = f"{name}_{today_str}.csv"
        filepath = os.path.join("data", filename)
        gz_filepath = f"{filepath}.gz"

        print(f"正在下載 {name}...")
        success = download_with_retry(session, url, filepath)

        if success:
            # Gzip 壓縮
            with open(filepath, "rb") as f_in:
                with gzip.open(gz_filepath, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

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
