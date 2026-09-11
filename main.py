import os
import json
import gspread
import smtplib
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from email.mime.text import MIMEText
from oauth2client.service_account import ServiceAccountCredentials

# 共通のヘッダー（人間がブラウザで見ているように装うための設定）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
}

def get_rakuten():
    try:
        # お米ジャンル デイリーランキング
        url = "https://ranking.rakuten.co.jp/daily/100227/"
        res = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.content, "html.parser")
        
        # 1位の商品名と金額（楽天は構造が複雑なため簡易取得）
        top_item = soup.select_one(".rnkRanking_itemName")
        name = top_item.get_text(strip=True) if top_item else "取得失敗"
        
        # 神崎町の順位を全テキストから探す（簡易版）
        rank_kz = "圏外"
        if "神崎町" in soup.get_text():
            rank_kz = "ランクイン中(要確認)"

        return ["楽天", "福岡県赤村(仮)", name[:30], "確認中", "確認中", rank_kz, "ふさおとめ", "確認中"]
    except:
        return ["楽天", "取得失敗", "取得失敗", "-", "-", "-", "-", "-"]

def get_satofull():
    try:
        url = "https://www.satofull.jp/static/ranking/rice.php"
        res = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.content, "html.parser")
        
        # 1位の自治体と品名
        top_town = soup.select_one(".ranking-item-town")
        top_name = soup.select_one(".ranking-item-name")
        town = top_town.get_text(strip=True) if top_town else "取得失敗"
        name = top_name.get_text(strip=True) if top_name else "取得失敗"
        
        # 神崎町の順位を探す
        rank_kz = "圏外"
        items = soup.select(".ranking-item")
        for i, item in enumerate(items, 1):
            if "神崎町" in item.get_text():
                rank_kz = f"{i}位"
                break

        return ["さとふる", town, name[:30], "15,000円", "確認中", rank_kz, "ふさおとめ", "12,000円"]
    except:
        return ["さとふる", "取得失敗", "取得失敗", "-", "-", "-", "-", "-"]

def get_furunavi():
    try:
        url = "https://furunavi.jp/ranking_list.aspx?categoryid=21"
        res = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.content, "html.parser")
        
        # 1位の自治体と品名
        top_town = soup.select_one(".municipality-name")
        top_name = soup.select_one(".product-name")
        town = top_town.get_text(strip=True) if top_town else "取得失敗"
        name = top_name.get_text(strip=True) if top_name else "取得失敗"
        
        # 神崎町の順位
        rank_kz = "圏外"
        items = soup.select(".ranking-item")
        for i, item in enumerate(items, 1):
            if "神崎町" in item.get_text():
                rank_kz = f"{i}位"
                break

        return ["ふるなび", town, name[:30], "5,700円", "確認中", rank_kz, "ふさおとめ", "12,000円"]
    except:
        return ["ふるなび", "取得失敗", "取得失敗", "-", "-", "-", "-", "-"]

def update_sheet(data):
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds_json = json.loads(os.environ["GCP_SA_JSON"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(os.environ["SPREADSHEET_ID"]).sheet1
        
        today = datetime.now().strftime("%Y/%m/%d")
        for row in data:
            sheet.append_row([today] + row)
    except Exception as e:
        print(f"Sheet Error: {e}")

def send_email(data):
    try:
        today = datetime.now().strftime("%Y/%m/%d")
        mail_content = f"{today} のふるさと納税お米ランキング（自動取得結果）\n\n"
        for row in data:
            mail_content += f"--- {row[0]} ---\n1位: {row[1]} / {row[2]}\n神崎町順位: {row[5]}\n\n"
        
        msg = MIMEText(mail_content)
        msg['Subject'] = f"【自動取得】お米ランキング報告（{today}）"
        msg['From'] = os.environ["EMAIL_USER"]
        msg['To'] = os.environ["EMAIL_USER"]

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(os.environ["EMAIL_USER"], os.environ["EMAIL_PASS"])
            server.send_message(msg)
    except Exception as e:
        print(f"Email Error: {e}")

if __name__ == "__main__":
    # 各サイトからデータを取得
    rakuten = get_rakuten()
    satofull = get_satofull()
    furunavi = get_furunavi()
    
    all_data = [rakuten, satofull, furunavi]
    
    # 保存と送信
    update_sheet(all_data)
    send_email(all_data)
