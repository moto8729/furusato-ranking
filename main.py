import os
import json
import gspread
import smtplib
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from email.mime.text import MIMEText
from oauth2client.service_account import ServiceAccountCredentials

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
}

def get_rakuten():
    try:
        url = "https://ranking.rakuten.co.jp/daily/100227/"
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.encoding = res.apparent_encoding # 文字化け対策
        soup = BeautifulSoup(res.text, "html.parser")
        
        top_item = soup.select_one(".rnkRanking_itemName")
        name = top_item.get_text(strip=True) if top_item else "取得失敗"
        
        rank_kz = "圏外"
        if "神崎町" in soup.get_text():
            rank_kz = "ランクイン中"

        return ["楽天", "福岡県赤村(仮)", str(name)[:30], "6,000円", "5位", rank_kz, "ふさおとめ", "6,000円"]
    except Exception as e:
        return ["楽天", "エラー", str(e)[:20], "-", "-", "-", "-", "-"]

def get_satofull():
    try:
        url = "https://www.satofull.jp/static/ranking/rice.php"
        res = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        
        top_town = soup.select_one(".ranking-item-town")
        top_name = soup.select_one(".ranking-item-name")
        town = top_town.get_text(strip=True) if top_town else "取得失敗"
        name = top_name.get_text(strip=True) if top_name else "取得失敗"
        
        rank_kz = "圏外"
        items = soup.select(".ranking-item")
        for i, item in enumerate(items, 1):
            if "神崎町" in item.get_text():
                rank_kz = f"{i}位"
                break
        return ["さとふる", str(town), str(name)[:30], "15,000円", "2位", rank_kz, "ふさおとめ", "12,000円"]
    except Exception as e:
        return ["さとふる", "エラー", str(e)[:20], "-", "-", "-", "-", "-"]

def get_furunavi():
    try:
        url = "https://furunavi.jp/ranking_list.aspx?categoryid=21"
        res = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        
        top_town = soup.select_one(".municipality-name")
        top_name = soup.select_one(".product-name")
        town = top_town.get_text(strip=True) if top_town else "取得失敗"
        name = top_name.get_text(strip=True) if top_name else "取得失敗"
        
        rank_kz = "圏外"
        items = soup.select(".ranking-item")
        for i, item in enumerate(items, 1):
            if "神崎町" in item.get_text():
                rank_kz = f"{i}位"
                break
        return ["ふるなび", str(town), str(name)[:30], "5,700円", "8位", rank_kz, "ふさおとめ", "12,000円"]
    except Exception as e:
        return ["ふるなび", "エラー", str(e)[:20], "-", "-", "-", "-", "-"]

def update_sheet(data):
    try:
        json_str = os.environ.get("GCP_SA_JSON", "")
        if not json_str:
            print("Sheet Error: GCP_SA_JSON is empty")
            return
        
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds_json = json.loads(json_str)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(os.environ["SPREADSHEET_ID"]).sheet1
        
        today = datetime.now().strftime("%Y/%m/%d")
        for row in data:
            sheet.append_row([today] + row)
        print("スプレッドシートを更新しました")
    except Exception as e:
        print(f"Sheet Error: {e}")

def send_email(data):
    try:
        today = datetime.now().strftime("%Y/%m/%d")
        mail_content = f"{today} のランキング結果報告\n\n"
        for row in data:
            mail_content += f"--- {str(row[0])} ---\n1位: {str(row[1])} / {str(row[2])}\n神崎町順位: {str(row[5])}\n\n"
        
        msg = MIMEText(mail_content)
        msg['Subject'] = f"【自動】お米ランキング（{today}）"
        msg['From'] = os.environ["EMAIL_USER"]
        msg['To'] = os.environ["EMAIL_USER"]

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(os.environ["EMAIL_USER"], os.environ["EMAIL_PASS"])
            server.send_message(msg)
        print("メールを送信しました")
    except Exception as e:
        print(f"Email Error: {e}")

if __name__ == "__main__":
    results = [get_rakuten(), get_satofull(), get_furunavi()]
    update_sheet(results)
    send_email(results)
