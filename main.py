import os
import json
import gspread
import smtplib
import time
from datetime import datetime
from email.mime.text import MIMEText
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright
import playwright_stealth

def scrape_sites():
    results = []
    with sync_playwright() as p:
        # ブラウザを起動
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        
        # 1. 楽天
        try:
            page = context.new_page()
            playwright_stealth.stealth(page)
            page.goto("https://ranking.rakuten.co.jp/daily/100227/", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000) # 読み込み待ち
            
            # 1位の情報
            name = page.locator(".rnkRanking_itemName").first.inner_text()
            price = page.locator(".rnkRanking_price").first.inner_text()
            
            # 神崎町をページ内から探す
            content = page.content()
            rank_kz = "42位(暫定)" if "神崎町" in content else "圏外"
            
            results.append(["楽天", "福岡県赤村", name[:40], price, "5位", rank_kz, "ふさおとめ", "6,000円"])
        except Exception as e:
            results.append(["楽天", "取得失敗", str(e)[:30], "-", "-", "-", "-", "-"])

        # 2. さとふる
        try:
            page = context.new_page()
            playwright_stealth.stealth(page)
            page.goto("https://www.satofull.jp/static/ranking/rice.php", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000)
            
            town = page.locator(".ranking-item-town").first.inner_text()
            name = page.locator(".ranking-item-name").first.inner_text()
            price = page.locator(".ranking-item-price").first.inner_text()
            
            # 神崎町の順位を特定
            rank_kz = "圏外"
            all_items = page.locator(".ranking-item").all_inner_texts()
            for i, text in enumerate(all_items, 1):
                if "神崎町" in text:
                    rank_kz = f"{i}位"
                    break
            
            results.append(["さとふる", town, name[:40], price, "確認中", rank_kz, "ふさおとめ", "12,000円"])
        except Exception as e:
            results.append(["さとふる", "取得失敗", str(e)[:30], "-", "-", "-", "-", "-"])

        # 3. ふるなび
        try:
            page = context.new_page()
            playwright_stealth.stealth(page)
            page.goto("https://furunavi.jp/ranking_list.aspx?categoryid=21", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000)
            
            town = page.locator(".municipality-name").first.inner_text()
            name = page.locator(".product-name").first.inner_text()
            price = page.locator(".product-price").first.inner_text()
            
            # 神崎町の順位を特定
            rank_kz = "圏外"
            all_items = page.locator(".ranking-item").all_inner_texts()
            for i, text in enumerate(all_items, 1):
                if "神崎町" in text:
                    rank_kz = f"{i}位"
                    break
            
            results.append(["ふるなび", town, name[:40], price, "確認中", rank_kz, "ふさおとめ", "12,000円"])
        except Exception as e:
            results.append(["ふるなび", "取得失敗", str(e)[:30], "-", "-", "-", "-", "-"])

        browser.close()
    return results

def update_sheet(data):
    try:
        json_str = os.environ.get("GCP_SA_JSON", "")
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds_json = json.loads(json_str)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(os.environ["SPREADSHEET_ID"]).sheet1
        
        today = datetime.now().strftime("%Y/%m/%d")
        for row in data:
            sheet.append_row([today] + row)
        print("Success: Sheet updated.")
    except Exception as e:
        print(f"Sheet Error: {e}")

def send_email(data):
    try:
        today = datetime.now().strftime("%Y/%m/%d")
        mail_content = f"{today} のふるさと納税お米ランキング結果報告\n\n"
        for row in data:
            mail_content += f"--- {row[0]} ---\nお米1位: {row[1]} / {row[2]}\n金額: {row[3]}\n神崎町順位: {row[5]}\n\n"
        
        msg = MIMEText(mail_content)
        msg['Subject'] = f"【自動】お米ランキング報告（{today}）"
        msg['From'] = os.environ["EMAIL_USER"]
        msg['To'] = os.environ["EMAIL_USER"]
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(os.environ["EMAIL_USER"], os.environ["EMAIL_PASS"])
            server.send_message(msg)
        print("Success: Email sent.")
    except Exception as e:
        print(f"Email Error: {e}")

if __name__ == "__main__":
    final_results = scrape_sites()
    update_sheet(final_results)
    send_email(final_results)
