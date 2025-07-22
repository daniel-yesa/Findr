from flask import Flask, render_template, request, send_file, redirect
from werkzeug.utils import secure_filename
import os
import tempfile
import pandas as pd
from processor import process_findr_report

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files.get("file")
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        appealer_name = request.form.get("appealer_name")
        sheet_url = request.form.get("sheet_url")
        creds_json = request.form.get("google_creds_json")

        if not file or not start_date or not end_date or not appealer_name or not sheet_url:
            return render_template("index.html", error="Please fill in all fields.")

        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        result_df = process_findr_report(
            uploaded_file=file_path,
            sheet_url=sheet_url,
            start_date=pd.to_datetime(start_date).date(),
            end_date=pd.to_datetime(end_date).date(),
            appealer_name=appealer_name,
            google_creds_json=creds_json
        )

        result_csv_path = os.path.join(app.config['UPLOAD_FOLDER'], "mismatches.csv")
        result_df.to_csv(result_csv_path, index=False)

        return send_file(result_csv_path, as_attachment=True, download_name="Findr_Mismatches.csv")

    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
