"""
Аналитика для бота - метрики и статистика
"""

import logging
from typing import Dict, List, Tuple, Any
from datetime import datetime, timedelta
from database import Database

logger = logging.getLogger(__name__)

class Analytics:
    """Класс для сбора и анализа метрик бота"""

    def __init__(self, database: Database):
        self.db = database

    async def get_dau_wau_mau(self) -> Dict[str, int]:
        """Получает DAU, WAU, MAU (Daily/Weekly/Monthly Active Users)"""
        try:
            # Получаем текущую дату
            now = datetime.now()
            today = now.date()
            week_ago = today - timedelta(days=7)
            month_ago = today - timedelta(days=30)

            # Запрос для подсчета активных пользователей (используем правильные имена полей)
            query = """
                SELECT
                    COUNT(DISTINCT CASE WHEN DATE(last_seen_at) >= %s THEN id END) as dau,
                    COUNT(DISTINCT CASE WHEN DATE(last_seen_at) >= %s THEN id END) as wau,
                    COUNT(DISTINCT CASE WHEN DATE(last_seen_at) >= %s THEN id END) as mau
                FROM users
                WHERE is_blocked = false
            """

            result = await self.db.execute(query, (today, week_ago, month_ago), fetch=True)

            if result:
                return {
                    'DAU': result[0]['dau'] or 0,
                    'WAU': result[0]['wau'] or 0,
                    'MAU': result[0]['mau'] or 0
                }
            else:
                return {'DAU': 0, 'WAU': 0, 'MAU': 0}

        except Exception as e:
            logger.error(f"Error getting DAU/WAU/MAU: {e}")
            return {'DAU': 0, 'WAU': 0, 'MAU': 0}

    async def get_total_users(self) -> Dict[str, int]:
        """Получает общее количество пользователей"""
        try:
            query = """
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN is_blocked = false THEN 1 END) as active,
                    COUNT(CASE WHEN is_blocked = true THEN 1 END) as blocked
                FROM users
            """

            result = await self.db.execute(query, fetch=True)

            if result:
                return {
                    'total': result[0]['total'] or 0,
                    'active': result[0]['active'] or 0,
                    'blocked': result[0]['blocked'] or 0
                }
            else:
                return {'total': 0, 'active': 0, 'blocked': 0}

        except Exception as e:
            logger.error(f"Error getting total users: {e}")
            return {'total': 0, 'active': 0, 'blocked': 0}

    async def get_average_retention(self, days: int, period_days: int = 30) -> float:
        """
        Получает средний retention rate для указанного количества дней

        Args:
            days: Количество дней для расчета (1, 7, 30)
            period_days: Период анализа в днях

        Returns:
            Процент удержания пользователей
        """
        try:
            # Получаем дату начала периода
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=period_days)

            query = """
                WITH user_cohorts AS (
                    SELECT
                        DATE(first_seen_at) as cohort_date,
                        id as user_id,
                        DATE(last_seen_at) as last_active_date
                    FROM users
                    WHERE DATE(first_seen_at) >= %s
                    AND DATE(first_seen_at) <= %s
                    AND is_blocked = false
                ),
                retention_calc AS (
                    SELECT
                        cohort_date,
                        COUNT(DISTINCT user_id) as cohort_size,
                        COUNT(DISTINCT CASE
                            WHEN last_active_date >= cohort_date + INTERVAL '%s days'
                            THEN user_id
                        END) as retained_users
                    FROM user_cohorts
                    GROUP BY cohort_date
                )
                SELECT
                    AVG(CASE
                        WHEN cohort_size > 0
                        THEN (retained_users::float / cohort_size::float) * 100
                        ELSE 0
                    END) as avg_retention
                FROM retention_calc
            """

            result = await self.db.execute(query, (start_date, end_date, days), fetch=True)

            if result:
                return round(result[0]['avg_retention'] or 0, 2)
            else:
                return 0.0

        except Exception as e:
            logger.error(f"Error calculating retention for {days} days: {e}")
            return 0.0

    async def get_churn_rate(self, days: int = 30) -> float:
        """
        Получает churn rate за указанный период

        Args:
            days: Период анализа в днях

        Returns:
            Процент оттока пользователей
        """
        try:
            # Получаем дату начала периода
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)

            query = """
                WITH active_users AS (
                    SELECT id as user_id
                    FROM users
                    WHERE is_blocked = false
                    AND DATE(last_seen_at) >= %s
                ),
                churned_users AS (
                    SELECT id as user_id
                    FROM users
                    WHERE is_blocked = false
                    AND DATE(last_seen_at) < %s
                    AND id IN (SELECT user_id FROM active_users)
                )
                SELECT
                    (COUNT(*)::float / NULLIF((SELECT COUNT(*) FROM active_users), 0)) * 100 as churn_rate
                FROM churned_users
            """

            result = await self.db.execute(query, (start_date, end_date), fetch=True)

            if result:
                return round(result[0]['churn_rate'] or 0, 2)
            else:
                return 0.0

        except Exception as e:
            logger.error(f"Error calculating churn rate: {e}")
            return 0.0

    async def get_feature_usage_stats(self) -> Dict[str, int]:
        """Получает статистику использования функций"""
        try:
            # Статистика по типам операций (если есть таблица логов)
            query = """
                SELECT
                    'uniqueness_tool' as feature,
                    COUNT(*) as usage_count
                FROM uniqueness_logs
                UNION ALL
                SELECT
                    'video_download' as feature,
                    COUNT(*) as usage_count
                FROM download_logs
                UNION ALL
                SELECT
                    'text_hiding' as feature,
                    COUNT(*) as usage_count
                FROM text_hiding_logs
                ORDER BY usage_count DESC
            """

            try:
                result = await self.db.execute(query, fetch=True)

                stats = {}
                for row in result:
                    stats[row['feature']] = row['usage_count']

                return stats

            except Exception:
                # Если таблиц нет, возвращаем заглушки
                return {
                    'uniqueness_tool': 0,
                    'video_download': 0,
                    'text_hiding': 0
                }

        except Exception as e:
            logger.error(f"Error getting feature usage stats: {e}")
            return {}

    async def get_system_performance(self) -> Dict[str, Any]:
        """Получает метрики производительности системы"""
        try:
            # Получаем статистику из очереди задач
            queue_stats = await self._get_queue_stats()

            # Получаем статистику по cookies
            cookies_stats = await self._get_cookies_stats()

            return {
                'queue': queue_stats,
                'cookies': cookies_stats,
                'timestamp': datetime.now()
            }

        except Exception as e:
            logger.error(f"Error getting system performance: {e}")
            return {}

    async def _get_queue_stats(self) -> Dict[str, int]:
        """Получает статистику очереди задач"""
        try:
            # Проверяем таблицу очереди если она есть
            query = """
                SELECT
                    COUNT(*) as total_tasks,
                    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
                    COUNT(CASE WHEN status = 'processing' THEN 1 END) as processing,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed
                FROM task_queue
            """

            try:
                result = await self.db.execute(query, fetch=True)

                if result:
                    return {
                        'total': result[0]['total_tasks'] or 0,
                        'pending': result[0]['pending'] or 0,
                        'processing': result[0]['processing'] or 0,
                        'completed': result[0]['completed'] or 0,
                        'failed': result[0]['failed'] or 0
                    }
                else:
                    return {'total': 0, 'pending': 0, 'processing': 0, 'completed': 0, 'failed': 0}

            except Exception:
                # Если таблицы нет, возвращаем нули
                return {'total': 0, 'pending': 0, 'processing': 0, 'completed': 0, 'failed': 0}

        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return {'total': 0, 'pending': 0, 'processing': 0, 'completed': 0, 'failed': 0}

    async def _get_cookies_stats(self) -> Dict[str, Any]:
        """Получает статистику cookies"""
        try:
            query = """
                SELECT
                    platform,
                    COUNT(*) as total,
                    SUM(CASE WHEN is_active THEN 1 ELSE 0 END) as active,
                    AVG(success_count) as avg_success,
                    AVG(error_count) as avg_errors,
                    MAX(last_used) as last_activity
                FROM platform_cookies
                GROUP BY platform
            """

            try:
                result = await self.db.execute(query, fetch=True)

                stats = {}
                for row in result:
                    stats[row['platform']] = {
                        'total': row['total'],
                        'active': row['active'],
                        'avg_success': round(row['avg_success'] or 0, 1),
                        'avg_errors': round(row['avg_errors'] or 0, 1),
                        'last_activity': row['last_activity']
                    }

                return stats

            except Exception:
                # Если таблицы нет, возвращаем пустой словарь
                return {}

        except Exception as e:
            logger.error(f"Error getting cookies stats: {e}")
            return {}

    async def get_detailed_metrics(self) -> Dict[str, Any]:
        """Получает детальную аналитику для админ панели"""
        try:
            # Получаем базовые метрики
            dau_wau_mau = await self.get_dau_wau_mau()
            total_users = await self.get_total_users()

            # Получаем retention rates
            retention = {
                'D1': await self.get_average_retention(1),
                'D7': await self.get_average_retention(7),
                'D30': await self.get_average_retention(30)
            }

            churn_rate = await self.get_churn_rate()

            # Получаем использование функций
            feature_usage = await self.get_feature_usage_stats()

            # Получаем производительность системы
            performance = await self.get_system_performance()

            return {
                'users': {
                    'dau_wau_mau': dau_wau_mau,
                    'total': total_users,
                    'retention': retention,
                    'churn_rate': churn_rate
                },
                'features': feature_usage,
                'performance': performance
            }

        except Exception as e:
            logger.error(f"Error getting detailed metrics: {e}")
            return {
                'users': {
                    'dau_wau_mau': {'DAU': 0, 'WAU': 0, 'MAU': 0},
                    'total': {'total': 0, 'active': 0, 'blocked': 0},
                    'retention': {'D1': 0, 'D7': 0, 'D30': 0},
                    'churn_rate': 0
                },
                'features': {},
                'performance': {}
            }

    async def get_command_usage(self, days: int = 30) -> List[Tuple[str, int]]:
        """Получает статистику использования команд"""
        try:
            # Используем таблицу events вместо command_logs
            query = """
                SELECT command, COUNT(*) as count
                FROM events
                WHERE ts >= NOW() - INTERVAL '%s days'
                  AND command IS NOT NULL
                  AND command != ''
                GROUP BY command
                ORDER BY count DESC
            """

            try:
                result = await self.db.execute(query, (days,), fetch=True)

                if result:
                    return [(row['command'], row['count']) for row in result]
                else:
                    # Если нет данных в events, возвращаем пустой список
                    return []

            except Exception:
                # Если ошибка запроса, возвращаем пустой список
                return []

        except Exception as e:
            logger.error(f"Error getting command usage: {e}")
            return []

    async def get_new_users(self, days: int = 7) -> List[Tuple[str, int]]:
        """Получает статистику новых пользователей по дням"""
        try:
            query = """
                SELECT
                    DATE(first_seen_at) as date,
                    COUNT(*) as count
                FROM users
                WHERE first_seen_at >= NOW() - INTERVAL '%s days'
                GROUP BY DATE(first_seen_at)
                ORDER BY DATE(first_seen_at) DESC
            """

            result = await self.db.execute(query, (days,), fetch=True)

            if result:
                return [(str(row['date']), row['count']) for row in result]
            else:
                return []

        except Exception as e:
            logger.error(f"Error getting new users: {e}")
            return []

    async def get_hourly_activity(self, days: int = 7) -> List[Tuple[int, int]]:
        """Получает активность пользователей по часам"""
        try:
            query = """
                SELECT
                    EXTRACT(HOUR FROM ts) as hour,
                    COUNT(*) as count
                FROM events
                WHERE ts >= NOW() - INTERVAL '%s days'
                GROUP BY EXTRACT(HOUR FROM ts)
                ORDER BY hour
            """

            result = await self.db.execute(query, (days,), fetch=True)

            if result:
                return [(int(row['hour']), row['count']) for row in result]
            else:
                return []

        except Exception as e:
            logger.error(f"Error getting hourly activity: {e}")
            return []

    async def get_users_for_broadcast(self) -> List[Dict[str, Any]]:
        """Получает список пользователей для рассылки"""
        try:
            query = """
                SELECT 
                    id,
                    tg_id,
                    username,
                    first_seen_at,
                    last_seen_at,
                    is_blocked
                FROM users
                WHERE is_blocked = false
                ORDER BY last_seen_at DESC
                LIMIT 1000
            """

            result = await self.db.execute(query, fetch=True)

            if result:
                return [
                    {
                        'id': row['id'],
                        'tg_id': row['tg_id'],
                        'username': row['username'],
                        'first_seen': row['first_seen_at'],
                        'last_seen': row['last_seen_at'],
                        'blocked': row['is_blocked']
                    }
                    for row in result
                ]
            else:
                return []

        except Exception as e:
            logger.error(f"Error getting users for broadcast: {e}")
            return []
