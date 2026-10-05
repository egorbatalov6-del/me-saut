from pymongo import MongoClient

client = MongoClient("mongodb+srv://egorbatalov6_db_user:KpSXoC7dPWhubslU@cluster0.vysgpku.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")

db = client["pixel_vault_db"]
games_collection = db["games"]
users_collection = db["users"]          # Коллекция пользователей
codes_collection = db["email_codes"]    # Коды подтверждения почты
orders_collection = db["orders"]        # Покупки пользователей