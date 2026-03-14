from groq import Groq
from dotenv import dotenv_values
import json
import os
from datetime import datetime

class BankChatbot:
    def __init__(self, bank_data_path="bank_data.json", history_path="conversation_history.json"):
        self.bank_data_path = bank_data_path
        self.history_path = history_path
        self.config = dotenv_values(".env")
        self.api = self.config.get("GROQ_API")
        self.client = Groq(api_key=self.api)
        
        # Initialize conversation history if it doesn't exist
        if not os.path.exists(self.history_path):
            with open(self.history_path, 'w') as f:
                json.dump([], f)
    
    def load_bank_data(self):
        """Load user's bank data from JSON file"""
        try:
            with open(self.bank_data_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: {self.bank_data_path} not found!")
            return None
    
    def load_conversation_history(self):
        """Load conversation history"""
        try:
            with open(self.history_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return []
    
    def save_conversation_history(self, history):
        """Save conversation history"""
        with open(self.history_path, 'w') as f:
            json.dump(history, f, indent=4)
    
    def prepare_context(self, bank_data):
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
        for loan in bank_data['loans']:
            context += f"""
- {loan['loan_type']}: ₹{loan['outstanding_balance']:,.2f} outstanding
  EMI: ₹{loan['emi_amount']:,.2f} (Due on {loan['emi_due_date']}th of each month)
  Interest Rate: {loan['interest_rate']}%
  Remaining Tenure: {loan['remaining_tenure_months']} months
"""
        
        context += "\n=== RECURRING PAYMENTS ===\n"
        for payment in bank_data['recurring_payments']:
            context += f"- {payment['category']}: ₹{payment['amount']:,.2f} ({payment['frequency']}) - Next due: {payment['next_due_date']}\n"
        
        context += f"""
=== CURRENT MONTH SPENDING ===
Total Spent: ₹{bank_data['spending_summary']['current_month']['total_spent']:,.2f}
Breakdown by Category:
"""
        for category, amount in bank_data['spending_summary']['current_month']['by_category'].items():
            context += f"- {category}: ₹{amount:,.2f}\n"
        
        context += "\n=== RECENT TRANSACTIONS (Last 5) ===\n"
        for txn in bank_data['transaction_history'][:5]:
            context += f"{txn['date']} | {txn['description']} | ₹{abs(txn['amount']):,.2f} ({txn['type']}) | Balance: ₹{txn['balance_after']:,.2f}\n"
        
        if bank_data['alerts']:
            context += "\n=== ACTIVE ALERTS ===\n"
            for alert in bank_data['alerts']:
                context += f"⚠️ {alert['type']}: {alert['message']} (Severity: {alert['severity']})\n"
        
        context += f"""
=== INVESTMENTS ===
"""
        for inv in bank_data['investments']:
            if inv['type'] == 'Mutual Funds':
                context += f"- {inv['type']}: ₹{inv['amount']:,.2f} invested, Current Value: ₹{inv['current_value']:,.2f} (Returns: {inv['returns_percentage']}%)\n"
            else:
                context += f"- {inv['type']}: ₹{inv['amount']:,.2f} @ {inv['interest_rate']}% (Maturity: {inv['maturity_date']})\n"
        
        return context
    
    def get_system_prompt(self, bank_context):
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
    
    def get_response(self, prompt):
        """Get response from Groq API with bank data context"""
        # Load bank data
        bank_data = self.load_bank_data()
        if not bank_data:
            return "Error: Could not load bank data. Please ensure bank_data.json exists."
        
        # Prepare context
        bank_context = self.prepare_context(bank_data)
        system_prompt = self.get_system_prompt(bank_context)
        
        # Load conversation history (last 5 messages to keep context manageable)
        history = self.load_conversation_history()
        recent_history = history[-10:] if len(history) > 10 else history
        
        # Prepare messages for API
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add recent conversation history
        for msg in recent_history:
            messages.append(msg)
        
        # Add current user message
        messages.append({"role": "user", "content": prompt})
        
        # Get response from Groq
        try:
            completion = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=0.7,
                max_completion_tokens=1024,
                top_p=0.9,
                stream=True,
                stop=None
            )
            
            full_response = ""
            print("Assistant: ", end="", flush=True)
            for chunk in completion:
                content = chunk.choices[0].delta.content or ""
                full_response += content
                print(content, end="", flush=True)
            print()  # New line after response
            
            # Save to conversation history
            history.append({"role": "user", "content": prompt})
            history.append({"role": "assistant", "content": full_response})
            self.save_conversation_history(history)
            
            return full_response
            
        except Exception as e:
            return f"Error getting response: {str(e)}"
    
    def chat(self):
        """Interactive chat loop"""
        print("=" * 60)
        print("🏦 AI Personal Finance Copilot")
        print("=" * 60)
        print("I have access to your complete financial profile.")
        print("Ask me anything about your finances, spending, or get personalized advice!")
        print("Type 'quit' or 'exit' to end the conversation.\n")
        
        while True:
            user_input = input("You: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("Assistant: Goodbye! Remember to keep tracking your finances. 💰")
                break
            
            if not user_input:
                continue
            
            self.get_response(user_input)
            print()

def main():
    # Create chatbot instance
    chatbot = BankChatbot()
    
    # Check if bank data exists
    if not os.path.exists("bank_data.json"):
        print("Warning: bank_data.json not found. Please create it with your financial data.")
        return
    
    # Start interactive chat
    chatbot.chat()

if __name__ == "__main__":
    main()