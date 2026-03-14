-- Bank Database Schema and Data

-- Create database
CREATE DATABASE IF NOT EXISTS bank_system;
USE bank_system;

-- User Profile Table
CREATE TABLE user_profile (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    account_number VARCHAR(50) UNIQUE NOT NULL,
    account_type VARCHAR(50),
    current_balance DECIMAL(15, 2),
    available_balance DECIMAL(15, 2),
    monthly_salary DECIMAL(15, 2),
    salary_credit_date INT,
    joined_date DATE,
    credit_score INT,
    risk_profile VARCHAR(50)
);

-- Recurring Payments Table
CREATE TABLE recurring_payments (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    category VARCHAR(100),
    amount DECIMAL(10, 2),
    frequency VARCHAR(50),
    next_due_date DATE,
    FOREIGN KEY (user_id) REFERENCES user_profile(id)
);

-- Loans Table
CREATE TABLE loans (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    loan_type VARCHAR(100),
    principal_amount DECIMAL(15, 2),
    outstanding_balance DECIMAL(15, 2),
    interest_rate DECIMAL(5, 2),
    emi_amount DECIMAL(10, 2),
    emi_due_date INT,
    remaining_tenure_months INT,
    status VARCHAR(50),
    FOREIGN KEY (user_id) REFERENCES user_profile(id)
);

-- Investments Table
CREATE TABLE investments (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    type VARCHAR(100),
    amount DECIMAL(15, 2),
    returns_percentage DECIMAL(5, 2),
    current_value DECIMAL(15, 2),
    interest_rate DECIMAL(5, 2),
    maturity_date DATE,
    FOREIGN KEY (user_id) REFERENCES user_profile(id)
);

-- Transaction History Table
CREATE TABLE transaction_history (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    date DATE,
    description VARCHAR(255),
    category VARCHAR(100),
    amount DECIMAL(15, 2),
    balance_after DECIMAL(15, 2),
    type VARCHAR(20),
    FOREIGN KEY (user_id) REFERENCES user_profile(id)
);

-- Alerts Table
CREATE TABLE alerts (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    type VARCHAR(100),
    message TEXT,
    severity VARCHAR(50),
    date DATE,
    FOREIGN KEY (user_id) REFERENCES user_profile(id)
);

-- Insert User Profile
INSERT INTO user_profile (name, account_number, account_type, current_balance, available_balance, 
                         monthly_salary, salary_credit_date, joined_date, credit_score, risk_profile)
VALUES ('John Doe', 'ACC123456789', 'Savings', 45000.00, 43500.00, 75000.00, 1, '2020-03-15', 720, 'Moderate');

-- Insert Recurring Payments
INSERT INTO recurring_payments (user_id, category, amount, frequency, next_due_date) VALUES
(1, 'Rent', 25000.00, 'monthly', '2026-02-01'),
(1, 'Netflix', 649.00, 'monthly', '2026-01-20'),
(1, 'Spotify', 119.00, 'monthly', '2026-01-25'),
(1, 'Gym Membership', 2000.00, 'monthly', '2026-01-28');

-- Insert Loans
INSERT INTO loans (user_id, loan_type, principal_amount, outstanding_balance, interest_rate, 
                   emi_amount, emi_due_date, remaining_tenure_months, status) VALUES
(1, 'Personal Loan', 200000.00, 150000.00, 10.5, 5500.00, 5, 30, 'Active'),
(1, 'Car Loan', 500000.00, 320000.00, 8.75, 8200.00, 10, 42, 'Active');

-- Insert Investments
INSERT INTO investments (user_id, type, amount, returns_percentage, current_value, interest_rate, maturity_date) VALUES
(1, 'Mutual Funds', 125000.00, 12.5, 140625.00, NULL, NULL),
(1, 'Fixed Deposit', 100000.00, NULL, NULL, 6.5, '2026-12-31');

-- Insert Transaction History
INSERT INTO transaction_history (user_id, date, description, category, amount, balance_after, type) VALUES
(1, '2026-01-16', 'Grocery Shopping - BigBazaar', 'Groceries', -3500.00, 45000.00, 'debit'),
(1, '2026-01-15', 'Fuel - Indian Oil', 'Transportation', -2000.00, 48500.00, 'debit'),
(1, '2026-01-14', 'Dinner - Taj Restaurant', 'Dining', -4500.00, 50500.00, 'debit'),
(1, '2026-01-13', 'Online Shopping - Amazon', 'Shopping', -8900.00, 55000.00, 'debit'),
(1, '2026-01-12', 'Movie Tickets - PVR', 'Entertainment', -1200.00, 63900.00, 'debit'),
(1, '2026-01-10', 'Car Loan EMI', 'Loan Payment', -8200.00, 65100.00, 'debit'),
(1, '2026-01-08', 'Medical - Apollo Pharmacy', 'Healthcare', -1500.00, 73300.00, 'debit'),
(1, '2026-01-05', 'Personal Loan EMI', 'Loan Payment', -5500.00, 74800.00, 'debit'),
(1, '2026-01-03', 'Electricity Bill', 'Utilities', -2200.00, 80300.00, 'debit'),
(1, '2026-01-01', 'Salary Credit', 'Income', 75000.00, 82500.00, 'credit'),
(1, '2025-12-28', 'Grocery Shopping - Reliance Fresh', 'Groceries', -4200.00, 7500.00, 'debit'),
(1, '2025-12-25', 'Gift Shopping - Lifestyle', 'Shopping', -6500.00, 11700.00, 'debit'),
(1, '2025-12-20', 'Restaurant - Barbeque Nation', 'Dining', -3800.00, 18200.00, 'debit'),
(1, '2025-12-15', 'Flight Booking - IndiGo', 'Travel', -12000.00, 22000.00, 'debit'),
(1, '2025-12-10', 'Car Loan EMI', 'Loan Payment', -8200.00, 34000.00, 'debit');

-- Insert Alerts
INSERT INTO alerts (user_id, type, message, severity, date) VALUES
(1, 'Low Balance Warning', 'Your balance is approaching the minimum threshold', 'medium', '2026-01-16'),
(1, 'High Spending', 'Shopping expenses increased by 37% compared to last month', 'low', '2026-01-14');