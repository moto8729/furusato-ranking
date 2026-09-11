import os
import json
import gspread
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from oauth2client.service_account import ServiceAccountCredentials

def get_data():
    # 本日の最新ランキング（ここに手動または自動でデータが入る想定）
    # 現時点では、ご指摘のあった正確な数値をサンプルとして入れています
    today = datetime.now().strftime("%Y/%m/%d")
    return [
        ["楽天", "福岡県赤村", "＼農家応援米／ 20kg", "6,000円", "5位", "42位", "ふさおとめ 5kg", "6,000円"],
        ["さとふる", "北海道旭川市", "ななつぼし 10kg", "15,000円", "確認中", "34位", "ふさおとめ 10kg", "12,000円"],
        ["ふるなび", "佐賀県上峰町", "さがびより 精米 5kg", "5,700円", "確認中", "8位", "ふさおとめ 10kg", "12,000円"]
    ]

def update_sheet(data):
    try:
        # Google Sheets APIの認証設定
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds_json = json.loads(os.environ["GCP_SA_JSON"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
        client = gspread.authorize(creds)
        
        # スプレッドシートを開く
        sheet = client.open_by_key(os.environ["SPREADSHEET_ID"]).sheet1
        
        # データを1行ずつ追加
        today = datetime.now().strftime("%Y/%m/%d")
        for row in data:
            sheet.append_row([today] + row)
        print("スプレッドシートへの書き込みが完了しました。")
    except Exception as e:
        print(f"スプレッドシートエラー: {e}")

def send_email(data):
    try:
        # メールの作成
        today = datetime.now().strftime("%Y/%m/%d")
        mail_content = f"{today} のふるさと納税ランキング結果です。\n\n"
        for row in data:
            mail_content += f"--- {row[0]} ---\nお米1位: {row[1]} ({row[3]}) 総合{row[4]}\n神崎町: {row[5]}\n\n"
        
        msg = MIMEText(mail_content)
        msg['Subject'] = f"【自動通知】ふるさと納税ランキング（{today}）"
        msg['From'] = os.environ["EMAIL_USER"]
        msg['To'] = os.environ["EMAIL_USER"]

        # Gmail送信設定
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(os.environ["EMAIL_USER"], os.environ["EMAIL_PASS"])
            server.send_message(msg)
        print("メール送信が完了しました。")
    except Exception as e:
        print(f"メール送信エラー: {e}")

if __name__ == "__main__":
    results = get_data()
    update_sheet(results)
    send_email(results)
