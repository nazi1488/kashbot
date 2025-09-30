"""
SQLAlchemy модели для работы с базой данных
"""

import asyncio
import logging
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, DateTime, Boolean, ForeignKey, Text, UUID as PGUUID, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()

logger = logging.getLogger(__name__)


class User(Base):
    """Модель пользователя"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    tg_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(Text, nullable=True)
    language = Column(String(5), nullable=True, default=None)  # Код языка (ru, en, uk)
    first_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_blocked = Column(Boolean, default=False)
    
    # Отношения
    events = relationship("Event", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, tg_id={self.tg_id}, username={self.username})>"


class Event(Base):
    """Модель события"""
    __tablename__ = 'events'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    ts = Column(DateTime, nullable=False, default=datetime.utcnow)
    event_type = Column(Text, nullable=False)  # 'command', 'message', 'callback', etc.
    command = Column(Text, nullable=True)  # Название команды/функции
    session_id = Column(PGUUID(as_uuid=True), ForeignKey('sessions.id'), nullable=True)
    
    # Отношения
    user = relationship("User", back_populates="events")
    session = relationship("Session", back_populates="events")
    
    def __repr__(self):
        return f"<Event(id={self.id}, user_id={self.user_id}, type={self.event_type}, command={self.command})>"


class Session(Base):
    """Модель сессии пользователя"""
    __tablename__ = 'sessions'
    
    id = Column(PGUUID(as_uuid=True), primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    events_count = Column(Integer, default=0)
    duration_seconds = Column(Integer, default=0)
    
    # Отношения
    user = relationship("User", back_populates="sessions")
    events = relationship("Event", back_populates="session", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Session(id={self.id}, user_id={self.user_id}, events={self.events_count})>"


# Класс для работы с базой данных
class Database:
    """Менеджер базы данных"""
    
    def __init__(self, database_url: str):
        # Заменяем драйвер если нужно
        if "postgresql+psycopg://" in database_url:
            database_url = database_url.replace("postgresql+psycopg://", "postgresql+psycopg2://")
        
        self.engine = create_engine(database_url, pool_size=10, max_overflow=20)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
    def get_session(self):
        """Получить сессию базы данных"""
        return self.SessionLocal()
    
    def create_tables(self):
        """Создать таблицы если их нет"""
        Base.metadata.create_all(bind=self.engine)

    async def execute(self, query: str, params=None, fetch: bool = False):
        """Выполняет SQL запрос асинхронно."""
        params = params or ()

        def _run_query():
            connection = self.engine.raw_connection()
            try:
                with connection.cursor() as cursor:
                    cursor.execute(query, params)

                    # Если нужно вернуть данные или запрос содержит RETURNING
                    if fetch or cursor.description:
                        rows = cursor.fetchall()
                        columns = [col[0] for col in cursor.description] if cursor.description else []
                        connection.commit()
                        if columns:
                            return [dict(zip(columns, row)) for row in rows]
                        return rows

                    connection.commit()
                    return None
            finally:
                connection.close()

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _run_query)

    async def get_user_language(self, tg_id: int) -> str:
        """Получает сохраненный язык пользователя"""
        try:
            query = "SELECT language FROM users WHERE tg_id = %s"
            result = await self.execute(query, (tg_id,), fetch=True)
            
            if result and result[0]['language']:
                return result[0]['language']
            else:
                return None  # Язык не установлен
                
        except Exception as e:
            logger.error(f"Error getting user language: {e}")
            return None

    async def set_user_language(self, tg_id: int, language: str, username: str = None) -> bool:
        """Сохраняет язык пользователя (создает пользователя если не существует)"""
        try:
            # Пытаемся обновить существующего пользователя
            query = """
                UPDATE users 
                SET language = %s, username = COALESCE(%s, username), last_seen_at = NOW()
                WHERE tg_id = %s
            """
            result = await self.execute(query, (language, username, tg_id))
            
            # Если пользователь не найден, создаем нового
            if not result:
                insert_query = """
                    INSERT INTO users (tg_id, username, language, first_seen_at, last_seen_at)
                    VALUES (%s, %s, %s, NOW(), NOW())
                    ON CONFLICT (tg_id) DO UPDATE SET
                        language = EXCLUDED.language,
                        username = COALESCE(EXCLUDED.username, users.username),
                        last_seen_at = EXCLUDED.last_seen_at
                """
                await self.execute(insert_query, (tg_id, username, language))
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting user language: {e}")
            return False

    async def get_gmail_usage_today(self, tg_id: int) -> int:
        """Получает количество использованных Gmail-алиасов за сегодня"""
        try:
            today = datetime.now().date()
            query = """
                SELECT count FROM gmail_alias_usage 
                WHERE user_id = %s AND usage_date = %s
            """
            result = await self.execute(query, (tg_id, today), fetch=True)
            
            if result:
                return result[0]['count']
            else:
                return 0
                
        except Exception as e:
            logger.error(f"Error getting Gmail usage: {e}")
            return 0

    async def increment_gmail_usage(self, tg_id: int, count: int) -> bool:
        """Увеличивает счетчик использования Gmail-алиасов на указанное количество"""
        try:
            today = datetime.now().date()
            
            # Используем UPSERT для увеличения счетчика
            query = """
                INSERT INTO gmail_alias_usage (user_id, usage_date, count)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, usage_date) 
                DO UPDATE SET count = gmail_alias_usage.count + %s
            """
            await self.execute(query, (tg_id, today, count, count))
            
            return True
            
        except Exception as e:
            logger.error(f"Error incrementing Gmail usage: {e}")
            return False

    async def get_gmail_remaining_quota(self, tg_id: int, max_daily: int = 10) -> int:
        """Получает оставшуюся квоту Gmail-алиасов на сегодня"""
        try:
            used_today = await self.get_gmail_usage_today(tg_id)
            remaining = max_daily - used_today
            return max(0, remaining)
            
        except Exception as e:
            logger.error(f"Error getting Gmail remaining quota: {e}")
            return 0


class PlatformCookie(Base):
    """Модель для куков платформ"""
    __tablename__ = 'platform_cookies'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(50), nullable=False)
    cookies_json = Column(Text, nullable=False)
    user_agent = Column(Text, nullable=True)
    proxy = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    added_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    success_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    last_used = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)  # Для soft delete
    
    def __repr__(self):
        return f"<PlatformCookie(id={self.id}, platform={self.platform}, active={self.is_active})>"


class GmailAliasUsage(Base):
    """Модель учета использования Gmail-алиасов"""
    __tablename__ = 'gmail_alias_usage'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)  # Telegram user ID
    usage_date = Column(Date, nullable=False)  # Дата использования
    count = Column(Integer, nullable=False, default=0)  # Количество сгенерированных алиасов
    
    def __repr__(self):
        return f"<GmailAliasUsage(user_id={self.user_id}, date={self.usage_date}, count={self.count})>"


class KashmailSession(Base):
    """Модель сессии KashMail"""
    __tablename__ = 'kashmail_sessions'
    
    user_id = Column(BigInteger, primary_key=True)  # Telegram user ID
    address = Column(Text, nullable=False)  # Email адрес
    jwt = Column(Text, nullable=False)  # JWT токен для доступа
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    status = Column(Text, nullable=False, default='active')  # active|waiting|done|burned
    
    def __repr__(self):
        return f"<KashmailSession(user_id={self.user_id}, address={self.address}, status={self.status})>"


class KashmailDailyCounter(Base):
    """Модель дневного счетчика использования KashMail"""
    __tablename__ = 'kashmail_daily_counters'
    
    user_id = Column(BigInteger, nullable=False, primary_key=True)
    day = Column(Date, nullable=False, primary_key=True)
    count = Column(Integer, nullable=False, default=0)
    
    def __repr__(self):
        return f"<KashmailDailyCounter(user_id={self.user_id}, day={self.day}, count={self.count})>"
