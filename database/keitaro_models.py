"""
SQLAlchemy модели для интеграции с Keitaro
"""

from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import (
    Column, Integer, BigInteger, String, DateTime, Boolean, 
    ForeignKey, Text, JSON, Enum, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from database.models import Base


class MatchByType(PyEnum):
    """Типы сопоставления для маршрутизации"""
    CAMPAIGN_ID = "campaign_id"
    SOURCE = "source"  
    ANY = "any"


class KeitaroProfile(Base):
    """Профиль интеграции с Keitaro для пользователя"""
    __tablename__ = 'keitaro_profiles'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_user_id = Column(BigInteger, nullable=False, index=True)  # Telegram user ID
    secret = Column(String(64), unique=True, nullable=False, index=True)  # Секретный токен для postback
    enabled = Column(Boolean, nullable=False, default=True)
    
    # Настройки доставки по умолчанию
    default_chat_id = Column(BigInteger, nullable=False)
    default_topic_id = Column(Integer, nullable=True)  # Thread ID для супергрупп
    
    # Настройки защиты
    rate_limit_rps = Column(Integer, nullable=False, default=27)  # Макс запросов в секунду
    dedup_ttl_sec = Column(Integer, nullable=False, default=3600)  # TTL для дедупликации
    
    # Опциональные настройки для pull-режима 
    pull_enabled = Column(Boolean, nullable=False, default=False)
    pull_base_url = Column(Text, nullable=True)  # База URL Keitaro API
    pull_api_key = Column(Text, nullable=True)  # API ключ Keitaro
    pull_filters = Column(JSON, nullable=True)  # Фильтры для pull (status, geo, dates)
    pull_last_check = Column(DateTime, nullable=True)  # Последняя проверка
    
    # Метаданные
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Отношения
    routes = relationship("KeitaroRoute", back_populates="profile", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<KeitaroProfile(id={self.id}, user={self.owner_user_id}, enabled={self.enabled})>"


class KeitaroRoute(Base):
    """Правило маршрутизации для событий Keitaro"""
    __tablename__ = 'keitaro_routes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(Integer, ForeignKey('keitaro_profiles.id', ondelete='CASCADE'), nullable=False)
    
    # Условия сопоставления
    match_by = Column(Enum(MatchByType), nullable=False)
    match_value = Column(Text, nullable=False)  # Exact значение или regex паттерн
    is_regex = Column(Boolean, nullable=False, default=False)  # Флаг для regex
    
    # Куда отправлять
    target_chat_id = Column(BigInteger, nullable=False)
    target_topic_id = Column(Integer, nullable=True)
    
    # Фильтры (опциональные)
    status_filter = Column(JSON, nullable=True)  # Список разрешенных статусов
    geo_filter = Column(JSON, nullable=True)  # Список разрешенных стран
    
    # Приоритет (для сортировки правил)
    priority = Column(Integer, nullable=False, default=100)
    
    # Метаданные
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Отношения
    profile = relationship("KeitaroProfile", back_populates="routes")
    
    __table_args__ = (
        Index('idx_keitaro_route_lookup', 'profile_id', 'match_by', 'match_value'),
        Index('idx_keitaro_route_priority', 'profile_id', 'priority'),
    )
    
    def __repr__(self):
        return f"<KeitaroRoute(id={self.id}, match={self.match_by.value}:{self.match_value})>"


class KeitaroEvent(Base):
    """Логирование событий от Keitaro (для дедупликации и аудита)"""
    __tablename__ = 'keitaro_events'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    profile_id = Column(Integer, ForeignKey('keitaro_profiles.id', ondelete='CASCADE'), nullable=False)
    
    # Идентификатор транзакции для дедупликации
    transaction_id = Column(String(128), nullable=False, index=True)
    
    # Данные события
    status = Column(String(64), nullable=True)
    campaign_id = Column(String(128), nullable=True)
    source = Column(String(128), nullable=True)
    country = Column(String(10), nullable=True)
    revenue = Column(String(64), nullable=True)
    
    # Результат обработки
    processed = Column(Boolean, nullable=False, default=False)
    sent_to_chat_id = Column(BigInteger, nullable=True)
    sent_to_topic_id = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    
    # Метаданные
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_keitaro_event_dedup', 'profile_id', 'transaction_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<KeitaroEvent(tx={self.transaction_id}, status={self.status})>"
