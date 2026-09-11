import os
import json
import gspread
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright
import playwright_stealth

def scrape_furusato():
    results = []
    with sync_playwright() as p:
        # ブラウザを起動。少しゆっくり動かす設定を追加
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800},
            locale="ja-JP"
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
                page = context.new_page()
                playwright_stealth.stealth(page)
                
                # 1. お米ランキングの取得 (タイムアウト対策で待機条件を緩和)
                page.goto(s["rice_url"], wait_until="commit", timeout=90000)
                # 要素が出るまで最大15秒待つ
                page.wait_for_selector(s["item_sel"], timeout=15000)
                
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
                page.goto(s["total_url"], wait_until="commit", timeout=90000)
                page.wait_for_selector(s["item_sel"], timeout=15000)
                
                overall_rank = "圏外"
                total_items = page.locator(s["item_sel"]).all_inner_texts()
                for i, t_name in enumerate(total_items, 1):
                    if rice_top_name[:10] in t_name:
                        overall_rank = f"{i}位"
                        break
                
                results.append([s["name"], "取得完了", rice_top_name[:40], rice_top_price, overall_rank, kz_rank, "ふさおとめ等", "確認中"])
                page.close()
            except Exception as e:
                # 失敗しても記録は残す
                results.append([s["name"], "一部失敗", "読込エラー", "-", "-", "-", "-", "-"])
                print(f"Error at {s['name']}: {e}")

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
        body = f"{today} のランキング結果報告\n\n"
        for r in data:
            body += f"【{r[0]}】\n・お米1位: {r[2]}\n・総合順位: {r[4]}\n・神崎町順位: {r[5]}\n\n"
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
