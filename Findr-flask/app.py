from flask import Flask, render_template, request
import pandas as pd
from datetime import datetime
import os
import json
import gspread
from google.oauth2.service_account import Credentials

from processor import process_findr_report

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            file = request.files["csv_file"]
            gs_url = request.form["sheet_url"]
            date_range = request.form["date_range"]
            appealer_name = request.form["appealer_name"]

            start_date_str, end_date_str = date_range.split(" - ")
            start_date = datetime.strptime(start_date_str.strip(), "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str.strip(), "%Y-%m-%d").date()

            df_uploaded = pd.read_csv(file)
            mismatches, internal_df = process_findr_report(df_uploaded, gs_url, start_date, end_date)

            # Filter out "Wrong date" from open appeals
            filtered = mismatches[mismatches["Reason"] != "Wrong date"]
            merged = pd.merge(filtered, internal_df, on="Account Number", how="left")

            today = datetime.today().strftime("%m/%d/%Y")

            def format_address(row):
                addr = row.get("Customer Address", "")
                addr2 = row.get("Customer Address Line 2", "")
                return f"{addr}, {addr2}" if pd.notna(addr2) and addr2.strip() else addr

            def install_type(val):
                return "Self Install" if str(val).strip().lower() == "yes" else "Tech Visit"

            def map_reason(reason):
                if reason == "Missing from report":
                    return "Account missing from report"
                elif reason == "PSU - no match":
                    return "PSUs don't match report"
                return ""

            appeals_df = pd.DataFrame({
                "Type of Appeal": ["Open"] * len(merged),
                "Name of Appealer": [appealer_name] * len(merged),
                "Date of Appeal": [today] * len(merged),
                "Account number": merged["Account Number"],
                "Customer Address": merged.apply(format_address, axis=1),
                "City": merged["City"],
                "Date Of Sale": pd.to_datetime(merged["Date of Sale"]).dt.strftime("%m/%d/%Y"),
                "Sales Rep": merged["Sale Rep"],
                "Rep ID": merged["Rep Id"],
                "Install Type": merged["Self Install"].apply(install_type),
                "Installation Date": pd.to_datetime(merged["Scheduled Install Date"]).dt.strftime("%m/%d/%Y"),
                "Internet": merged["Internet_YESA"].apply(lambda x: 1 if x == 1 else ""),
                "TV": merged["TV_YESA"].apply(lambda x: 1 if x == 1 else ""),
                "Phone": merged["Phone_YESA"].apply(lambda x: 1 if x == 1 else ""),
                "Products": (
                    merged["Internet_YESA"].apply(lambda x: 1 if x == 1 else 0) +
                    merged["TV_YESA"].apply(lambda x: 1 if x == 1 else 0) +
                    merged["Phone_YESA"].apply(lambda x: 1 if x == 1 else 0)
                ),
                "Reason for Appeal": merged["Reason"].apply(map_reason)
            })

            ontario_df = appeals_df[appeals_df["Account number"].str.startswith("500")].copy()
            quebec_df = appeals_df[appeals_df["Account number"].str.startswith("960")].copy()

            return render_template(
                "index.html",
                mismatches=mismatches.to_dict(orient="records"),
                ontario=ontario_df.to_dict(orient="records"),
                quebec=quebec_df.to_dict(orient="records"),
                appealer_name=appealer_name
            )
        except Exception as e:
            return f"<h3 style='color: red;'>Error: {str(e)}</h3>"

    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
