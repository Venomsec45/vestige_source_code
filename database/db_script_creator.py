import argparse
import os
import mysql.connector

def argument():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True, help="Enter the hostname (e.g. 127.0.0.1)")
    parser.add_argument("--user", required=True, help="Enter the username")
    parser.add_argument("--password", required=True, help="Enter the password of the mysql database")
    parser.add_argument("--database", required=True, help="Enter the name of the database")
    return parser

args = argument().parse_args()

def create_db_script(host: str, user: str, password: str, database: str):
    with open(f"{os.path.dirname(__file__)}/db_connection.py", "w") as file:
        file.write(f"""import mysql.connector

def connect_to_db():
    return mysql.connector.connect(
        host="{host}",
        user="{user}",
        password="{password}",
        database="{database}"    
    )
""")

create_db_script(args.host, args.user, args.password, args.database)