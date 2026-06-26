"""
Train a LightGBM 5-class classifier on NSL-KDD for network anomaly detection.

Classes: Normal | DoS | Probe | R2L | U2R

Split strategy:
  KDDTrain+  → 80% train / 20% validation  (stratified)
  KDDTest+   → held-out test set           (never seen during training)

Outputs (written to ./artifacts/):
  model.pkl          — LGBMClassifier loaded by FastAPI backend
  model.joblib       — same model, loaded by KServe sklearn server
  encoders.pkl       — LabelEncoders for categorical features
  feature_names.json
  class_names.json   — ordered list of 5 class labels
  metrics.json       — overall + per-class metrics on KDDTest+
  attack_family.json — specific attack name → family mapping
"""

import io
import json
import os

import joblib
import lightgbm as lgb
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
import requests
from lightgbm import LGBMClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

# Local dev: writes to ./mlruns (no server needed).
# In cluster: export MLFLOW_TRACKING_URI=http://mlflow.cluster.lan
MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "file://" + os.path.join(os.path.dirname(__file__), "mlruns"))
EXPERIMENT = "netguard-nsl-kdd"

TRAIN_URL = "https://raw.githubusercontent.com/defcom17/NSL_KDD/master/KDDTrain+.txt"
TEST_URL  = "https://raw.githubusercontent.com/defcom17/NSL_KDD/master/KDDTest+.txt"

COLUMNS = [
    "duration", "protocol_type", "service", "flag",
    "src_bytes", "dst_bytes", "land", "wrong_fragment", "urgent",
    "hot", "num_failed_logins", "logged_in", "num_compromised",
    "root_shell", "su_attempted", "num_root", "num_file_creations",
    "num_shells", "num_access_files", "num_outbound_cmds",
    "is_host_login", "is_guest_login", "count", "srv_count",
    "serror_rate", "srv_serror_rate", "rerror_rate", "srv_rerror_rate",
    "same_srv_rate", "diff_srv_rate", "srv_diff_host_rate",
    "dst_host_count", "dst_host_srv_count", "dst_host_same_srv_rate",
    "dst_host_diff_srv_rate", "dst_host_same_src_port_rate",
    "dst_host_srv_diff_host_rate", "dst_host_serror_rate",
    "dst_host_srv_serror_rate", "dst_host_rerror_rate",
    "dst_host_srv_rerror_rate", "label", "difficulty",
]

CATEGORICAL = ["protocol_type", "service", "flag"]

ATTACK_FAMILY: dict[str, str] = {
    "normal": "Normal",
    # DoS
    "neptune": "DoS", "smurf": "DoS", "pod": "DoS", "teardrop": "DoS",
    "land": "DoS", "back": "DoS", "udpstorm": "DoS", "processtable": "DoS",
    "mailbomb": "DoS", "apache2": "DoS", "worm": "DoS",
    # Probe
    "portsweep": "Probe", "ipsweep": "Probe", "nmap": "Probe", "satan": "Probe",
    "mscan": "Probe", "saint": "Probe",
    # R2L
    "ftp_write": "R2L", "guess_passwd": "R2L", "imap": "R2L", "multihop": "R2L",
    "phf": "R2L", "spy": "R2L", "warezclient": "R2L", "warezmaster": "R2L",
    "snmpgetattack": "R2L", "named": "R2L", "xlock": "R2L", "xsnoop": "R2L",
    "sendmail": "R2L", "httptunnel": "R2L",
    # U2R
    "buffer_overflow": "U2R", "loadmodule": "U2R", "perl": "U2R",
    "rootkit": "U2R", "xterm": "U2R", "ps": "U2R", "sqlattack": "U2R",
}

CLASS_NAMES = ["Normal", "DoS", "Probe", "R2L", "U2R"]
CLASS_MAP   = {name: i for i, name in enumerate(CLASS_NAMES)}


def load_dataset(url: str) -> pd.DataFrame:
    print(f"Downloading {url} ...")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text), header=None, names=COLUMNS)
    df.drop(columns=["difficulty"], inplace=True)
    return df


def label_to_class(label: str) -> int:
    family = ATTACK_FAMILY.get(label.strip().lower(), "U2R")
    return CLASS_MAP[family]


def encode(df: pd.DataFrame, encoders: dict | None = None, fit: bool = True):
    df = df.copy()
    if encoders is None:
        encoders = {}
    for col in CATEGORICAL:
        if fit:
            le = LabelEncoder()
            df[col] = le.fit_transform(df[col].astype(str))
            encoders[col] = le
        else:
            le = encoders[col]
            df[col] = df[col].astype(str).map(
                lambda x, le=le: le.transform([x])[0] if x in le.classes_ else -1
            )
    return df, encoders


def main():
    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment(EXPERIMENT)

    # ── Load ────────────────────────────────────────────────────────
    train_raw = load_dataset(TRAIN_URL)
    test_raw  = load_dataset(TEST_URL)

    train_raw["class_label"] = train_raw["label"].map(label_to_class)
    test_raw["class_label"]  = test_raw["label"].map(label_to_class)

    with open(os.path.join(ARTIFACTS_DIR, "attack_family.json"), "w") as f:
        json.dump(ATTACK_FAMILY, f)

    # ── Encode ──────────────────────────────────────────────────────
    train_raw, encoders = encode(train_raw, fit=True)
    test_raw,  _        = encode(test_raw, encoders=encoders, fit=False)

    feature_names = [c for c in COLUMNS if c not in ("label", "difficulty")]

    X_all  = train_raw[feature_names].values
    y_all  = train_raw["class_label"].values
    X_test = test_raw[feature_names].values
    y_test = test_raw["class_label"].values

    # 80/20 stratified split of KDDTrain+ → train + validation
    X_train, X_val, y_train, y_val = train_test_split(
        X_all, y_all, test_size=0.20, random_state=42, stratify=y_all
    )

    print(f"Train: {len(X_train)}  Val: {len(X_val)}  Test: {len(X_test)}")

    # ── Train ────────────────────────────────────────────────────────
    params = {
        "n_estimators":  400,
        "learning_rate": 0.05,
        "max_depth":     8,
        "num_leaves":    63,
        "class_weight":  "balanced",
        "random_state":  42,
        "n_jobs":        -1,
        "verbose":       -1,
    }

    with mlflow.start_run(run_name="lgbm-5class"):
        mlflow.log_params(params)
        mlflow.log_param("dataset", "NSL-KDD KDDTrain+ / KDDTest+")
        mlflow.log_param("num_classes", 5)
        mlflow.log_param("class_names", CLASS_NAMES)
        mlflow.log_param("train_samples", len(X_train))
        mlflow.log_param("val_samples",   len(X_val))
        mlflow.log_param("test_samples",  len(X_test))

        print("\nTraining LightGBM 5-class ...")
        clf = LGBMClassifier(**params)
        clf.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[
                lgb.early_stopping(stopping_rounds=50, verbose=False),
                lgb.log_evaluation(period=100),
            ],
        )

        # Validation metrics
        y_val_pred = clf.predict(X_val)
        mlflow.log_metric("val_accuracy", round(accuracy_score(y_val, y_val_pred), 4))
        mlflow.log_metric("val_f1_macro", round(f1_score(y_val, y_val_pred, average="macro"), 4))

        # Test metrics
        y_pred = clf.predict(X_test)
        report = classification_report(
            y_test, y_pred, target_names=CLASS_NAMES, output_dict=True
        )

        overall = {
            "accuracy":    round(accuracy_score(y_test, y_pred), 4),
            "f1_macro":    round(f1_score(y_test, y_pred, average="macro"), 4),
            "f1_weighted": round(f1_score(y_test, y_pred, average="weighted"), 4),
        }
        per_class = {
            cls: {
                "precision": round(report[cls]["precision"], 4),
                "recall":    round(report[cls]["recall"],    4),
                "f1":        round(report[cls]["f1-score"],  4),
                "support":   int(report[cls]["support"]),
            }
            for cls in CLASS_NAMES
        }
        metrics = {"overall": overall, "per_class": per_class}

        for k, v in overall.items():
            mlflow.log_metric(f"test_{k}", v)
        for cls, m in per_class.items():
            mlflow.log_metric(f"test_f1_{cls}",     m["f1"])
            mlflow.log_metric(f"test_recall_{cls}", m["recall"])

        print("\n=== Test Metrics ===")
        for k, v in overall.items():
            print(f"  {k}: {v}")
        print()
        print(classification_report(y_test, y_pred, target_names=CLASS_NAMES))

        # ── Save artifacts ──────────────────────────────────────────
        joblib.dump(clf,      os.path.join(ARTIFACTS_DIR, "model.pkl"))
        joblib.dump(clf,      os.path.join(ARTIFACTS_DIR, "model.joblib"))  # KServe
        joblib.dump(encoders, os.path.join(ARTIFACTS_DIR, "encoders.pkl"))

        with open(os.path.join(ARTIFACTS_DIR, "feature_names.json"), "w") as f:
            json.dump(feature_names, f)
        with open(os.path.join(ARTIFACTS_DIR, "class_names.json"), "w") as f:
            json.dump(CLASS_NAMES, f)
        with open(os.path.join(ARTIFACTS_DIR, "metrics.json"), "w") as f:
            json.dump(metrics, f, indent=2)

        # Log model + all artifacts to MLflow
        mlflow.sklearn.log_model(
            clf,
            artifact_path="model",
            registered_model_name="netguard-lgbm",
        )
        mlflow.log_artifacts(ARTIFACTS_DIR, artifact_path="artifacts")

        run_id = mlflow.active_run().info.run_id
        print(f"\nArtifacts saved to {ARTIFACTS_DIR}/")
        print(f"MLflow run ID: {run_id}")
        print(f"MLflow UI: {MLFLOW_URI}/#/experiments/{EXPERIMENT}")


if __name__ == "__main__":
    main()
