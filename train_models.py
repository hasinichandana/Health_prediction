import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
import joblib
import os

# Create models folder if not exists
os.makedirs("models", exist_ok=True)

# -----------------------------
# Train Diabetes Model
# -----------------------------
diabetes = pd.read_csv("data/diabetes.csv")

X_d = diabetes.drop("Outcome", axis=1)
y_d = diabetes["Outcome"]

X_train_d, X_test_d, y_train_d, y_test_d = train_test_split(
    X_d, y_d, test_size=0.2, random_state=42
)

model_d = RandomForestClassifier()
model_d.fit(X_train_d, y_train_d)

joblib.dump(model_d, "models/diabetes_model.pkl")
print("Diabetes model trained and saved!")

# -----------------------------
# Train Heart Model
# -----------------------------
heart = pd.read_csv("data/heart.csv")

X_h = heart.drop("target", axis=1)
y_h = heart["target"]

X_train_h, X_test_h, y_train_h, y_test_h = train_test_split(
    X_h, y_h, test_size=0.2, random_state=42
)

model_h = RandomForestClassifier()
model_h.fit(X_train_h, y_train_h)

joblib.dump(model_h, "models/heart_model.pkl")
print("Heart model trained and saved!")