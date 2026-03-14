from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from groq import Groq
from dotenv import dotenv_values
import json
import os
from datetime import datetime, timedelta
import uvicorn
from contextlib import asynccontextmanager
import shutil

# Import integrated modules
from ai_tax_assistant import AITaxAssistant
from cash_flowpred import CashFlowPredictor, CashFlowInput, RecurringIncome, Transaction, IncomeCategory
from user_clustering import classify_single_user

# Pydantic Models
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    user_id: str = Field(..., min_length=1)

class ChatResponse(BaseModel):
    response: str
    timestamp: str
    conversation_id: Optional[str] = None

class ConversationHistory(BaseModel):
    messages: List[Message]
    total_messages: int

class BankDataResponse(BaseModel):
    user_profile: Dict[str, Any]
    summary: Dict[str, Any]

# New Pydantic Models for integrated features
class ForecastRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    prediction_months: int = Field(default=6, ge=1, le=24)
    warning_threshold: Optional[float] = Field(default=5000.0)
    expense_growth_rate: Optional[float] = Field(default=0.0)
    income_growth_rate: Optional[float] = Field(default=0.0)

class ForecastResponse(BaseModel):
    monthly_predictions: List[Dict[str, Any]]
    summary: Dict[str, Any]
    chart_data: Dict[str, Any]

class SpendingClassificationRequest(BaseModel):
    income: float = Field(..., gt=0)
    expenses: Dict[str, float]

class SpendingClassificationResponse(BaseModel):
    income: float
    total_spend: float
    spend_to_income_ratio: float
    savings_ratio: float
    discretionary_ratio: float
    spender_type: int
    spender_label: str

class TaxDocumentResponse(BaseModel):
    doc_id: int
    filename: str
    doc_type: str
    upload_date: str
    text_preview: Optional[str] = None

class TaxAnalysisResponse(BaseModel):
    analysis_id: int
    user_id: str
    analysis_date: str
    analysis_text: str
    recommendations: List[str]

class UserProfileResponse(BaseModel):
    user_profile: Dict[str, Any]
    bank_summary: Dict[str, Any]
    spending_classification: Optional[Dict[str, Any]] = None

# Security
security = HTTPBearer()

class BankChatbotService:
    def __init__(self):
        self.config = dotenv_values(".env")
        self.api_key = self.config.get("GROQ_API")
        if not self.api_key:
            raise ValueError("GROQ_API key not found in .env file")
        self.client = Groq(api_key=self.api_key)
        self.data_dir = "user_data"
        os.makedirs(self.data_dir, exist_ok=True)
    
    def get_user_data_path(self, user_id: str) -> tuple:
        """Get file paths for user's bank data and conversation history"""
        user_folder = os.path.join(self.data_dir, user_id)
        os.makedirs(user_folder, exist_ok=True)
        bank_data_path = os.path.join(user_folder, "bank_data.json")
        history_path = os.path.join(user_folder, "conversation_history.json")
        return bank_data_path, history_path
    
    def load_bank_data(self, user_id: str) -> Optional[Dict]:
        """Load user's bank data from JSON file"""
        bank_data_path, _ = self.get_user_data_path(user_id)
        try:
            with open(bank_data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise HTTPException(
                status_code=404,
                detail=f"Bank data not found for user {user_id}"
            )
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=500,
                detail="Invalid bank data format"
            )
    
    def load_conversation_history(self, user_id: str) -> List[Dict]:
        """Load conversation history"""
        _, history_path = self.get_user_data_path(user_id)
        try:
            with open(history_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return []
        except json.JSONDecodeError:
            return []
    
    def save_conversation_history(self, user_id: str, history: List[Dict]):
        """Save conversation history"""
        _, history_path = self.get_user_data_path(user_id)
        with open(history_path, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=4, ensure_ascii=False)
    
    def prepare_context(self, bank_data: Dict) -> str:
        """Prepare bank data context for the AI"""
        context = f"""
=== USER FINANCIAL PROFILE ===
Name: {bank_data['user_profile']['name']}
Current Balance: ₹{bank_data['user_profile']['current_balance']:,.2f}
Available Balance: ₹{bank_data['user_profile']['available_balance']:,.2f}
Monthly Salary: ₹{bank_data['user_profile']['monthly_salary']:,.2f}
Credit Score: {bank_data['user_profile']['credit_score']}
Risk Profile: {bank_data['user_profile']['risk_profile']}

=== ACTIVE LOANS ===
"""
        for loan in bank_data.get('loans', []):
            context += f"""
- {loan['loan_type']}: ₹{loan['outstanding_balance']:,.2f} outstanding
  EMI: ₹{loan['emi_amount']:,.2f} (Due on {loan['emi_due_date']}th of each month)
  Interest Rate: {loan['interest_rate']}%
  Remaining Tenure: {loan['remaining_tenure_months']} months
"""
        
        context += "\n=== RECURRING PAYMENTS ===\n"
        for payment in bank_data.get('recurring_payments', []):
            context += f"- {payment['category']}: ₹{payment['amount']:,.2f} ({payment['frequency']}) - Next due: {payment['next_due_date']}\n"
        
        context += f"""
=== CURRENT MONTH SPENDING ===
Total Spent: ₹{bank_data['spending_summary']['current_month']['total_spent']:,.2f}
Breakdown by Category:
"""
        for category, amount in bank_data['spending_summary']['current_month']['by_category'].items():
            context += f"- {category}: ₹{amount:,.2f}\n"
        
        context += "\n=== RECENT TRANSACTIONS (Last 5) ===\n"
        for txn in bank_data.get('transaction_history', [])[:5]:
            context += f"{txn['date']} | {txn['description']} | ₹{abs(txn['amount']):,.2f} ({txn['type']}) | Balance: ₹{txn['balance_after']:,.2f}\n"
        
        if bank_data.get('alerts'):
            context += "\n=== ACTIVE ALERTS ===\n"
            for alert in bank_data['alerts']:
                context += f"⚠️ {alert['type']}: {alert['message']} (Severity: {alert['severity']})\n"
        
        context += "\n=== INVESTMENTS ===\n"
        for inv in bank_data.get('investments', []):
            if inv['type'] == 'Mutual Funds':
                context += f"- {inv['type']}: ₹{inv['amount']:,.2f} invested, Current Value: ₹{inv['current_value']:,.2f} (Returns: {inv['returns_percentage']}%)\n"
            else:
                context += f"- {inv['type']}: ₹{inv['amount']:,.2f} @ {inv['interest_rate']}% (Maturity: {inv['maturity_date']})\n"
        
        return context
    
    def get_system_prompt(self, bank_context: str) -> str:
        """Create enhanced system prompt with bank data context"""
        return f'''Role: You are the AI Personal Finance Copilot, a highly intelligent, empathetic, and proactive financial advisor. You have direct access to the user's complete banking information and transaction history.

Core Capabilities & Context:

Real-Time Data Access: You have access to the user's current balance, transaction history, loans, investments, spending patterns, and recurring payments. Use this data to provide personalized, actionable advice.

Predictive Analysis: Forecast account balances based on spending patterns and warn users before they hit low-balance thresholds or overspend.

Behavioral Intelligence: Identify spending patterns and behavioral traits (Saver, Impulsive Spender, Balanced). Adapt your tone accordingly.

Sentiment Awareness: Analyze the user's language. If they sound stressed, excited, or impulsive, provide a "cooling off" warning before major financial decisions.

Optimization Engines: Specialize in EMI optimization, loan default risk assessment, budget planning, and investment advice.

{bank_context}

Operational Guidelines:

1. Be Proactive: Don't just answer questions. Notice trends and bring them up (e.g., "Your dining expenses increased by 18% this month").
2. Data-Driven: Always reference specific numbers from the user's account when giving advice.
3. Context-Aware: Consider upcoming EMIs, salary credit dates, and recurring payments when advising.
4. Risk Assessment: Alert users about potential overdrafts, high debt-to-income ratios, or concerning spending patterns.
5. Goal-Oriented: Help users plan for savings goals, emergency funds, and debt repayment.
6. Privacy First: Never share sensitive account details unnecessarily, but use them to provide personalized advice.

Tone and Voice:
- Professional yet conversational
- Non-judgmental but honest about financial risks
- Calm and reassuring, especially during budget concerns
- Use Indian currency format (₹ and lakhs/crores when appropriate)

Safety Disclaimer: Remind users that while you provide data-driven insights based on their actual financial data, you are an AI assistant. Major financial decisions should be verified with official bank statements or a human financial advisor.'''
    
    async def get_chat_response(self, user_id: str, message: str) -> str:
        """Get response from Groq API with bank data context"""
        # Load bank data
        bank_data = self.load_bank_data(user_id)
        
        # Prepare context
        bank_context = self.prepare_context(bank_data)
        system_prompt = self.get_system_prompt(bank_context)
        
        # Load conversation history (last 10 messages)
        history = self.load_conversation_history(user_id)
        recent_history = history[-10:] if len(history) > 10 else history
        
        # Prepare messages for API
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(recent_history)
        messages.append({"role": "user", "content": message})
        
        try:
            completion = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=0.7,
                max_completion_tokens=1024,
                top_p=0.9,
                stream=False,
                stop=None
            )
            
            full_response = completion.choices[0].message.content
            
            # Save to conversation history
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": full_response})
            self.save_conversation_history(user_id, history)
            
            return full_response
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error getting AI response: {str(e)}"
            )

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting Bank Chatbot API...")
    yield
    # Shutdown
    print("Shutting down Bank Chatbot API...")

# Initialize FastAPI app
app = FastAPI(
    title="AI Banking Chatbot API",
    description="Intelligent personal finance assistant with real-time banking data integration",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize service
chatbot_service = BankChatbotService()

# Simple auth verification (replace with proper JWT/OAuth in production)
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    # TODO: Implement proper token verification
    # For now, just check if token exists
    if not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    return credentials.credentials

# API Endpoints
@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "AI Banking Chatbot API",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(
    request: ChatRequest,
    token: str = Depends(verify_token)
):
    """
    Send a message to the AI banking assistant
    
    - **message**: User's question or message
    - **user_id**: Unique identifier for the user
    """
    try:
        response = await chatbot_service.get_chat_response(
            user_id=request.user_id,
            message=request.message
        )
        
        return ChatResponse(
            response=response,
            timestamp=datetime.now().isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@app.get("/api/history/{user_id}", response_model=ConversationHistory, tags=["Chat"])
async def get_conversation_history(
    user_id: str,
    limit: Optional[int] = 50,
    token: str = Depends(verify_token)
):
    """
    Get conversation history for a user
    
    - **user_id**: Unique identifier for the user
    - **limit**: Maximum number of messages to return (default: 50)
    """
    try:
        history = chatbot_service.load_conversation_history(user_id)
        limited_history = history[-limit:] if len(history) > limit else history
        
        messages = [Message(**msg) for msg in limited_history]
        
        return ConversationHistory(
            messages=messages,
            total_messages=len(history)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error loading conversation history: {str(e)}"
        )

@app.delete("/api/history/{user_id}", tags=["Chat"])
async def clear_conversation_history(
    user_id: str,
    token: str = Depends(verify_token)
):
    """
    Clear conversation history for a user
    
    - **user_id**: Unique identifier for the user
    """
    try:
        chatbot_service.save_conversation_history(user_id, [])
        return {"status": "success", "message": "Conversation history cleared"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error clearing conversation history: {str(e)}"
        )

@app.get("/api/bank-data/{user_id}", response_model=BankDataResponse, tags=["Banking"])
async def get_bank_data_summary(
    user_id: str,
    token: str = Depends(verify_token)
):
    """
    Get bank data summary for a user
    
    - **user_id**: Unique identifier for the user
    """
    try:
        bank_data = chatbot_service.load_bank_data(user_id)
        
        summary = {
            "total_balance": bank_data['user_profile']['current_balance'],
            "total_loans": sum(loan['outstanding_balance'] for loan in bank_data.get('loans', [])),
            "monthly_expenses": bank_data['spending_summary']['current_month']['total_spent'],
            "credit_score": bank_data['user_profile']['credit_score']
        }
        
        return BankDataResponse(
            user_profile=bank_data['user_profile'],
            summary=summary
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error loading bank data: {str(e)}"
        )

# Cash Flow Forecasting Endpoints
@app.post("/api/forecast", response_model=ForecastResponse, tags=["Forecasting"])
async def generate_cash_flow_forecast(
    request: ForecastRequest,
    token: str = Depends(verify_token)
):
    """
    Generate cash flow forecast for a user
    
    - **user_id**: Unique identifier for the user
    - **prediction_months**: Number of months to forecast (1-24)
    - **warning_threshold**: Balance threshold for warnings
    - **expense_growth_rate**: Monthly expense growth rate (0.0 = no growth)
    - **income_growth_rate**: Monthly income growth rate (0.0 = no growth)
    """
    try:
        # Load user's bank data
        bank_data = chatbot_service.load_bank_data(request.user_id)
        
        # Extract data for forecast
        current_balance = bank_data['user_profile']['current_balance']
        monthly_salary = bank_data['user_profile']['monthly_salary']
        
        # Create recurring income from salary
        recurring_income = [
            RecurringIncome(
                amount=monthly_salary,
                category=IncomeCategory.SALARY
            )
        ]
        
        # Calculate monthly expenses from spending summary
        monthly_expenses = bank_data['spending_summary']['current_month']['by_category']
        
        # Add loan payments to expenses
        for loan in bank_data.get('loans', []):
            if 'Loan Payment' not in monthly_expenses:
                monthly_expenses['Loan Payment'] = 0
            monthly_expenses['Loan Payment'] += loan['emi_amount']
        
        # Create forecast input
        forecast_input = CashFlowInput(
            current_balance=current_balance,
            recurring_income=recurring_income,
            monthly_expenses=monthly_expenses,
            one_time_expenses=[],
            one_time_income=[],
            prediction_months=request.prediction_months,
            warning_threshold=request.warning_threshold,
            expense_growth_rate=request.expense_growth_rate,
            income_growth_rate=request.income_growth_rate
        )
        
        # Generate forecast
        predictor = CashFlowPredictor(forecast_input)
        predictor.predict()
        
        # Get results
        monthly_predictions = []
        for pred in predictor.predictions:
            monthly_predictions.append({
                "month": pred.month,
                "date": pred.date,
                "opening_balance": pred.opening_balance,
                "income": pred.income,
                "expenses": pred.expenses,
                "closing_balance": pred.closing_balance,
                "net_flow": pred.net_flow,
                "income_breakdown": pred.income_breakdown,
                "expense_breakdown": pred.expense_breakdown,
                "warnings": pred.warnings,
                "risk_level": pred.risk_level.value
            })
        
        summary = predictor.get_summary()
        summary_dict = {
            "initial_balance": summary.initial_balance,
            "final_balance": summary.final_balance,
            "total_change": summary.total_change,
            "total_income": summary.total_income,
            "total_expenses": summary.total_expenses,
            "total_net_flow": summary.total_net_flow,
            "average_monthly_balance": summary.average_monthly_balance,
            "median_monthly_balance": summary.median_monthly_balance,
            "lowest_balance": summary.lowest_balance,
            "highest_balance": summary.highest_balance,
            "lowest_balance_month": summary.lowest_balance_month,
            "highest_balance_month": summary.highest_balance_month,
            "months_below_threshold": summary.months_below_threshold,
            "months_negative": summary.months_negative,
            "is_sustainable": summary.is_sustainable,
            "overall_risk_level": summary.overall_risk_level.value,
            "savings_rate": summary.savings_rate,
            "emergency_fund_months": summary.emergency_fund_months,
            "income_by_category": summary.income_by_category,
            "volatility_score": summary.volatility_score
        }
        
        chart_data = predictor.get_chart_data()
        
        return ForecastResponse(
            monthly_predictions=monthly_predictions,
            summary=summary_dict,
            chart_data=chart_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating forecast: {str(e)}"
        )

# User Spending Classification Endpoint
@app.post("/api/classify-spending", response_model=SpendingClassificationResponse, tags=["Classification"])
async def classify_user_spending(
    request: SpendingClassificationRequest,
    token: str = Depends(verify_token)
):
    """
    Classify user's spending pattern
    
    - **income**: User's monthly income
    - **expenses**: Dictionary of expense categories and amounts
    """
    try:
        result = classify_single_user(request.income, request.expenses)
        
        return SpendingClassificationResponse(**result)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error classifying spending: {str(e)}"
        )

# User Profile Endpoint (combines bank data + classification)
@app.get("/api/user-profile/{user_id}", response_model=UserProfileResponse, tags=["User"])
async def get_user_profile(
    user_id: str,
    token: str = Depends(verify_token)
):
    """
    Get complete user profile with bank data and spending classification
    
    - **user_id**: Unique identifier for the user
    """
    try:
        # Get bank data
        bank_data = chatbot_service.load_bank_data(user_id)
        
        user_profile = bank_data['user_profile']
        summary = {
            "total_balance": user_profile['current_balance'],
            "total_loans": sum(loan['outstanding_balance'] for loan in bank_data.get('loans', [])),
            "monthly_expenses": bank_data['spending_summary']['current_month']['total_spent'],
            "credit_score": user_profile['credit_score']
        }
        
        # Classify spending pattern
        try:
            income = user_profile['monthly_salary']
            expenses = bank_data['spending_summary']['current_month']['by_category']
            classification = classify_single_user(income, expenses)
        except Exception as e:
            print(f"Classification error: {e}")
            classification = None
        
        return UserProfileResponse(
            user_profile=user_profile,
            bank_summary=summary,
            spending_classification=classification
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error loading user profile: {str(e)}"
        )


if __name__ == "__main__":
    uvicorn.run(
        "eg2:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )