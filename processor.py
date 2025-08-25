import os
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import json

INTERNET_KEYWORDS = [
    "1 Gig", "500 Mbps", "200 Mbps", "100 Mbps",
    "UltraFibre 60 - Unlimited", "UltraFibre 90 - Unlimited",
    "UltraFibre 120 - Unlimited", "UltraFibre 180 - Unlimited",
    "UltraFibre 360 - Unlimited", "UltraFibre 1Gig - Unlimited",
    "UltraFibre 2Gig - Unlimited"
]
TV_KEYWORDS = [
    "Stream Box", "Family +", "Variety +", "Entertainment +", "Locals +",
    "Supreme package", "epico x-stream", "epico plus", "epico intro", "epico basic"
]
PHONE_KEYWORDS = ["Freedom", "Basic", "Landline Phone"]

def match_product(name, keywords):
    return any(k == str(name).strip() for k in keywords)

def process_findr_report(uploaded_file, sheet_url, start_date, end_date, appealer_name):
    internal_df = uploaded_file
    internal_df['Date of Sale'] = pd.to_datetime(internal_df['Date of Sale'], errors='coerce')
    internal_df = internal_df[
        (internal_df['Date of Sale'] >= pd.to_datetime(start_date)) &
        (internal_df['Date of Sale'] <= pd.to_datetime(end_date))
    ]
    internal_df['Account Number'] = internal_df['Account Number'].astype(str).str.strip()

    internal_df['Internet'] = internal_df['Product Name'].apply(lambda x: int(match_product(x, INTERNET_KEYWORDS)))
    internal_df['TV'] = internal_df['Product Name'].apply(lambda x: int(match_product(x, TV_KEYWORDS)))
    internal_df['Phone'] = internal_df['Product Name'].apply(lambda x: int(match_product(x, PHONE_KEYWORDS)))

    summarized = internal_df.groupby('Account Number')[['Internet', 'TV', 'Phone']].max().reset_index()

    creds = Credentials.from_service_account_info(
    json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]),
    scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    )
    
    sheet = gspread.authorize(creds).open_by_url(sheet_url)
    worksheet = sheet.worksheet("Merged PSUReport")
    rows = worksheet.get_all_values()
    headers = rows[0]
    psu_df = pd.DataFrame(rows[1:], columns=headers)
    psu_df.columns = [col.strip() for col in psu_df.columns]
    psu_df['Account Number'] = psu_df['Account Number'].astype(str).str.strip()
    psu_df['Date of Sale'] = pd.to_datetime(psu_df['Date of Sale'], errors='coerce')
    for col in ['Internet', 'TV', 'Phone']:
        psu_df[col] = psu_df[col].apply(lambda x: 1 if str(x).strip() else 0)
    psu_df = psu_df.set_index("Account Number")

    mismatches = []

    for idx, row in summarized.iterrows():
        acct = row['Account Number']
        if acct.startswith("833"):
            continue

        if acct not in psu_df.index:
            mismatches.append({
                'Account Number': acct,
                'Reason': 'Missing from report',
                'Internet_YESA': row['Internet'],
                'TV_YESA': row['TV'],
                'Phone_YESA': row['Phone'],
                'Client Account': acct,
                'Internet_Client': "",
                'TV_Client': "",
                'Phone_Client': "",
                'Date': ""
            })
            continue

        psu_rows = psu_df.loc[[acct]] if acct in psu_df.index else pd.DataFrame()
        psu_rows_in_range = psu_rows[
            psu_rows['Date of Sale'].notna() &
            (psu_rows['Date of Sale'].dt.date >= start_date) &
            (psu_rows['Date of Sale'].dt.date <= end_date)
        ]

        reason = None
        psu = None
        if not psu_rows_in_range.empty:
            combined = psu_rows_in_range[['Internet', 'TV', 'Phone']].max()
            if not (
                combined['Internet'] == row['Internet'] and
                combined['TV'] == row['TV'] and
                combined['Phone'] == row['Phone']
            ):
                reason = "PSU - no match"
                psu = psu_rows_in_range.iloc[0]
        else:
            reason = "Wrong date"
            psu = psu_rows.iloc[0] if not psu_rows.empty else None

        if reason and psu is not None:
            mismatches.append({
                'Account Number': acct,
                'Reason': reason,
                'Internet_YESA': row['Internet'],
                'TV_YESA': row['TV'],
                'Phone_YESA': row['Phone'],
                'Client Account': acct,
                'Internet_Client': psu['Internet'],
                'TV_Client': psu['TV'],
                'Phone_Client': psu['Phone'],
                'Date': psu['Date of Sale']
            })

    result_df = pd.DataFrame(mismatches)
    return result_df, internal_df
