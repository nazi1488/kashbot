"""
Модуль аналитики для расчета метрик
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy import func, and_, or_, distinct
from sqlalchemy.orm import Session as DBSession
from .models import User, Event, Session, Database
import logging

logger = logging.getLogger(__name__)


class Analytics:
    """Класс для расчета аналитических метрик"""
    
    def __init__(self, database: Database):
        self.db = database
    
    def get_active_users(self, period_days: int) -> int:
        """Получить количество активных пользователей за период"""
        with self.db.get_session() as db_session:
            cutoff_date = datetime.utcnow() - timedelta(days=period_days)
            
            count = db_session.query(func.count(distinct(User.id))).join(Event).filter(
                Event.ts >= cutoff_date
            ).scalar()
            
            return count or 0
    
    def get_dau_wau_mau(self) -> Dict[str, int]:
        """Получить DAU, WAU, MAU"""
        return {
            'DAU': self.get_active_users(1),
            'WAU': self.get_active_users(7),
            'MAU': self.get_active_users(30)
        }
    
    def get_retention(self, cohort_days_ago: int, check_day: int) -> float:
        """
        Расчет retention для когорты
        cohort_days_ago - сколько дней назад была когорта
        check_day - на какой день проверяем возвращение (1, 7, 30)
        """
        with self.db.get_session() as db_session:
            # Дата когорты
            cohort_date = datetime.utcnow().date() - timedelta(days=cohort_days_ago)
            cohort_end = cohort_date + timedelta(days=1)
            
            # Пользователи из когорты
            cohort_users = db_session.query(User.id).filter(
                and_(
                    func.date(User.first_seen_at) >= cohort_date,
                    func.date(User.first_seen_at) < cohort_end
                )
            ).all()
            
            cohort_user_ids = [u.id for u in cohort_users]
            
            if not cohort_user_ids:
                return 0.0
            
            # Дата проверки
            check_date = cohort_date + timedelta(days=check_day)
            check_end = check_date + timedelta(days=1)
            
            # Вернувшиеся пользователи
            returned_users = db_session.query(func.count(distinct(Event.user_id))).filter(
                and_(
                    Event.user_id.in_(cohort_user_ids),
                    func.date(Event.ts) >= check_date,
                    func.date(Event.ts) < check_end
                )
            ).scalar()
            
            retention = (returned_users / len(cohort_user_ids)) * 100
            return round(retention, 1)
    
    def get_average_retention(self, retention_day: int, periods: int = 30) -> float:
        """Средний retention за последние N периодов"""
        retentions = []
        
        for days_ago in range(retention_day + 1, retention_day + periods + 1):
            ret = self.get_retention(days_ago, retention_day)
            if ret > 0:  # Учитываем только дни с данными
                retentions.append(ret)
        
        if retentions:
            return round(sum(retentions) / len(retentions), 1)
        return 0.0
    
    def get_command_usage(self, days: int = 30) -> List[Tuple[str, int]]:
        """Получить статистику использования команд"""
        with self.db.get_session() as db_session:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            results = db_session.query(
                Event.command,
                func.count(Event.id).label('count')
            ).filter(
                and_(
                    Event.ts >= cutoff_date,
                    Event.command.isnot(None)
                )
            ).group_by(Event.command).order_by(func.count(Event.id).desc()).all()
            
            return [(cmd, count) for cmd, count in results]
    
    def get_average_session_length(self, days: int = 30) -> Dict[str, float]:
        """Получить среднюю длину сессии"""
        with self.db.get_session() as db_session:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Средняя продолжительность в секундах
            avg_duration = db_session.query(
                func.avg(Session.duration_seconds)
            ).filter(
                and_(
                    Session.started_at >= cutoff_date,
                    Session.ended_at.isnot(None),
                    Session.duration_seconds > 0
                )
            ).scalar()
            
            # Среднее количество событий
            avg_events = db_session.query(
                func.avg(Session.events_count)
            ).filter(
                and_(
                    Session.started_at >= cutoff_date,
                    Session.events_count > 0
                )
            ).scalar()
            
            return {
                'avg_duration_minutes': round(avg_duration / 60, 1) if avg_duration else 0,
                'avg_events_count': round(avg_events, 1) if avg_events else 0
            }
    
    def get_churn_rate(self, days: int = 30) -> float:
        """Расчет churn rate"""
        with self.db.get_session() as db_session:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Всего активных пользователей за период
            total_users = db_session.query(
                func.count(distinct(Event.user_id))
            ).filter(
                Event.ts >= cutoff_date - timedelta(days=days)
            ).scalar()
            
            if not total_users:
                return 0.0
            
            # Пользователи, которые были активны в первой половине периода
            first_half_users = db_session.query(Event.user_id).filter(
                and_(
                    Event.ts >= cutoff_date - timedelta(days=days),
                    Event.ts < cutoff_date - timedelta(days=days//2)
                )
            ).distinct().subquery()
            
            # Из них не вернулись во второй половине
            churned_users = db_session.query(
                func.count(first_half_users.c.user_id)
            ).filter(
                ~first_half_users.c.user_id.in_(
                    db_session.query(Event.user_id).filter(
                        Event.ts >= cutoff_date - timedelta(days=days//2)
                    ).distinct()
                )
            ).scalar()
            
            churn_rate = (churned_users / total_users) * 100
            return round(churn_rate, 1)
    
    def get_new_users(self, days: int = 30) -> List[Tuple[str, int]]:
        """Получить количество новых пользователей по дням"""
        with self.db.get_session() as db_session:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            results = db_session.query(
                func.date(User.first_seen_at).label('date'),
                func.count(User.id).label('count')
            ).filter(
                User.first_seen_at >= cutoff_date
            ).group_by(
                func.date(User.first_seen_at)
            ).order_by(
                func.date(User.first_seen_at).desc()
            ).all()
            
            return [(date.strftime('%Y-%m-%d'), count) for date, count in results]
    
    def get_total_users(self) -> Dict[str, int]:
        """Получить общую статистику по пользователям"""
        with self.db.get_session() as db_session:
            total = db_session.query(func.count(User.id)).scalar()
            blocked = db_session.query(func.count(User.id)).filter(User.is_blocked == True).scalar()
            
            return {
                'total': total or 0,
                'active': (total or 0) - (blocked or 0),
                'blocked': blocked or 0
            }
    
    def get_hourly_activity(self, days: int = 7) -> List[Tuple[int, int]]:
        """Получить активность по часам"""
        with self.db.get_session() as db_session:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            results = db_session.query(
                func.extract('hour', Event.ts).label('hour'),
                func.count(Event.id).label('count')
            ).filter(
                Event.ts >= cutoff_date
            ).group_by(
                func.extract('hour', Event.ts)
            ).order_by(
                func.extract('hour', Event.ts)
            ).all()
            
            return [(int(hour), count) for hour, count in results]
    
    def get_users_for_broadcast(self, segment: Optional[str] = None) -> List[int]:
        """Получить список пользователей для рассылки"""
        with self.db.get_session() as db_session:
            query = db_session.query(User.tg_id).filter(User.is_blocked == False)
            
            if segment == 'active_7d':
                # Активные за последние 7 дней
                cutoff = datetime.utcnow() - timedelta(days=7)
                active_users = db_session.query(Event.user_id).filter(
                    Event.ts >= cutoff
                ).distinct().subquery()
                query = query.filter(User.id.in_(active_users))
                
            elif segment == 'active_30d':
                # Активные за последние 30 дней
                cutoff = datetime.utcnow() - timedelta(days=30)
                active_users = db_session.query(Event.user_id).filter(
                    Event.ts >= cutoff
                ).distinct().subquery()
                query = query.filter(User.id.in_(active_users))
                
            elif segment == 'inactive_7d':
                # Неактивные последние 7 дней
                cutoff = datetime.utcnow() - timedelta(days=7)
                active_users = db_session.query(Event.user_id).filter(
                    Event.ts >= cutoff
                ).distinct()
                query = query.filter(~User.id.in_(active_users))
            
            return [tg_id for tg_id, in query.all()]
