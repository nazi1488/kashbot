"""
Модуль для трекинга событий и сессий пользователей
"""

import logging
from datetime import datetime, timedelta
from uuid import uuid4
from typing import Optional, Dict
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy.orm import Session as DBSession
from .models import User, Event, Session, Database

logger = logging.getLogger(__name__)


class EventTracker:
    """Класс для отслеживания событий пользователей"""
    
    def __init__(self, database: Database):
        self.db = database
        self.session_timeout = timedelta(minutes=30)  # Сессия считается завершенной после 30 минут неактивности
        
    def get_or_create_user(self, db_session: DBSession, tg_id: int, username: Optional[str] = None) -> User:
        """Получить или создать пользователя"""
        user = db_session.query(User).filter_by(tg_id=tg_id).first()
        
        if not user:
            user = User(
                tg_id=tg_id,
                username=username,
                first_seen_at=datetime.utcnow(),
                last_seen_at=datetime.utcnow()
            )
            db_session.add(user)
            db_session.commit()
            logger.info(f"Created new user: {tg_id} ({username})")
        else:
            # Обновляем last_seen_at и username
            user.last_seen_at = datetime.utcnow()
            if username and user.username != username:
                user.username = username
            db_session.commit()
            
        return user
    
    def get_or_create_session(self, db_session: DBSession, user: User, context: ContextTypes.DEFAULT_TYPE) -> Session:
        """Получить или создать сессию для пользователя"""
        # Проверяем, есть ли активная сессия в контексте
        session_id = context.user_data.get('session_id')
        
        if session_id:
            session = db_session.query(Session).filter_by(id=session_id).first()
            if session and (datetime.utcnow() - session.started_at) < self.session_timeout:
                # Сессия еще активна
                return session
        
        # Создаем новую сессию
        session = Session(
            id=uuid4(),
            user_id=user.id,
            started_at=datetime.utcnow()
        )
        db_session.add(session)
        db_session.commit()
        
        # Сохраняем ID сессии в контексте
        context.user_data['session_id'] = session.id
        logger.info(f"Created new session for user {user.tg_id}: {session.id}")
        
        return session
    
    async def track_event(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        event_type: str,
        command: Optional[str] = None
    ):
        """Отслеживать событие"""
        try:
            if not update.effective_user:
                return
            
            with self.db.get_session() as db_session:
                # Получаем или создаем пользователя
                user = self.get_or_create_user(
                    db_session,
                    update.effective_user.id,
                    update.effective_user.username
                )
                
                # Получаем или создаем сессию
                session = self.get_or_create_session(db_session, user, context)
                
                # Создаем событие
                event = Event(
                    user_id=user.id,
                    ts=datetime.utcnow(),
                    event_type=event_type,
                    command=command,
                    session_id=session.id
                )
                db_session.add(event)
                
                # Обновляем счетчик событий в сессии
                session.events_count += 1
                session.duration_seconds = int((datetime.utcnow() - session.started_at).total_seconds())
                
                db_session.commit()
                logger.debug(f"Tracked event: {event_type} - {command} for user {user.tg_id}")
                
        except Exception as e:
            logger.error(f"Error tracking event: {e}")
    
    async def end_session(self, context: ContextTypes.DEFAULT_TYPE):
        """Завершить текущую сессию"""
        session_id = context.user_data.get('session_id')
        if not session_id:
            return
        
        try:
            with self.db.get_session() as db_session:
                session = db_session.query(Session).filter_by(id=session_id).first()
                if session and not session.ended_at:
                    session.ended_at = datetime.utcnow()
                    session.duration_seconds = int((session.ended_at - session.started_at).total_seconds())
                    db_session.commit()
                    logger.info(f"Ended session {session_id}")
                    
                # Удаляем из контекста
                context.user_data.pop('session_id', None)
                
        except Exception as e:
            logger.error(f"Error ending session: {e}")
    
    def close_old_sessions(self):
        """Закрыть старые незавершенные сессии"""
        try:
            with self.db.get_session() as db_session:
                cutoff_time = datetime.utcnow() - self.session_timeout
                
                old_sessions = db_session.query(Session).filter(
                    Session.ended_at.is_(None),
                    Session.started_at < cutoff_time
                ).all()
                
                for session in old_sessions:
                    session.ended_at = session.started_at + self.session_timeout
                    session.duration_seconds = int(self.session_timeout.total_seconds())
                    
                db_session.commit()
                
                if old_sessions:
                    logger.info(f"Closed {len(old_sessions)} old sessions")
                    
        except Exception as e:
            logger.error(f"Error closing old sessions: {e}")


# Декоратор для автоматического трекинга команд
def track_command(command_name: str):
    """Декоратор для отслеживания команд"""
    def decorator(func):
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            # Трекаем событие
            if hasattr(context.bot_data, 'event_tracker'):
                await context.bot_data['event_tracker'].track_event(
                    update, context, 'command', command_name
                )
            
            # Вызываем оригинальную функцию
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    return decorator
