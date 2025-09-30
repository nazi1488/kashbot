"""
Асинхронная обертка для базы данных с connection pooling
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

import asyncpg
from asyncpg import Pool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text

logger = logging.getLogger(__name__)

Base = declarative_base()


class AsyncDatabase:
    """Асинхронный менеджер БД с connection pooling"""
    
    def __init__(self, database_url: str, pool_size: int = 20, max_overflow: int = 10):
        """
        Args:
            database_url: PostgreSQL connection string
            pool_size: Размер пула соединений
            max_overflow: Максимальное превышение пула
        """
        # Конвертируем URL для asyncpg
        if database_url.startswith('postgresql://'):
            self.async_url = database_url.replace('postgresql://', 'postgresql+asyncpg://')
        else:
            self.async_url = database_url
            
        self.pool: Optional[Pool] = None
        self.engine = None
        self.async_session = None
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        
    async def init(self):
        """Инициализация пула соединений"""
        try:
            # SQLAlchemy async engine с пулом
            self.engine = create_async_engine(
                self.async_url,
                pool_size=self.pool_size,
                max_overflow=self.max_overflow,
                pool_pre_ping=True,  # Проверка соединения перед использованием
                pool_recycle=3600,   # Переподключение каждый час
                echo=False
            )
            
            # Создаем фабрику сессий
            self.async_session = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Создаем raw asyncpg pool для быстрых запросов
            db_url = self.async_url.replace('postgresql+asyncpg://', 'postgresql://')
            self.pool = await asyncpg.create_pool(
                db_url,
                min_size=10,
                max_size=self.pool_size,
                command_timeout=60,
                max_queries=50000,
                max_inactive_connection_lifetime=300
            )
            
            logger.info(f"Database pool initialized with {self.pool_size} connections")
            
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise
    
    async def close(self):
        """Закрытие пула соединений"""
        if self.pool:
            await self.pool.close()
        if self.engine:
            await self.engine.dispose()
    
    @asynccontextmanager
    async def session(self):
        """Контекстный менеджер для сессии"""
        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    
    @asynccontextmanager
    async def connection(self):
        """Контекстный менеджер для прямого соединения"""
        async with self.pool.acquire() as connection:
            yield connection
    
    async def execute(self, query: str, *args) -> Optional[List[asyncpg.Record]]:
        """
        Выполнение сырого SQL запроса
        
        Args:
            query: SQL запрос
            *args: Параметры запроса
        
        Returns:
            Результаты запроса
        """
        async with self.connection() as conn:
            try:
                return await conn.fetch(query, *args)
            except Exception as e:
                logger.error(f"Query execution failed: {e}")
                raise
    
    async def execute_one(self, query: str, *args) -> Optional[asyncpg.Record]:
        """Выполнение запроса с одним результатом"""
        async with self.connection() as conn:
            try:
                return await conn.fetchrow(query, *args)
            except Exception as e:
                logger.error(f"Query execution failed: {e}")
                raise
    
    async def execute_scalar(self, query: str, *args) -> Any:
        """Выполнение запроса со скалярным результатом"""
        async with self.connection() as conn:
            try:
                return await conn.fetchval(query, *args)
            except Exception as e:
                logger.error(f"Query execution failed: {e}")
                raise
    
    async def execute_many(self, query: str, args_list: List[tuple]):
        """Выполнение batch запросов"""
        async with self.connection() as conn:
            try:
                await conn.executemany(query, args_list)
            except Exception as e:
                logger.error(f"Batch execution failed: {e}")
                raise
    
    # Методы для работы с пользователями
    async def get_user(self, user_id: int) -> Optional[Dict]:
        """Получение пользователя по ID"""
        query = """
            SELECT user_id, username, first_name, last_name, language_code, 
                   is_premium, created_at, updated_at
            FROM users 
            WHERE user_id = $1
        """
        row = await self.execute_one(query, user_id)
        return dict(row) if row else None
    
    async def upsert_user(self, user_data: Dict) -> bool:
        """Создание или обновление пользователя"""
        query = """
            INSERT INTO users (user_id, username, first_name, last_name, language_code, is_premium)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (user_id) 
            DO UPDATE SET 
                username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                language_code = EXCLUDED.language_code,
                is_premium = EXCLUDED.is_premium,
                updated_at = NOW()
            RETURNING user_id
        """
        try:
            await self.execute_scalar(
                query,
                user_data['user_id'],
                user_data.get('username'),
                user_data.get('first_name'),
                user_data.get('last_name'),
                user_data.get('language_code', 'ru'),
                user_data.get('is_premium', False)
            )
            return True
        except Exception as e:
            logger.error(f"Failed to upsert user: {e}")
            return False
    
    # Методы для работы с задачами
    async def save_task_result(self, task_id: str, user_id: int, result: Dict):
        """Сохранение результата задачи"""
        query = """
            INSERT INTO task_results (task_id, user_id, status, result, created_at)
            VALUES ($1, $2, $3, $4::jsonb, NOW())
            ON CONFLICT (task_id) 
            DO UPDATE SET 
                status = EXCLUDED.status,
                result = EXCLUDED.result,
                updated_at = NOW()
        """
        try:
            import json
            await self.execute(
                query,
                task_id,
                user_id,
                result.get('status', 'completed'),
                json.dumps(result)
            )
        except Exception as e:
            logger.error(f"Failed to save task result: {e}")
    
    async def get_user_tasks(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Получение задач пользователя"""
        query = """
            SELECT task_id, status, result, created_at
            FROM task_results
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2
        """
        rows = await self.execute(query, user_id, limit)
        return [dict(row) for row in rows] if rows else []
    
    # Метрики для мониторинга
    async def get_pool_stats(self) -> Dict:
        """Получение статистики пула соединений"""
        if not self.pool:
            return {}
        
        return {
            'size': self.pool.get_size(),
            'free': self.pool.get_idle_size(),
            'used': self.pool.get_size() - self.pool.get_idle_size(),
            'max_size': self.pool_size
        }


# Глобальный экземпляр для использования в приложении
async_db: Optional[AsyncDatabase] = None


async def init_async_db(database_url: str) -> AsyncDatabase:
    """Инициализация глобального async DB"""
    global async_db
    async_db = AsyncDatabase(database_url)
    await async_db.init()
    return async_db


async def close_async_db():
    """Закрытие глобального async DB"""
    global async_db
    if async_db:
        await async_db.close()
        async_db = None
