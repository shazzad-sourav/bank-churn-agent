"""Builds the SQLite database the agent queries, and hands out read-only connections.

The derived columns mirror the Power BI project's Power Query step, so answers from the
agent match the dashboard (https://github.com/shazzad-sourav/bank-churn-powerbi).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from . import config

TABLE = "customers"

# Plain-English descriptions shown to the model by the get_schema tool.
COLUMN_NOTES: dict[str, str] = {
    "client_id": "Unique customer id (text).",
    "churned": "1 if the customer closed their card account (attrited), else 0.",
    "status": "'Churned' or 'Active'.",
    "customer_age": "Age in years.",
    "age_group": "'Under 30', '30-39', '40-49', '50-59', '60+'.",
    "gender": "'Female' or 'Male'.",
    "dependent_count": "Number of dependents.",
    "education_level": "Uneducated, High School, College, Graduate, Post-Graduate, Doctorate, Unknown.",
    "marital_status": "Married, Single, Divorced, Unknown.",
    "income_category": "'< $40K', '$40K - $60K', '$60K - $80K', '$80K - $120K', '$120K +', 'Unknown'.",
    "card_category": "Blue, Silver, Gold, Platinum.",
    "months_on_book": "Months the customer has held the card.",
    "total_relationship_count": "Number of bank products held (1-6).",
    "months_inactive_12_mon": "Months with no activity in the last 12 months (0-6).",
    "contacts_count_12_mon": "Service contacts with the bank in the last 12 months (0-6).",
    "credit_limit": "Credit limit in dollars.",
    "total_revolving_bal": "Revolving balance carried, in dollars (0 = pays in full).",
    "avg_open_to_buy": "Average unused credit, in dollars.",
    "total_amt_chng_q4_q1": "Ratio of Q4 to Q1 spend amount.",
    "total_trans_amt": "Total spend in the last 12 months, in dollars.",
    "total_trans_ct": "Number of transactions in the last 12 months.",
    "total_ct_chng_q4_q1": "Ratio of Q4 to Q1 transaction count (below 1 = activity dropping).",
    "avg_utilization_ratio": "Average share of the credit limit in use (0-1).",
    "txn_count_band": "'Under 40', '40-59', '60-79', '80+' transactions a year.",
    "carries_balance": "'Carries balance' or 'No balance'.",
    "flag_low_txn": "1 if total_trans_ct < 60.",
    "flag_activity_drop": "1 if total_ct_chng_q4_q1 < 0.6.",
    "flag_no_balance": "1 if total_revolving_bal = 0.",
    "flag_high_contacts": "1 if contacts_count_12_mon >= 4.",
    "flag_few_products": "1 if total_relationship_count <= 2.",
    "flag_inactive": "1 if months_inactive_12_mon >= 3.",
    "risk_score": "Sum of the six flags (0-6).",
    "risk_tier": "'High' (score >= 3), 'Medium' (score = 2), 'Low' (score <= 1).",
}


def _bin(value: float, edges: list[float], labels: list[str]) -> str:
    for edge, label in zip(edges, labels):
        if value < edge:
            return label
    return labels[-1]


def build_frame(csv_path: Path = config.CSV_PATH) -> pd.DataFrame:
    raw = pd.read_csv(csv_path)
    df = pd.DataFrame()
    df["client_id"] = raw["CLIENTNUM"].astype(str)
    df["churned"] = (raw["Attrition_Flag"] == "Attrited Customer").astype(int)
    df["status"] = df["churned"].map({1: "Churned", 0: "Active"})
    df["customer_age"] = raw["Customer_Age"]
    df["age_group"] = raw["Customer_Age"].apply(
        lambda a: _bin(a, [30, 40, 50, 60], ["Under 30", "30-39", "40-49", "50-59", "60+"])
    )
    df["gender"] = raw["Gender"].map({"F": "Female", "M": "Male"})
    df["dependent_count"] = raw["Dependent_count"]
    df["education_level"] = raw["Education_Level"]
    df["marital_status"] = raw["Marital_Status"]
    df["income_category"] = raw["Income_Category"].replace({"Less than $40K": "< $40K"})
    df["card_category"] = raw["Card_Category"]
    for src in [
        "Months_on_book", "Total_Relationship_Count", "Months_Inactive_12_mon",
        "Contacts_Count_12_mon", "Credit_Limit", "Total_Revolving_Bal", "Avg_Open_To_Buy",
        "Total_Amt_Chng_Q4_Q1", "Total_Trans_Amt", "Total_Trans_Ct", "Total_Ct_Chng_Q4_Q1",
        "Avg_Utilization_Ratio",
    ]:
        df[src.lower()] = raw[src]
    df["txn_count_band"] = df["total_trans_ct"].apply(
        lambda n: _bin(n, [40, 60, 80], ["Under 40", "40-59", "60-79", "80+"])
    )
    df["carries_balance"] = (df["total_revolving_bal"] == 0).map(
        {True: "No balance", False: "Carries balance"}
    )
    df["flag_low_txn"] = (df["total_trans_ct"] < 60).astype(int)
    df["flag_activity_drop"] = (df["total_ct_chng_q4_q1"] < 0.6).astype(int)
    df["flag_no_balance"] = (df["total_revolving_bal"] == 0).astype(int)
    df["flag_high_contacts"] = (df["contacts_count_12_mon"] >= 4).astype(int)
    df["flag_few_products"] = (df["total_relationship_count"] <= 2).astype(int)
    df["flag_inactive"] = (df["months_inactive_12_mon"] >= 3).astype(int)
    flags = [c for c in df.columns if c.startswith("flag_")]
    df["risk_score"] = df[flags].sum(axis=1)
    df["risk_tier"] = df["risk_score"].apply(
        lambda s: "High" if s >= 3 else ("Medium" if s == 2 else "Low")
    )
    return df


def build_database(csv_path: Path = config.CSV_PATH, db_path: Path = config.DB_PATH) -> Path:
    """(Re)create the SQLite file from the CSV. Safe to run repeatedly."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    df = build_frame(csv_path)
    with sqlite3.connect(db_path) as con:
        df.to_sql(TABLE, con, if_exists="replace", index=False)
        con.execute(f"CREATE INDEX IF NOT EXISTS ix_tier ON {TABLE}(risk_tier)")
    return db_path


def ensure_database(db_path: Path = config.DB_PATH) -> Path:
    if not db_path.exists():
        build_database(db_path=db_path)
    return db_path


def read_only_connection(db_path: Path = config.DB_PATH) -> sqlite3.Connection:
    """Open the database read-only at the SQLite level (mode=ro), whatever SQL is sent."""
    ensure_database(db_path)
    con = sqlite3.connect(f"{Path(db_path).resolve().as_uri()}?mode=ro", uri=True)
    con.execute("PRAGMA query_only = ON")
    return con


if __name__ == "__main__":
    path = build_database()
    print(f"Built {path}")
