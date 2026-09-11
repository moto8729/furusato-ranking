import os
import json
import gspread
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth

def scrape_furusato():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # --- 1. 楽天の取得 ---
        try:
            page = context.new_page()
            stealth(page)
            # お米ランキング
            page.goto("https://ranking.rakuten.co.jp/daily/100227/", wait_until="networkidle")
            page.wait_for_timeout(2000)
            rice_top_name = page.locator(".rnkRanking_itemName").first.inner_text()
            rice_top_price = page.locator(".rnkRanking_price").first.inner_text()
            
            # 神崎町を探す
            kz_rank = "圏外"
            all_text = page.content()
            if "神崎町" in all_text:
                kz_rank = "入賞(詳細確認)"

            # 総合ランキングでお米1位を探す
            page.goto("https://ranking.rakuten.co.jp/daily/", wait_until="networkidle")
            overall_rank = "圏外"
            overall_items = page.locator(".rnkRanking_itemName").all_inner_texts()
            for i, name in enumerate(overall_items, 1):
                if rice_top_name[:10] in name:
                    overall_rank = f"{i}位"
                    break
            
            results.append(["楽天", "福岡県赤村(推定)", rice_top_name[:40], rice_top_price, overall_rank, kz_rank, "ふさおとめ", "6,000円"])
        except Exception as e:
            results.append(["楽天", "取得失敗", str(e)[:30], "-", "-", "-", "-", "-"])

        # --- 2. さとふるの取得 ---
        try:
            page = context.new_page()
            stealth(page)
            page.goto("https://www.satofull.jp/static/ranking/rice.php", wait_until="networkidle")
            page.wait_for_timeout(2000)
            town = page.locator(".ranking-item-town").first.inner_text()
            name = page.locator(".ranking-item-name").first.inner_text()
            price = page.locator(".ranking-item-price").first.inner_text()
            
            # 神崎町順位
            kz_rank = "圏外"
            items = page.locator(".ranking-item").all_inner_texts()
            for i, text in enumerate(items, 1):
                if "神崎町" in text:
                    kz_rank = f"{i}位"
                    break
            
            # 総合でお米1位を探す
            page.goto("https://www.satofull.jp/static/ranking/total.php", wait_until="networkidle")
            overall_rank = "圏外"
            total_items = page.locator(".ranking-item-name").all_inner_texts()
            for i, t_name in enumerate(total_items, 1):
                if name[:10] in t_name:
                    overall_rank = f"{i}位"
                    break

            results.append(["さとふる", town, name[:40], price, overall_rank, kz_rank, "ふさおとめ", "12,000円"])
        except Exception as e:
            results.append(["さとふる", "取得失敗", str(e)[:30], "-", "-", "-", "-", "-"])

        # --- 3. ふるなびの取得 ---
        try:
            page = context.new_page()
            stealth(page)
            page.goto("https://furunavi.jp/ranking_list.aspx?categoryid=21", wait_until="networkidle")
            page.wait_for_timeout(2000)
            town = page.locator(".municipality-name").first.inner_text()
            name = page.locator(".product-name").first.inner_text()
            price = page.locator(".product-price").first.inner_text()
            
            kz_rank = "圏外"
            items = page.locator(".ranking-item").all_inner_texts()
            for i, text in enumerate(items, 1):
                if "神崎町" in text:
                    kz_rank = f"{i}位"
                    break

            # 総合でお米1位を探す
            page.goto("https://furunavi.jp/ranking_list.aspx", wait_until="networkidle")
            overall_rank = "圏外"
            total_items = page.locator(".product-name").all_inner_texts()
            for i, t_name in enumerate(total_items, 1):
                if name[:10] in t_name:
                    overall_rank = f"{i}位"
                    break

            results.append(["ふるなび", town, name[:40], price, overall_rank, kz_rank, "ふさおとめ", "12,000円"])
        except Exception as e:
            results.append(["ふるなび", "取得失敗", str(e)[:30], "-", "-", "-", "-", "-"])

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
        print("Success: Sheet updated")
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
        print("Success: Email sent")
    except Exception as e:
        print(f"Email Error: {e}")

if __name__ == "__main__":
    final_data = scrape_furusato()
    update_sheet(final_data)
    send_email(final_data)
