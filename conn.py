import sqlite3
#define connection and cursor
connection =sqlite3.connect('dbname')
cursor = connection.cursor()
#create table 
command1="""CREATE TABLE IF NOT EXISTS 
loan(loan_id INTEGER PRIMARY KEY,amount INTEGER)"""
cursor.execute(command1)