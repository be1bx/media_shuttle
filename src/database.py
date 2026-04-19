import asyncpg
import os

class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            host="db" # Имя сервиса из docker-compose
        )
        
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    requests_count INTEGER DEFAULT 0
                )
            ''')

    async def log_request(self, user_id, username):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO users (user_id, username, requests_count)
                VALUES ($1, $2, 1)
                ON CONFLICT (user_id) DO UPDATE 
                SET requests_count = users.requests_count + 1
            ''', user_id, username)
