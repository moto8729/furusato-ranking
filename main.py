import os
import json
import gspread
import smtplib
import time
import random
from datetime import datetime
from email.mime.text import MIMEText
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright
import playwright_stealth

def scrape_furusato():
    results = []
    with sync_playwright() as p:
        # iPhone 13 Proの設定を借りる
        iphone = p.devices['iPhone 13 Pro']
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            **iphone,
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
            extra_http_headers={"Accept-Language": "ja,en-US;q=0.9,en;q=0.8"}
        )

        sites = [
            {
                "name": "楽天",
                "rice_url": "https://ranking.rakuten.co.jp/daily/100227/",
                "total_url": "https://ranking.rakuten.co.jp/daily/",
                "item_sel": ".rnkRanking_itemName",
                "price_sel": ".rnkRanking_price"
            },
            {
                "name": "さとふる",
                "rice_url": "https://www.satofull.jp/static/ranking/rice.php",
                "total_url": "https://www.satofull.jp/static/ranking/total.php",
                "item_sel": ".ranking-item-name",
                "price_sel": ".ranking-item-price"
            },
            {
                "name": "ふるなび",
                "rice_url": "https://furunavi.jp/ranking_list.aspx?categoryid=21",
                "total_url": "https://furunavi.jp/ranking_list.aspx",
                "item_sel": ".product-name",
                "price_sel": ".product-price"
            }
        ]

        for s in sites:
            try:
                # アクセス前に5〜10秒のランダムな休憩
                time.sleep(random.uniform(5, 10))
                
                page = context.new_page()
                playwright_stealth.stealth(page)
                
                # 1. お米ランキングの取得
                # タイムアウトを120秒に延長し、読み込み完了を待たずに進む
                page.goto(s["rice_url"], wait_until="domcontentloaded", timeout=120000)
                page.wait_for_timeout(5000) # 画面が開くまで5秒待つ
                
                # 商品名が出てくるのを待つ
                page.wait_for_selector(s["item_sel"], timeout=20000)
                
                rice_top_name = page.locator(s["item_sel"]).first.inner_text().strip()
                rice_top_price = page.locator(s["price_sel"]).first.inner_text().strip()
                
                # 神崎町をページ全体から探す
                content = page.content()
                kz_rank = "圏外"
                if "神崎町" in content:
                    all_items = page.locator(s["item_sel"]).all_inner_texts()
                    for i, name in enumerate(all_items, 1):
                        if "神崎町" in name:
                            kz_rank = f"{i}位"
                            break

                # 2. 総合ランキングでお米1位を探す
                page.goto(s["total_url"], wait_until="domcontentloaded", timeout=120000)
                page.wait_for_timeout(5000)
                
                overall_rank = "圏外"
                total_items = page.locator(s["item_sel"]).all_inner_texts()
                for i, t_name in enumerate(total_items, 1):
                    if rice_top_name[:10] in t_name:
                        overall_rank = f"{i}位"
                        break
                
                results.append([s["name"], "成功", rice_top_name[:40], rice_top_price, overall_rank, kz_rank, "ふさおとめ等", "12,000円"])
                page.close()
                print(f"{s['name']} の取得に成功しました")

            except Exception as e:
                results.append([s["name"], "取得失敗", "読込エラー", "-", "-", "-", "-", "-"])
                print(f"{s['name']} でエラーが発生しました: {e}")

        browser.close()
    return results

def update_sheet(data):
    try:
        json_str = os.environ.get("GCP_SA_JSON")
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(json_str), scope)
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
        body = f"{today} のふるさと納税ランキング結果（iPhone偽装モード）\n\n"
        for r in data:
            body += f"【{r[0]}】\n・状態: {r[1]}\n・お米1位: {r[2]}\n・総合順位: {r[4]}\n・神崎町順位: {r[5]}\n\n"
        msg = MIMEText(body)
        msg['Subject'] = f"【自動】ランキング報告（{today}）"
        msg['From'] = os.environ["EMAIL_USER"]
        msg['To'] = os.environ["EMAIL_USER"]
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(os.environ["EMAIL_USER"], os.environ["EMAIL_PASS"])
            server.send_message(msg)
    except Exception as e:
        print(f"Email Error: {e}")

if __name__ == "__main__":
    final_data = scrape_furusato()
    update_sheet(final_data)
    send_email(final_data)
