"""
Репозиторий для работы с сессиями KashMail
"""

import logging
from datetime import datetime, date
from typing import Optional, Dict, Any
from database.models import Database, KashmailSession, KashmailDailyCounter

logger = logging.getLogger(__name__)


class KashmailSessionRepository:
    """Репозиторий для работы с сессиями KashMail"""
    
    def __init__(self, database: Database):
        self.db = database
    
    async def create_session(
        self, 
        user_id: int, 
        address: str, 
        jwt: str, 
        expires_at: datetime
    ) -> bool:
        """Создать новую сессию KashMail"""
        try:
            query = """
                INSERT INTO kashmail_sessions (user_id, address, jwt, created_at, expires_at, status)
                VALUES (%s, %s, %s, NOW(), %s, 'active')
                ON CONFLICT (user_id) 
                DO UPDATE SET 
                    address = EXCLUDED.address,
                    jwt = EXCLUDED.jwt,
                    created_at = EXCLUDED.created_at,
                    expires_at = EXCLUDED.expires_at,
                    status = EXCLUDED.status
            """
            await self.db.execute(query, (user_id, address, jwt, expires_at))
            logger.info(f"Created KashMail session for user {user_id}: {address}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create KashMail session: {e}")
            return False
    
    async def get_session(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить активную сессию пользователя"""
        try:
            query = """
                SELECT user_id, address, jwt, created_at, expires_at, status
                FROM kashmail_sessions 
                WHERE user_id = %s AND status != 'burned'
            """
            result = await self.db.execute(query, (user_id,), fetch=True)
            
            if result:
                return result[0]
            return None
            
        except Exception as e:
            logger.error(f"Failed to get KashMail session: {e}")
            return None
    
    async def update_session_status(self, user_id: int, status: str) -> bool:
        """Обновить статус сессии"""
        try:
            query = """
                UPDATE kashmail_sessions 
                SET status = %s 
                WHERE user_id = %s
            """
            await self.db.execute(query, (status, user_id))
            logger.info(f"Updated KashMail session status for user {user_id}: {status}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update KashMail session status: {e}")
            return False
    
    async def burn_session(self, user_id: int) -> bool:
        """Сжечь сессию (пометить как burned)"""
        return await self.update_session_status(user_id, 'burned')
    
    async def delete_session(self, user_id: int) -> bool:
        """Полностью удалить сессию"""
        try:
            query = "DELETE FROM kashmail_sessions WHERE user_id = %s"
            await self.db.execute(query, (user_id,))
            logger.info(f"Deleted KashMail session for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete KashMail session: {e}")
            return False
    
    async def is_session_valid(self, user_id: int) -> bool:
        """Проверить, валидна ли сессия (не истекла и не сожжена)"""
        try:
            query = """
                SELECT 1 FROM kashmail_sessions 
                WHERE user_id = %s 
                AND status NOT IN ('burned', 'done')
                AND expires_at > NOW()
            """
            result = await self.db.execute(query, (user_id,), fetch=True)
            return bool(result)
            
        except Exception as e:
            logger.error(f"Failed to check session validity: {e}")
            return False
    
    async def cleanup_expired_sessions(self) -> int:
        """Очистить истекшие сессии"""
        try:
            query = """
                DELETE FROM kashmail_sessions 
                WHERE expires_at < NOW() OR status = 'burned'
            """
            result = await self.db.execute(query)
            logger.info("Cleaned up expired KashMail sessions")
            return 1  # SQLAlchemy не возвращает количество удаленных строк в этой реализации
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {e}")
            return 0


class KashmailCounterRepository:
    """Репозиторий для работы с дневными счетчиками KashMail"""
    
    def __init__(self, database: Database):
        self.db = database
    
    async def get_daily_usage(self, user_id: int, day: Optional[date] = None) -> int:
        """Получить количество использований за день"""
        if day is None:
            day = datetime.now().date()
        
        try:
            query = """
                SELECT count FROM kashmail_daily_counters 
                WHERE user_id = %s AND day = %s
            """
            result = await self.db.execute(query, (user_id, day), fetch=True)
            
            if result:
                return result[0]['count']
            return 0
            
        except Exception as e:
            logger.error(f"Failed to get daily usage: {e}")
            return 0
    
    async def increment_daily_usage(self, user_id: int, count: int = 1) -> bool:
        """Увеличить счетчик использований за день"""
        today = datetime.now().date()
        
        try:
            query = """
                INSERT INTO kashmail_daily_counters (user_id, day, count)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, day) 
                DO UPDATE SET count = kashmail_daily_counters.count + %s
            """
            await self.db.execute(query, (user_id, today, count, count))
            logger.info(f"Incremented KashMail usage for user {user_id} by {count}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to increment daily usage: {e}")
            return False
    
    async def get_remaining_quota(self, user_id: int, daily_limit: int = 10) -> int:
        """Получить оставшуюся квоту на сегодня"""
        used_today = await self.get_daily_usage(user_id)
        remaining = daily_limit - used_today
        return max(0, remaining)
    
    async def can_create_email(self, user_id: int, daily_limit: int = 10) -> bool:
        """Проверить, может ли пользователь создать еще один email"""
        remaining = await self.get_remaining_quota(user_id, daily_limit)
        return remaining > 0
    
    async def cleanup_old_counters(self, days_to_keep: int = 30) -> int:
        """Очистить старые счетчики (старше указанного количества дней)"""
        try:
            query = """
                DELETE FROM kashmail_daily_counters 
                WHERE day < CURRENT_DATE - INTERVAL '%s days'
            """
            result = await self.db.execute(query, (days_to_keep,))
            logger.info(f"Cleaned up old KashMail counters (older than {days_to_keep} days)")
            return 1
            
        except Exception as e:
            logger.error(f"Failed to cleanup old counters: {e}")
            return 0


class KashmailRepository:
    """Комбинированный репозиторий для KashMail"""
    
    def __init__(self, database: Database):
        self.sessions = KashmailSessionRepository(database)
        self.counters = KashmailCounterRepository(database)
        self.db = database
    
    async def can_user_create_email(
        self, 
        user_id: int, 
        daily_limit: int = 10,
        check_active_session: bool = True
    ) -> tuple[bool, str]:
        """
        Проверить, может ли пользователь создать новый email
        
        Returns:
            tuple[can_create: bool, reason: str]
        """
        try:
            # Проверяем дневной лимит
            if not await self.counters.can_create_email(user_id, daily_limit):
                used_today = await self.counters.get_daily_usage(user_id)
                return False, f"Превышен дневной лимит: {used_today}/{daily_limit}"
            
            # Проверяем наличие активной сессии
            if check_active_session:
                session = await self.sessions.get_session(user_id)
                if session and session['status'] in ['active', 'waiting']:
                    return False, "У вас уже есть активная сессия KashMail"
            
            return True, "OK"
            
        except Exception as e:
            logger.error(f"Failed to check if user can create email: {e}")
            return False, "Ошибка проверки лимитов"
    
    async def create_new_email_session(
        self, 
        user_id: int, 
        address: str, 
        jwt: str, 
        expires_at: datetime
    ) -> bool:
        """Создать новую сессию и увеличить счетчик"""
        try:
            # Создаем сессию
            session_created = await self.sessions.create_session(
                user_id, address, jwt, expires_at
            )
            
            if session_created:
                # Увеличиваем счетчик
                await self.counters.increment_daily_usage(user_id, 1)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to create new email session: {e}")
            return False
    
    async def cleanup_all(self) -> Dict[str, int]:
        """Очистить все старые данные"""
        try:
            expired_sessions = await self.sessions.cleanup_expired_sessions()
            old_counters = await self.counters.cleanup_old_counters(30)
            
            return {
                "expired_sessions": expired_sessions,
                "old_counters": old_counters
            }
            
        except Exception as e:
            logger.error(f"Failed to cleanup KashMail data: {e}")
            return {"expired_sessions": 0, "old_counters": 0}
