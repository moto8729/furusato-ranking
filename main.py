import os
import json
import gspread
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright

# stealthライブラリを安全に読み込む設定
try:
    from playwright_stealth import stealth
except ImportError:
    # ライブラリがない場合は何もしない関数を代用
    def stealth(page):
        pass

def scrape_furusato():
    results = []
    with sync_playwright() as p:
        # ブラウザを起動（ヘッドレスモード）
        browser = p.chromium.launch(headless=True)
        # 人間のブラウザを偽装する設定
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

        # --- 各サイトの取得処理を定義 ---
        sites = [
            {"name": "楽天", "rice_url": "https://ranking.rakuten.co.jp/daily/100227/", "total_url": "https://ranking.rakuten.co.jp/daily/", "item_selector": ".rnkRanking_itemName", "price_selector": ".rnkRanking_price"},
            {"name": "さとふる", "rice_url": "https://www.satofull.jp/static/ranking/rice.php", "total_url": "https://www.satofull.jp/static/ranking/total.php", "item_selector": ".ranking-item-name", "price_selector": ".ranking-item-price"},
            {"name": "ふるなび", "rice_url": "https://furunavi.jp/ranking_list.aspx?categoryid=21", "total_url": "https://furunavi.jp/ranking_list.aspx", "item_selector": ".product-name", "price_selector": ".product-price"}
        ]

        for site in sites:
            try:
                page = context.new_page()
                stealth(page) # ここでの呼び出しエラーを回避する修正をしました
                
                # 1. お米ランキングの取得
                page.goto(site["rice_url"], wait_until="load", timeout=60000)
                page.wait_for_timeout(3000) # 読み込み待ち
                
                # お米1位の情報
                rice_1_name = page.locator(site["item_selector"]).first.inner_text().strip()
                rice_1_price = page.locator(site["price_selector"]).first.inner_text().strip()
                town_1 = "取得中"
                if site["name"] == "さとふる":
                    town_1 = page.locator(".ranking-item-town").first.inner_text().strip()
                elif site["name"] == "ふるなび":
                    town_1 = page.locator(".municipality-name").first.inner_text().strip()
                else:
                    town_1 = "商品名参照"

                # 神崎町がランキング内（TOP50程度）にいるか探す
                kz_rank = "圏外"
                all_names = page.locator(site["item_selector"]).all_inner_texts()
                for i, name in enumerate(all_names, 1):
                    if "神崎町" in name:
                        kz_rank = f"{i}位"
                        break

                # 2. 総合ランキングでお米1位が何位か探す
                page.goto(site["total_url"], wait_until="load", timeout=60000)
                page.wait_for_timeout(3000)
                overall_rank = "圏外"
                all_total_names = page.locator(site["item_selector"]).all_inner_texts()
                for i, name in enumerate(all_total_names, 1):
                    # 商品名の一部が一致するか照合
                    if rice_1_name[:15] in name:
                        overall_rank = f"{i}位"
                        break
                
                results.append([site["name"], town_1, rice_1_name[:40], rice_1_price, overall_rank, kz_rank, "ふさおとめ等", "確認中"])
                page.close()
            except Exception as e:
                results.append([site["name"], "取得失敗", str(e)[:40], "-", "-", "-", "-", "-"])

        browser.close()
    return results

def update_sheet(data):
    try:
        json_str = os.environ.get("GCP_SA_JSON")
        if not json_str: return
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
        body = f"{today} ふるさと納税ランキング報告\n\n"
        for r in data:
            body += f"【{r[0]}】\n・お米1位: {r[1]} / {r[2]}\n・金額: {r[3]}\n・総合順位: {r[4]}\n・神崎町順位: {r[5]}\n\n"
        
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
