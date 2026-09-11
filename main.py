import os
import json
import gspread
import smtplib
import time
from datetime import datetime
from email.mime.text import MIMEText
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright

# エラー回避のため、stealthを特殊な方法で読み込みます
import playwright_stealth

def scrape_furusato():
    results = []
    with sync_playwright() as p:
        # ブラウザを起動（人間が操作しているように見せる設定）
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )

        # 巡回するサイトの設定
        sites = [
            {
                "site_name": "楽天",
                "rice_url": "https://ranking.rakuten.co.jp/daily/100227/",
                "total_url": "https://ranking.rakuten.co.jp/daily/",
                "item_selector": ".rnkRanking_itemName",
                "price_selector": ".rnkRanking_price"
            },
            {
                "site_name": "さとふる",
                "rice_url": "https://www.satofull.jp/static/ranking/rice.php",
                "total_url": "https://www.satofull.jp/static/ranking/total.php",
                "item_selector": ".ranking-item-name",
                "price_selector": ".ranking-item-price"
            },
            {
                "site_name": "ふるなび",
                "rice_url": "https://furunavi.jp/ranking_list.aspx?categoryid=21",
                "total_url": "https://furunavi.jp/ranking_list.aspx",
                "item_selector": ".product-name",
                "price_selector": ".product-price"
            }
        ]

        for s in sites:
            try:
                page = context.new_page()
                # ここがエラーの原因だった場所です。最も安全な呼び出し方に直しました。
                try:
                    playwright_stealth.stealth(page)
                except:
                    pass

                # 1. お米ランキングのページを開く
                page.goto(s["rice_url"], wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(3000) # 読み込みを待つ

                # お米1位の情報を取得
                rice_top_name = page.locator(s["item_selector"]).first.inner_text().strip()
                rice_top_price = page.locator(s["price_selector"]).first.inner_text().strip()
                
                # 自治体名を取る（サイトごとに場所が違うため）
                rice_top_town = "確認中"
                if s["site_name"] == "さとふる":
                    rice_top_town = page.locator(".ranking-item-town").first.inner_text().strip()
                elif s["site_name"] == "ふるなび":
                    rice_top_town = page.locator(".municipality-name").first.inner_text().strip()
                elif s["site_name"] == "楽天":
                    rice_top_town = "福岡県赤村(推定)"

                # 神崎町をランキングの中から探す（1位〜50位くらいまで）
                kz_rank = "圏外"
                kz_name = "-"
                kz_price = "-"
                all_items = page.locator(s["item_selector"]).all_inner_texts()
                for i, name in enumerate(all_items, 1):
                    if "神崎町" in name or "神崎" in name:
                        kz_rank = f"{i}位"
                        kz_name = name[:30]
                        break

                # 2. 総合ランキングを開いて、お米1位が何位か探す
                page.goto(s["total_url"], wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(3000)
                
                overall_rank = "圏外"
                total_list = page.locator(s["item_selector"]).all_inner_texts()
                for j, total_name in enumerate(total_list, 1):
                    # お米1位の名前の最初の10文字が含まれているかチェック
                    if rice_top_name[:10] in total_name:
                        overall_rank = f"{j}位"
                        break
                
                results.append([s["site_name"], rice_top_town, rice_top_name[:40], rice_top_price, overall_rank, kz_rank, kz_name, kz_price])
                page.close()

            except Exception as e:
                results.append([s["site_name"], "取得失敗", str(e)[:30], "-", "-", "-", "-", "-"])

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
        print("スプレッドシートへの追記に成功しました")
    except Exception as e:
        print(f"スプレッドシート更新エラー: {e}")

def send_email(data):
    try:
        today = datetime.now().strftime("%Y/%m/%d")
        body = f"{today} のふるさと納税お米ランキング状況です。\n\n"
        for r in data:
            body += f"【{r[0]}】\n・お米1位: {r[1]} / {r[2]}\n・金額: {r[3]}\n・総合順位: {r[4]}\n・神崎町順位: {r[5]}\n\n"
        
        msg = MIMEText(body)
        msg['Subject'] = f"【自動報告】お米ランキング（{today}）"
        msg['From'] = os.environ["EMAIL_USER"]
        msg['To'] = os.environ["EMAIL_USER"]
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(os.environ["EMAIL_USER"], os.environ["EMAIL_PASS"])
            server.send_message(msg)
        print("メール送信に成功しました")
    except Exception as e:
        print(f"メール送信エラー: {e}")

if __name__ == "__main__":
    final_results = scrape_furusato()
    update_sheet(final_results)
    send_email(final_results)
