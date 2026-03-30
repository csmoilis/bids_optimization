import sqlite3
import random
from datetime import datetime

# 1. Connect to the database
conn = sqlite3.connect('centrica_trading_practice_v2.db')
cursor = conn.cursor()
cursor.execute("PRAGMA foreign_keys = ON;")

# 2. Create the Revised Infrastructure
cursor.executescript('''
    -- Information from "SQL Server" (Manual/Internal Data)
    CREATE TABLE dim_traders (
        trader_id INTEGER PRIMARY KEY AUTOINCREMENT,
        trader_name TEXT NOT NULL,
        strategy TEXT,
        years_experience INTEGER
    );

    -- Information from "SQL Server" (Contract/External Service)
    CREATE TABLE dim_exchange_contracts (
        contract_id INTEGER PRIMARY KEY, -- e.g. 5001, 5002
        exchange_name TEXT NOT NULL,
        stock_ticker TEXT NOT NULL,
        country TEXT,
        commission REAL
    );

    -- MANY-TO-MANY BRIDGE TABLE
    CREATE TABLE bridge_trader_contract (
        trader_id INTEGER,
        contract_id INTEGER,
        cod_auth TEXT,
        PRIMARY KEY (trader_id, contract_id),
        FOREIGN KEY (trader_id) REFERENCES dim_traders(trader_id),
        FOREIGN KEY (contract_id) REFERENCES dim_exchange_contracts(contract_id)
    );

    -- FACT TABLE: Merging "Excel" data with existing keys
    CREATE TABLE fact_trades (
        trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
        trader_id INTEGER,
        contract_id INTEGER,
        price REAL,
        take_profit REAL,
        stop_loss REAL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (trader_id) REFERENCES dim_traders(trader_id),
        FOREIGN KEY (contract_id) REFERENCES dim_exchange_contracts(contract_id)
    );
''')

# 3. Generate Synthetic Data for "SQL Server" Tables
traders = [
    ('Alice Schmidt', 'Wind Hedging', 5),
    ('Mateo Silva', 'Gas Arbitrage', 8),
    ('Hanna Jensen', 'Carbon Credits', 3)
]

contracts = [
    (5001, 'ICE', 'NG', 'United Kingdom', 0.05), # Natural Gas
    (5002, 'EPEX', 'PWR_DE', 'Germany', 0.08),   # Power Germany
    (5003, 'NASDAQ', 'EQ_UK', 'United Kingdom', 0.02)
]

cursor.executemany("INSERT INTO dim_traders (trader_name, strategy, years_experience) VALUES (?, ?, ?)", traders)
cursor.executemany("INSERT INTO dim_exchange_contracts VALUES (?, ?, ?, ?, ?)", contracts)

# Create Bridge Relationships (Traders assigned to specific contracts)
bridge_data = [
    (1, 5001, 'AUTH-99'), # Alice trades Gas
    (1, 5003, 'AUTH-88'), # Alice trades UK Equities
    (2, 5002, 'AUTH-77'), # Mateo trades Power
    (3, 5001, 'AUTH-66')  # Hanna trades Gas
]
cursor.executemany("INSERT INTO bridge_trader_contract VALUES (?, ?, ?)", bridge_data)

# 4. Generate Synthetic "Excel" Style Data for the Fact Table
# In your project, you'll eventually replace this with a Pandas read_excel loop
for _ in range(30):
    t_id = random.choice([1, 2, 3])
    c_id = random.choice([5001, 5002, 5003])
    base_price = random.uniform(50, 150)
    
    cursor.execute('''
        INSERT INTO fact_trades (trader_id, contract_id, price, take_profit, stop_loss)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        t_id, 
        c_id, 
        round(base_price, 2), 
        round(base_price * 1.10, 2), # Take profit at +10%
        round(base_price * 0.95, 2)  # Stop loss at -5%
    ))

conn.commit()
print("Infrastructure v2 ready: Traders, Contracts, and Trades populated!")
conn.close()