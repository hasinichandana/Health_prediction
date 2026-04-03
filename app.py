import bcrypt
from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
import joblib
import sqlite3
from functools import wraps
from flask import send_file
import os

API_KEY = os.getenv("OPENROUTER_API_KEY")
# ----------------------
# APP CONFIG
# ----------------------
app = Flask(__name__)
app.secret_key = "supersecretkey"


# ----------------------
# DATABASE
# ----------------------
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password BLOB NOT NULL,
        role TEXT DEFAULT 'patient'
    )
""")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            disease TEXT,
            result TEXT,
            probability REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


init_db()


# ----------------------
# LOAD MODELS
# ----------------------
diabetes_model = joblib.load("models/diabetes_model.pkl")
heart_model = joblib.load("models/heart_model.pkl")


# ----------------------
# LOGIN REQUIRED DECORATOR
# ----------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "username" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


# ----------------------
# DASHBOARD
# ----------------------
@app.route("/")
@login_required
def home():
    conn = get_db()

    total = conn.execute(
        "SELECT COUNT(*) FROM history WHERE username=?",
        (session["username"],)
    ).fetchone()[0]

    avg = conn.execute(
        "SELECT AVG(probability) FROM history WHERE username=?",
        (session["username"],)
    ).fetchone()[0]

    high = conn.execute(
        "SELECT COUNT(*) FROM history WHERE username=? AND probability >= 70",
        (session["username"],)
    ).fetchone()[0]

    conn.close()

    avg = round(avg, 2) if avg else 0

    return render_template("dashboard.html",
                           total=total,
                           avg=avg,
                           high=high)


# ----------------------
# HISTORY PAGE
# ----------------------
@app.route("/history")
@login_required
def history():
    conn = get_db()

    records = conn.execute("""
        SELECT result, probability, created_at
        FROM history
        WHERE username=?
        ORDER BY created_at DESC
    """, (session["username"],)).fetchall()

    conn.close()

    return render_template("history.html", history=records)


# ----------------------
# HISTORY CHART DATA
# ----------------------
@app.route("/history_data")
@login_required
def history_data():
    conn = get_db()

    records = conn.execute("""
        SELECT disease, probability, created_at
        FROM history
        WHERE username=?
        ORDER BY created_at ASC
    """, (session["username"],)).fetchall()

    conn.close()

    labels = []
    diabetes_values = []
    heart_values = []

    for r in records:
        labels.append(r["created_at"])

        if r["disease"] == "Diabetes":
            diabetes_values.append(r["probability"])
            heart_values.append(None)
        elif r["disease"] == "Heart Disease":
            heart_values.append(r["probability"])
            diabetes_values.append(None)

    return jsonify({
        "labels": labels,
        "diabetes": diabetes_values,
        "heart": heart_values
    })


# ----------------------
# REGISTER
# ----------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

        try:
            conn = get_db()
            conn.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (username, hashed_password, "patient")
            )
            conn.commit()
            conn.close()

            flash("Registration successful!")
            return redirect("/login")

        except sqlite3.IntegrityError:
            flash("Username already exists.")
            return redirect("/register")

    return render_template("register.html")


# ----------------------
# LOGIN
# ----------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()
        conn.close()

        if user and bcrypt.checkpw(password.encode(), user["password"]):
            session["username"] = username
            session["role"]=user["role"]
            return redirect("/")
        else:
            flash("Invalid credentials")
            return redirect("/login")

    return render_template("login.html")


# ----------------------
# LOGOUT
# ----------------------
@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect("/login")


# ----------------------
# PREDICT PAGE
# ----------------------
@app.route("/predict")
@login_required
def predict():
    return render_template("predict.html")


# ----------------------
# DIABETES PREDICTION
# ----------------------

@app.route("/predict_diabetes", methods=["POST"])
@login_required
def predict_diabetes():
    try:
        values = [float(x) for x in request.form.values()]
    except:
        flash("Invalid input values.")
        return redirect("/predict")

    # ✅ Basic validation
    if any(v < 0 for v in values):
        flash("Values must be positive.")
        return redirect("/predict")

    prediction = diabetes_model.predict([values])[0]
    probability = diabetes_model.predict_proba([values])[0][1] * 100

    result = "Diabetic" if prediction == 1 else "Not Diabetic"

    # ✅ Risk Level
    if probability < 40:
        risk = "Low"
    elif probability < 70:
        risk = "Medium"
    else:
        risk = "High"

    conn = get_db()
    conn.execute(
        "INSERT INTO history (username, disease, result, probability) VALUES (?, ?, ?, ?)",
        (session["username"], "Diabetes", result, round(probability, 2))
    )
    conn.commit()
    conn.close()

    return render_template("result.html",
                           disease="Diabetes",
                           result=result,
                           probability=round(probability, 2),
                           risk=risk)

# ----------------------
# HEART PREDICTION
# ----------------------
@app.route("/predict_heart", methods=["POST"])
@login_required
def predict_heart():
    try:
        values = [float(x) for x in request.form.values()]
    except:
        flash("Invalid input values.")
        return redirect("/predict")

    # ✅ Basic validation
    if any(v < 0 for v in values):
        flash("Values must be positive.")
        return redirect("/predict")

    prediction = heart_model.predict([values])[0]
    probability = heart_model.predict_proba([values])[0][1] * 100

    result = "Heart Disease Detected" if prediction == 1 else "No Heart Disease"

    # ✅ Risk Level
    if probability < 40:
        risk = "Low"
    elif probability < 70:
        risk = "Medium"
    else:
        risk = "High"

    conn = get_db()
    conn.execute(
        "INSERT INTO history (username, disease, result, probability) VALUES (?, ?, ?, ?)",
        (session["username"], "Heart Disease", result, round(probability, 2))
    )
    conn.commit()
    conn.close()

    return render_template("result.html",
                           disease="Heart Disease",
                           result=result,
                           probability=round(probability, 2),
                           risk=risk)




from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

@app.route("/download_report")
@login_required
def download_report():
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors

    conn = get_db()
    record = conn.execute("""
        SELECT disease, result, probability, created_at
        FROM history
        WHERE username=?
        ORDER BY created_at DESC LIMIT 1
    """, (session["username"],)).fetchone()
    conn.close()

    if not record:
        return "No data found"

    file_path = "report.pdf"

    doc = SimpleDocTemplate(file_path)
    styles = getSampleStyleSheet()

    elements = []

    # 🏥 Title
    elements.append(Paragraph("<b>Health AI Medical Report</b>", styles['Title']))
    elements.append(Spacer(1, 20))

    # 👤 Patient
    elements.append(Paragraph(f"<b>Patient:</b> {session['username']}", styles['Normal']))
    elements.append(Spacer(1, 10))

    # 🦠 Disease
    elements.append(Paragraph(f"<b>Disease:</b> {record['disease']}", styles['Normal']))
    elements.append(Spacer(1, 10))

    # 📊 Result
    elements.append(Paragraph(f"<b>Result:</b> {record['result']}", styles['Normal']))
    elements.append(Spacer(1, 10))

    # 📈 Probability
    elements.append(Paragraph(f"<b>Risk Probability:</b> {record['probability']}%", styles['Normal']))
    elements.append(Spacer(1, 15))

    # 🧠 Recommendation
    prob = record['probability']

    if prob < 40:
        rec = "Low risk. Maintain a healthy lifestyle."
    elif prob < 70:
        rec = "Moderate risk. Consider consulting a doctor."
    else:
        rec = "High risk. Immediate medical attention recommended."

    elements.append(Paragraph("<b>Recommendation:</b>", styles['Heading2']))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(rec, styles['Normal']))
    elements.append(Spacer(1, 20))

    # 📅 Date
    elements.append(Paragraph(f"<b>Date:</b> {record['created_at']}", styles['Normal']))

    doc.build(elements)

    return send_file(file_path, as_attachment=True)

@app.route("/admin")
@login_required
def admin():
    # Only allow admin user
    if session.get("role") != "admin":
        return "Access Denied"

    conn = get_db()

    total = conn.execute("SELECT COUNT(*) FROM history").fetchone()[0]
    users = conn.execute("SELECT username FROM users").fetchall()

    records = conn.execute("""
        SELECT username, disease, result, probability, created_at
        FROM history
        ORDER BY created_at DESC
    """).fetchall()

    conn.close()

    return render_template("admin.html",
                           total=total,
                           users=users,
                           records=records)

    
import requests

@app.route("/ask_ai", methods=["POST"])
@login_required
def ask_ai():
    question = request.form.get("question")

    if not question:
        return jsonify({"answer": "Ask something."})

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openai/gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": "You are a medical assistant. Give clear and short answers."},
                    {"role": "user", "content": question}
                ]
            }
        )
        print("KEY:", os.getenv("OPENROUTER_API_KEY"))
        data = response.json()
        print("DEBUG:", data)  # 👈 keep this

        # ✅ HANDLE ERROR PROPERLY
        if "error" in data:
            return jsonify({"answer": "API Error: " + data["error"]["message"]})

        # ✅ SAFE ACCESS
        answer = data.get("choices", [{}])[0].get("message", {}).get("content", "No response")

        return jsonify({"answer": answer})

    except Exception as e:
        return jsonify({"answer": "Error: " + str(e)})

    
@app.route("/chat")
@login_required
def chat():
    return render_template("chat.html")

# ----------------------
# RUN APP
# ----------------------
if __name__ == "__main__":
    app.run(debug=True)