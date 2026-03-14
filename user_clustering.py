import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# Spender type definitions
SPENDER_TYPES = {
    0: "Saver",
    1: "Impulsive",
    2: "Debt Heavy",
    3: "Balanced",
    4: "Responsible"
}

EXPENSE_COLS = [
    "Entertainment",
    "Foods and Drinks",
    "Health",
    "Shopping",
    "Education",
    "Savings and investments",
    "Personal care"
]

DISCRETIONARY_COLS = ["Entertainment", "Shopping", "Personal care"]
ESSENTIAL_COLS = ["Foods and Drinks", "Health"]


def preprocess(df):
    """Calculate spending ratios and derived features"""
    df["total_spend"] = df[EXPENSE_COLS].sum(axis=1)
    for col in EXPENSE_COLS:
        df[col + "_ratio"] = df[col] / df["income"]
    df["discretionary_spend"] = df[DISCRETIONARY_COLS].sum(axis=1)
    df["discretionary_ratio"] = df["discretionary_spend"] / df["income"]
    df["essential_spend"] = df[ESSENTIAL_COLS].sum(axis=1)
    df["essential_ratio"] = df["essential_spend"] / df["income"]
    df["spend_to_income_ratio"] = df["total_spend"] / df["income"]
    
    # Features for clustering
    features = [
        col + "_ratio" for col in EXPENSE_COLS
    ] + ["discretionary_ratio", "spend_to_income_ratio"]
    
    return df, features


def run_clustering(df):
    """Perform K-means clustering on spending patterns"""
    
    df, features = preprocess(df)
    
    X = df[features]
    
    # Standardize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Cluster into 5 groups
    kmeans = KMeans(n_clusters=5, random_state=42, n_init=10)
    df["cluster"] = kmeans.fit_predict(X_scaled)
    
    return df, kmeans


def map_clusters(df):
    """Map clusters to spender types based on spending behavior"""
    
    cluster_map = {}
    
    for c in df["cluster"].unique():
        cluster_data = df[df["cluster"] == c]
        
        # Calculate key metrics for this cluster
        avg_savings_ratio = cluster_data["Savings and investments_ratio"].mean()
        avg_discretionary_ratio = cluster_data["discretionary_ratio"].mean()
        avg_spend_ratio = cluster_data["spend_to_income_ratio"].mean()
        avg_education_ratio = cluster_data["Education_ratio"].mean()
        
        # Classification logic with priority order
        
        # 1. Debt Heavy: Spending more than earning
        if avg_spend_ratio > 1.05:
            cluster_map[c] = 2  # Debt Heavy
        
        # 2. Saver: High savings rate (>30% of income)
        elif avg_savings_ratio > 0.30:
            cluster_map[c] = 0  # Saver
        
        # 3. Impulsive: High discretionary spending (>35% of income) with low savings
        elif avg_discretionary_ratio > 0.35 and avg_savings_ratio < 0.15:
            cluster_map[c] = 1  # Impulsive
        
        # 4. Responsible: Good savings (15-30%), moderate discretionary spending
        elif avg_savings_ratio >= 0.15 and avg_discretionary_ratio < 0.30:
            cluster_map[c] = 4  # Responsible
        
        # 5. Balanced: Everything else - reasonable balance
        else:
            cluster_map[c] = 3  # Balanced
    
    df["spender_type"] = df["cluster"].map(cluster_map)
    df["spender_label"] = df["spender_type"].map(SPENDER_TYPES)
    
    return df


def classify_single_user(income, expenses_dict):
    """
    Classify a single user based on their income and expenses
    
    Parameters:
    - income: User's monthly/annual income
    - expenses_dict: Dictionary with expense categories as keys
    
    Returns:
    - Dictionary with classification results
    """
    
    # Create dataframe from single user data
    data = {"income": income}
    data.update(expenses_dict)
    
    df = pd.DataFrame([data])
    
    # Ensure all expense columns exist
    for col in EXPENSE_COLS:
        if col not in df.columns:
            df[col] = 0
    
    # Preprocess single user
    df, features = preprocess(df)
    
    # Classify based on spending patterns (no clustering needed for single user)
    avg_savings_ratio = df["Savings and investments_ratio"].iloc[0]
    avg_discretionary_ratio = df["discretionary_ratio"].iloc[0]
    avg_spend_ratio = df["spend_to_income_ratio"].iloc[0]
    
    # Classification logic
    if avg_spend_ratio > 1.05:
        spender_type = 2  # Debt Heavy
    elif avg_savings_ratio > 0.30:
        spender_type = 0  # Saver
    elif avg_discretionary_ratio > 0.35 and avg_savings_ratio < 0.15:
        spender_type = 1  # Impulsive
    elif avg_savings_ratio >= 0.15 and avg_discretionary_ratio < 0.30:
        spender_type = 4  # Responsible
    else:
        spender_type = 3  # Balanced
    
    df["spender_type"] = spender_type
    df["spender_label"] = SPENDER_TYPES[spender_type]
    
    # Return classification results
    result = {
        "income": income,
        "total_spend": df["total_spend"].iloc[0],
        "spend_to_income_ratio": df["spend_to_income_ratio"].iloc[0],
        "savings_ratio": df["Savings and investments_ratio"].iloc[0],
        "discretionary_ratio": df["discretionary_ratio"].iloc[0],
        "spender_type": int(df["spender_type"].iloc[0]),
        "spender_label": df["spender_label"].iloc[0]
    }
    
    return result


if __name__ == "__main__":
    
    # Test with multiple user profiles
    test_users = [
        {
            "name": "High Saver",
            "income": 50000,
            "Entertainment": 2000,
            "Foods and Drinks": 6000,
            "Health": 2000,
            "Shopping": 3000,
            "Education": 2000,
            "Savings and investments": 20000,
            "Personal care": 1500,
        },
        {
            "name": "Impulsive Spender",
            "income": 50000,
            "Entertainment": 8000,
            "Foods and Drinks": 10000,
            "Health": 2000,
            "Shopping": 12000,
            "Education": 1000,
            "Savings and investments": 5000,
            "Personal care": 4000,
        },
        {
            "name": "Debt Heavy",
            "income": 50000,
            "Entertainment": 10000,
            "Foods and Drinks": 15000,
            "Health": 5000,
            "Shopping": 15000,
            "Education": 2000,
            "Savings and investments": 2000,
            "Personal care": 5000,
        },
        {
            "name": "Balanced",
            "income": 50000,
            "Entertainment": 5000,
            "Foods and Drinks": 10000,
            "Health": 3000,
            "Shopping": 6000,
            "Education": 3000,
            "Savings and investments": 10000,
            "Personal care": 3000,
        },
        {
            "name": "Responsible",
            "income": 50000,
            "Entertainment": 3000,
            "Foods and Drinks": 8000,
            "Health": 3000,
            "Shopping": 4000,
            "Education": 4000,
            "Savings and investments": 12000,
            "Personal care": 2000,
        }
    ]
    
    print("=" * 80)
    print("USER SPENDING CLASSIFICATION RESULTS")
    print("=" * 80)
    
    for user in test_users:
        name = user.pop("name")
        income = user["income"]
        
        result = classify_single_user(income, user)
        
        print(f"\n{name}:")
        print(f"  Income: ${result['income']:,.0f}")
        print(f"  Total Spend: ${result['total_spend']:,.0f}")
        print(f"  Spend/Income Ratio: {result['spend_to_income_ratio']:.2%}")
        print(f"  Savings Ratio: {result['savings_ratio']:.2%}")
        print(f"  Discretionary Ratio: {result['discretionary_ratio']:.2%}")
        print(f"  → Classification: {result['spender_label']} (Type {result['spender_type']})")
        print("-" * 80)