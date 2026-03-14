import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
from enum import Enum
import json


class RiskLevel(Enum):
    """Risk levels for cash flow forecast"""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class IncomeCategory(Enum):
    """Categories for income sources"""
    SALARY = "salary"
    INVESTMENTS = "investments"
    FREELANCE = "freelance"
    BUSINESS = "business"
    RENTAL = "rental"
    OTHER = "other"


@dataclass
class Transaction:
    """Represents a one-time transaction"""
    month: int
    amount: float
    description: str
    category: Optional[str] = None


@dataclass
class RecurringIncome:
    """Represents recurring income with category"""
    amount: float
    category: IncomeCategory
    start_month: int = 0
    end_month: Optional[int] = None


@dataclass
class CashFlowInput:
    """Input parameters for cash flow prediction"""
    current_balance: float
    recurring_income: List[RecurringIncome]
    monthly_expenses: Dict[str, float]
    one_time_expenses: List[Transaction]
    one_time_income: List[Transaction]
    prediction_months: int
    warning_threshold: float
    critical_threshold: Optional[float] = None
    savings_goal: Optional[float] = None
    expense_growth_rate: float = 0.0
    income_growth_rate: float = 0.0
    emergency_fund_target: Optional[float] = None


@dataclass
class MonthlyPrediction:
    """Prediction for a single month"""
    month: int
    date: str
    opening_balance: float
    income: float
    expenses: float
    closing_balance: float
    net_flow: float
    income_breakdown: Dict[str, float]
    expense_breakdown: Dict[str, float]
    warnings: List[str]
    risk_level: RiskLevel


@dataclass
class ForecastSummary:
    """Summary statistics for the forecast period"""
    initial_balance: float
    final_balance: float
    total_change: float
    total_income: float
    total_expenses: float
    total_net_flow: float
    average_monthly_balance: float
    median_monthly_balance: float
    lowest_balance: float
    lowest_balance_month: str
    highest_balance: float
    highest_balance_month: str
    months_below_threshold: int
    months_negative: int
    is_sustainable: bool
    overall_risk_level: RiskLevel
    savings_rate: float
    emergency_fund_months: float
    income_by_category: Dict[str, float]
    volatility_score: float


class CashFlowPredictor:
    """
    Advanced cash flow predictor with features suitable for backend integration.
    
    Backend-ready features:
    - JSON serializable outputs for API responses
    - Risk assessment and scoring
    - Income source tracking and categorization
    - Volatility analysis
    - Emergency fund calculation
    - Savings rate tracking
    - Trend detection
    - Scenario comparison support
    - Time-series data for charts
    - Export to various formats
    """
    
    def __init__(self, inputs: CashFlowInput):
        self.inputs = inputs
        self.predictions: List[MonthlyPrediction] = []
        
        # Set critical threshold default if not provided
        if inputs.critical_threshold is None:
            self.inputs.critical_threshold = inputs.warning_threshold * 0.5
    
    def calculate_monthly_expense(self, month: int) -> Tuple[float, Dict[str, float]]:
        """Calculate total monthly expenses with growth rate applied"""
        expense_breakdown = {}
        years = month / 12
        
        for category, amount in self.inputs.monthly_expenses.items():
            inflated_amount = amount * ((1 + self.inputs.expense_growth_rate) ** years)
            expense_breakdown[category] = inflated_amount
        
        total = sum(expense_breakdown.values())
        return total, expense_breakdown
    
    def calculate_monthly_income(self, month: int) -> Tuple[float, Dict[str, float]]:
        """Calculate monthly income with growth rate applied and category breakdown"""
        income_breakdown = {}
        years = month / 12
        
        for income in self.inputs.recurring_income:
            # Check if income is active this month
            if income.start_month <= month:
                if income.end_month is None or month <= income.end_month:
                    adjusted_amount = income.amount * ((1 + self.inputs.income_growth_rate) ** years)
                    category_name = income.category.value
                    
                    if category_name in income_breakdown:
                        income_breakdown[category_name] += adjusted_amount
                    else:
                        income_breakdown[category_name] = adjusted_amount
        
        total = sum(income_breakdown.values())
        return total, income_breakdown
    
    def get_one_time_transactions(self, month: int) -> Tuple[float, float]:
        """Get one-time income and expenses for a specific month"""
        income = sum(t.amount for t in self.inputs.one_time_income if t.month == month)
        expenses = sum(t.amount for t in self.inputs.one_time_expenses if t.month == month)
        return income, expenses
    
    def calculate_risk_level(self, balance: float, net_flow: float, month: int) -> RiskLevel:
        """Calculate risk level based on balance and trends"""
        if balance < 0:
            return RiskLevel.CRITICAL
        elif balance < self.inputs.critical_threshold:
            return RiskLevel.HIGH
        elif balance < self.inputs.warning_threshold:
            return RiskLevel.MODERATE
        elif net_flow < 0 and month > 0:
            return RiskLevel.MODERATE
        else:
            return RiskLevel.LOW
    
    def predict(self) -> List[MonthlyPrediction]:
        """Generate cash flow predictions for the specified period"""
        balance = self.inputs.current_balance
        start_date = datetime.now()
        
        for month in range(self.inputs.prediction_months + 1):
            warnings = []
            month_date = start_date + timedelta(days=30 * month)
            
            if month == 0:
                # Current month - no transactions
                prediction = MonthlyPrediction(
                    month=month,
                    date=month_date.strftime("%b %Y"),
                    opening_balance=balance,
                    income=0,
                    expenses=0,
                    closing_balance=balance,
                    net_flow=0,
                    income_breakdown={},
                    expense_breakdown={},
                    warnings=[],
                    risk_level=self.calculate_risk_level(balance, 0, month)
                )
            else:
                # Calculate income and expenses
                recurring_income, income_breakdown = self.calculate_monthly_income(month)
                monthly_expense, expense_breakdown = self.calculate_monthly_expense(month)
                one_time_income, one_time_expense = self.get_one_time_transactions(month)
                
                # Add one-time transactions to breakdown
                if one_time_income > 0:
                    income_breakdown['one_time'] = one_time_income
                if one_time_expense > 0:
                    expense_breakdown['one_time'] = one_time_expense
                
                total_income = recurring_income + one_time_income
                total_expenses = monthly_expense + one_time_expense
                net_flow = total_income - total_expenses
                
                opening_balance = balance
                balance += net_flow
                
                # Generate warnings
                if balance < 0:
                    warnings.append(
                        f"🚨 CRITICAL: Negative balance! Overdraft of ${abs(balance):,.2f}"
                    )
                elif balance < self.inputs.critical_threshold:
                    warnings.append(
                        f"🚨 HIGH RISK: Balance (${balance:,.2f}) critically low"
                    )
                elif balance < self.inputs.warning_threshold:
                    warnings.append(
                        f"⚠️  WARNING: Balance (${balance:,.2f}) below threshold (${self.inputs.warning_threshold:,.2f})"
                    )
                
                if self.inputs.savings_goal and balance < self.inputs.savings_goal:
                    shortfall = self.inputs.savings_goal - balance
                    warnings.append(
                        f"📊 ${shortfall:,.2f} short of savings goal"
                    )
                
                if net_flow < 0:
                    warnings.append(
                        f"📉 Spending exceeds income by ${abs(net_flow):,.2f}"
                    )
                
                if self.inputs.emergency_fund_target:
                    if balance < self.inputs.emergency_fund_target:
                        warnings.append(
                            f"🏦 Below emergency fund target by ${self.inputs.emergency_fund_target - balance:,.2f}"
                        )
                
                risk_level = self.calculate_risk_level(balance, net_flow, month)
                
                prediction = MonthlyPrediction(
                    month=month,
                    date=month_date.strftime("%b %Y"),
                    opening_balance=opening_balance,
                    income=total_income,
                    expenses=total_expenses,
                    closing_balance=balance,
                    net_flow=net_flow,
                    income_breakdown=income_breakdown,
                    expense_breakdown=expense_breakdown,
                    warnings=warnings,
                    risk_level=risk_level
                )
            
            self.predictions.append(prediction)
        
        return self.predictions
    
    def get_summary(self) -> ForecastSummary:
        """Generate comprehensive summary statistics"""
        if not self.predictions:
            self.predict()
        
        final_prediction = self.predictions[-1]
        balances = [p.closing_balance for p in self.predictions]
        total_income = sum(p.income for p in self.predictions)
        total_expenses = sum(p.expenses for p in self.predictions)
        
        # Calculate income by category
        income_by_category = {}
        for pred in self.predictions:
            for category, amount in pred.income_breakdown.items():
                if category in income_by_category:
                    income_by_category[category] += amount
                else:
                    income_by_category[category] = amount
        
        # Calculate risk metrics
        months_below_threshold = sum(
            1 for p in self.predictions 
            if p.closing_balance < self.inputs.warning_threshold
        )
        
        months_negative = sum(1 for p in self.predictions if p.closing_balance < 0)
        
        # Overall risk level
        risk_counts = {level: 0 for level in RiskLevel}
        for p in self.predictions:
            risk_counts[p.risk_level] += 1
        
        if risk_counts[RiskLevel.CRITICAL] > 0:
            overall_risk = RiskLevel.CRITICAL
        elif risk_counts[RiskLevel.HIGH] > 2:
            overall_risk = RiskLevel.HIGH
        elif risk_counts[RiskLevel.MODERATE] > len(self.predictions) / 2:
            overall_risk = RiskLevel.MODERATE
        else:
            overall_risk = RiskLevel.LOW
        
        # Calculate volatility
        if len(balances) > 1:
            volatility = np.std(balances) / np.mean(balances) if np.mean(balances) > 0 else 0
        else:
            volatility = 0
        
        # Savings rate
        savings_rate = ((total_income - total_expenses) / total_income * 100) if total_income > 0 else 0
        
        # Emergency fund in months
        avg_monthly_expense = total_expenses / len(self.predictions) if len(self.predictions) > 0 else 0
        emergency_fund_months = (final_prediction.closing_balance / avg_monthly_expense) if avg_monthly_expense > 0 else 0
        
        # Find extremes
        lowest_balance = min(balances)
        highest_balance = max(balances)
        lowest_pred = next(p for p in self.predictions if p.closing_balance == lowest_balance)
        highest_pred = next(p for p in self.predictions if p.closing_balance == highest_balance)
        
        return ForecastSummary(
            initial_balance=self.inputs.current_balance,
            final_balance=final_prediction.closing_balance,
            total_change=final_prediction.closing_balance - self.inputs.current_balance,
            total_income=total_income,
            total_expenses=total_expenses,
            total_net_flow=total_income - total_expenses,
            average_monthly_balance=float(np.mean(balances)),
            median_monthly_balance=float(np.median(balances)),
            lowest_balance=lowest_balance,
            lowest_balance_month=lowest_pred.date,
            highest_balance=highest_balance,
            highest_balance_month=highest_pred.date,
            months_below_threshold=months_below_threshold,
            months_negative=months_negative,
            is_sustainable=final_prediction.closing_balance > self.inputs.warning_threshold,
            overall_risk_level=overall_risk,
            savings_rate=savings_rate,
            emergency_fund_months=emergency_fund_months,
            income_by_category=income_by_category,
            volatility_score=float(volatility)
        )
    
    def get_chart_data(self) -> Dict:
        """
        Get data formatted for frontend charts
        Suitable for: Line charts, area charts, comparison charts
        """
        if not self.predictions:
            self.predict()
        
        return {
            "labels": [p.date for p in self.predictions],
            "balance": [p.closing_balance for p in self.predictions],
            "income": [p.income for p in self.predictions],
            "expenses": [p.expenses for p in self.predictions],
            "net_flow": [p.net_flow for p in self.predictions],
            "predicted_vs_actual": [
                {
                    "date": p.date,
                    "predicted": p.closing_balance,
                    "actual": None  # To be filled by backend with actual data
                }
                for p in self.predictions
            ]
        }
    
    def get_income_pie_chart_data(self) -> List[Dict]:
        """Get income breakdown for pie/donut chart"""
        summary = self.get_summary()
        
        return [
            {
                "category": category,
                "amount": amount,
                "percentage": (amount / summary.total_income * 100) if summary.total_income > 0 else 0
            }
            for category, amount in summary.income_by_category.items()
        ]
    
    def to_json(self) -> str:
        """Export complete forecast as JSON (for API responses)"""
        if not self.predictions:
            self.predict()
        
        data = {
            "summary": asdict(self.get_summary()),
            "predictions": [
                {
                    "month": p.month,
                    "date": p.date,
                    "opening_balance": p.opening_balance,
                    "income": p.income,
                    "expenses": p.expenses,
                    "closing_balance": p.closing_balance,
                    "net_flow": p.net_flow,
                    "income_breakdown": p.income_breakdown,
                    "expense_breakdown": p.expense_breakdown,
                    "warnings": p.warnings,
                    "risk_level": p.risk_level.value
                }
                for p in self.predictions
            ],
            "chart_data": self.get_chart_data(),
            "income_chart_data": self.get_income_pie_chart_data()
        }
        
        # Convert enum to string for JSON serialization
        data["summary"]["overall_risk_level"] = data["summary"]["overall_risk_level"].value
        
        return json.dumps(data, indent=2, default=str)
    
    def print_report(self):
        """Print detailed cash flow report to console"""
        if not self.predictions:
            self.predict()
        
        print("=" * 90)
        print("FORECASH - CASH FLOW PREDICTION REPORT".center(90))
        print("=" * 90)
        print()
        
        # Summary section
        summary = self.get_summary()
        print("📊 SUMMARY")
        print("-" * 90)
        print(f"Initial Balance:          ${summary.initial_balance:>12,.2f}")
        print(f"Final Balance:            ${summary.final_balance:>12,.2f}")
        print(f"Total Change:             ${summary.total_change:>12,.2f}")
        print(f"Total Income:             ${summary.total_income:>12,.2f}")
        print(f"Total Expenses:           ${summary.total_expenses:>12,.2f}")
        print(f"Savings Rate:             {summary.savings_rate:>12.1f}%")
        print(f"Average Balance:          ${summary.average_monthly_balance:>12,.2f}")
        print(f"Median Balance:           ${summary.median_monthly_balance:>12,.2f}")
        print(f"Lowest Balance:           ${summary.lowest_balance:>12,.2f} ({summary.lowest_balance_month})")
        print(f"Highest Balance:          ${summary.highest_balance:>12,.2f} ({summary.highest_balance_month})")
        print(f"Emergency Fund (months):  {summary.emergency_fund_months:>12.1f}")
        print(f"Volatility Score:         {summary.volatility_score:>12.2f}")
        print(f"Overall Risk Level:       {summary.overall_risk_level.value.upper():>12}")
        print()
        
        # Income breakdown
        print("💰 INCOME BY SOURCE")
        print("-" * 90)
        for category, amount in summary.income_by_category.items():
            percentage = (amount / summary.total_income * 100) if summary.total_income > 0 else 0
            print(f"{category.capitalize():<20} ${amount:>12,.2f}  ({percentage:>5.1f}%)")
        print()
        
        # Monthly predictions
        print("📅 MONTHLY FORECAST")
        print("-" * 90)
        print(f"{'Month':<6} {'Date':<10} {'Opening':<12} {'Income':<12} {'Expenses':<12} {'Closing':<12} {'Risk':<10}")
        print("-" * 90)
        
        for p in self.predictions:
            risk_emoji = {"low": "🟢", "moderate": "🟡", "high": "🟠", "critical": "🔴"}
            print(f"{p.month:<6} {p.date:<10} ${p.opening_balance:>10,.0f} "
                  f"${p.income:>10,.0f} ${p.expenses:>10,.0f} "
                  f"${p.closing_balance:>10,.0f} {risk_emoji[p.risk_level.value]} {p.risk_level.value:<8}")
            
            for warning in p.warnings:
                print(f"       {warning}")
        
        print()
        print("=" * 90)
        
        # Risk assessment
        if summary.overall_risk_level == RiskLevel.LOW:
            print("✅ Your cash flow appears healthy and sustainable.")
        elif summary.overall_risk_level == RiskLevel.MODERATE:
            print("⚠️  Your cash flow shows moderate risk. Monitor closely.")
        elif summary.overall_risk_level == RiskLevel.HIGH:
            print("🟠 HIGH RISK: Your cash flow needs immediate attention!")
        else:
            print("🔴 CRITICAL: Severe cash flow issues detected! Take action now!")
        
        print("=" * 90)


# Example usage
if __name__ == "__main__":
    # Define inputs
    inputs = CashFlowInput(
        current_balance=5000.00,
        recurring_income=[
            RecurringIncome(amount=3000.00, category=IncomeCategory.SALARY),
            RecurringIncome(amount=500.00, category=IncomeCategory.FREELANCE),
            RecurringIncome(amount=200.00, category=IncomeCategory.INVESTMENTS),
        ],
        monthly_expenses={
            'rent': 1200.00,
            'utilities': 200.00,
            'groceries': 400.00,
            'transport': 150.00,
            'entertainment': 300.00,
            'insurance': 150.00,
            'subscriptions': 50.00,
            'other': 200.00
        },
        one_time_expenses=[
            Transaction(month=2, amount=800.00, description="Car repair", category="vehicle"),
            Transaction(month=5, amount=1500.00, description="Vacation", category="travel"),
            Transaction(month=8, amount=600.00, description="Electronics", category="shopping"),
        ],
        one_time_income=[
            Transaction(month=3, amount=2000.00, description="Tax refund", category="tax"),
            Transaction(month=6, amount=1000.00, description="Bonus", category="bonus"),
        ],
        prediction_months=12,
        warning_threshold=2000.00,
        critical_threshold=500.00,
        savings_goal=10000.00,
        expense_growth_rate=0.03,  # 3% annual inflation
        income_growth_rate=0.05,   # 5% annual raise
        emergency_fund_target=7500.00  # 3 months of expenses
    )
    
    # Create predictor and generate report
    predictor = CashFlowPredictor(inputs)
    predictor.predict()
    predictor.print_report()
    
    # Get JSON output (suitable for API)
    print("\n\n📤 JSON OUTPUT FOR API:")
    print("=" * 90)
    json_output = predictor.to_json()
    # Print first 1000 characters
    print(json_output[:1000] + "...")
    print(f"\n[Total JSON length: {len(json_output)} characters]")