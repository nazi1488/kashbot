"""
Менеджер куков для ротации и управления cookies различных платформ
"""

import json
import random
import logging
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
from database import Database
import hashlib

logger = logging.getLogger(__name__)


class CookiesManager:
    """Менеджер для управления и ротации куков"""
    
    def __init__(self, db: Database):
        self.db = db
        self.cache = {}  # Кеш активных куков
        self.last_cache_update = {}  # Время последнего обновления кеша
        self.cache_ttl = 300  # 5 минут TTL для кеша
        
        # Разрешенные домены для каждой платформы
        self.allowed_domains = {
            'instagram': {
                '.instagram.com', 'instagram.com',
                '.facebook.com', 'facebook.com', 
                '.fbcdn.net', 'fbcdn.net'
            },
            'youtube': {
                '.youtube.com', 'youtube.com',
                '.google.com', 'google.com',
                '.googleapis.com', 'googleapis.com',
                '.googlevideo.com', 'googlevideo.com',
                '.ytimg.com', 'ytimg.com'
            },
            'tiktok': {
                '.tiktok.com', 'tiktok.com',
                '.musical.ly', 'musical.ly',
                '.bytedance.com', 'bytedance.com',
                '.tiktokcdn.com', 'tiktokcdn.com'
            }
        }
    
    def _filter_cookies_by_platform(self, cookies_json: str, platform: str) -> Tuple[str, int]:
        """
        Фильтрует куки, оставляя только разрешенные для платформы домены
        
        Args:
            cookies_json: JSON строка с куками
            platform: Платформа (instagram, youtube, tiktok)
            
        Returns:
            Tuple[str, int]: (отфильтрованный JSON, количество удаленных куков)
        """
        try:
            cookies = json.loads(cookies_json)
            allowed_domains = self.allowed_domains.get(platform, set())
            
            if not allowed_domains:
                logger.warning(f"No allowed domains defined for platform: {platform}")
                return cookies_json, 0
            
            filtered_cookies = []
            removed_count = 0
            
            for cookie in cookies:
                if not isinstance(cookie, dict):
                    continue
                    
                domain = cookie.get('domain', '').lower().strip()
                
                # Проверяем, разрешен ли домен
                is_allowed = False
                
                for allowed_domain in allowed_domains:
                    if domain == allowed_domain or domain.endswith(allowed_domain):
                        is_allowed = True
                        break
                
                if is_allowed:
                    filtered_cookies.append(cookie)
                else:
                    removed_count += 1
                    logger.info(f"🗑️ Filtered out cookie: {cookie.get('name', 'unknown')}@{domain} for {platform}")
            
            if removed_count > 0:
                logger.info(f"🧹 Filtered {removed_count} foreign cookies for {platform}, kept {len(filtered_cookies)} valid cookies")
            
            return json.dumps(filtered_cookies), removed_count
            
        except Exception as e:
            logger.error(f"Error filtering cookies for {platform}: {e}")
            return cookies_json, 0
    
    async def add_cookies(self, platform: str, cookies_data: str, 
                         user_agent: Optional[str] = None,
                         proxy: Optional[str] = None,
                         notes: Optional[str] = None,
                         added_by: Optional[int] = None) -> bool:
        """
        Добавляет новые куки в базу данных
        
        Args:
            platform: Платформа (instagram, youtube, tiktok)
            cookies_data: JSON строка с куками или Netscape формат
            user_agent: User-Agent для этих куков
            proxy: Прокси если используется
            notes: Заметки (например, email аккаунта)
            added_by: ID админа который добавил
            
        Returns:
            True если успешно добавлены
        """
        try:
            # Проверяем формат куков
            if cookies_data.startswith('['):
                # JSON формат
                cookies_json = cookies_data
            else:
                # Netscape формат - конвертируем в JSON
                cookies_json = self._netscape_to_json(cookies_data)
            
            # Проверяем валидность JSON
            json.loads(cookies_json)
            
            # 🧹 АВТОМАТИЧЕСКАЯ ФИЛЬТРАЦИЯ: удаляем посторонние куки
            filtered_cookies_json, removed_count = self._filter_cookies_by_platform(cookies_json, platform)
            
            if removed_count > 0:
                logger.info(f"✅ Auto-filtered {removed_count} foreign cookies for {platform}")
                # Обновляем заметки, указывая что была произведена фильтрация
                if notes:
                    notes = f"{notes} [AUTO-FILTERED: -{removed_count} cookies]"
                else:
                    notes = f"[AUTO-FILTERED: -{removed_count} cookies]"
            
            # Проверяем, остались ли валидные куки после фильтрации
            filtered_cookies = json.loads(filtered_cookies_json)
            if not filtered_cookies:
                logger.error(f"❌ No valid cookies left for {platform} after filtering")
                return False
            
            logger.info(f"📊 Adding {len(filtered_cookies)} filtered cookies for {platform}")
            
            # Вычисляем срок истечения куков
            expires_at = datetime.now() + timedelta(days=30)  # По умолчанию 30 дней
            
            # Сохраняем в БД
            query = """
                INSERT INTO platform_cookies 
                (platform, cookies_json, user_agent, proxy, notes, added_by, expires_at, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            
            result = await self.db.execute(
                query, 
                (platform, filtered_cookies_json, user_agent, proxy, notes, added_by, expires_at, True),
                fetch=True
            )
            
            if result:
                logger.info(f"Added new cookies for {platform}, ID: {result[0]['id']}")
                # Сбрасываем кеш
                if platform in self.cache:
                    del self.cache[platform]
                return True
            
            return False
            
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON format for cookies: {cookies_data[:100]}...")
            return False
        except Exception as e:
            logger.error(f"Error adding cookies: {e}")
            return False
    
    async def get_cookies(self, platform: str, retry_on_error: bool = True) -> Optional[Dict]:
        """
        Получает активные куки для платформы с ротацией
        
        Args:
            platform: Платформа
            retry_on_error: Пробовать другие куки если текущие не работают
            
        Returns:
            Словарь с куками и метаданными или None
        """
        try:
            # Проверяем кеш
            now = datetime.now()
            if platform in self.cache and platform in self.last_cache_update:
                if (now - self.last_cache_update[platform]).seconds < self.cache_ttl:
                    cookies_list = self.cache[platform]
                else:
                    cookies_list = await self._load_active_cookies(platform)
            else:
                cookies_list = await self._load_active_cookies(platform)
            
            if not cookies_list:
                logger.warning(f"No active cookies found for {platform}")
                return None
            
            # Выбираем куки с наименьшим количеством ошибок
            # и которые не использовались недавно
            sorted_cookies = sorted(cookies_list, 
                      key=lambda x: (
                          x.get('error_count', 0), 
                          -(x.get('success_count') or 0),  # Только одна строка с обработкой None
                          x.get('last_used') or datetime.min
                      ))
            
            for cookie_data in sorted_cookies:
                # Проверяем срок истечения
                if cookie_data.get('expires_at') and cookie_data['expires_at'] < now:
                    await self._mark_cookies_inactive(cookie_data['id'])
                    continue
                
                # Обновляем время последнего использования
                await self._update_last_used(cookie_data['id'])
                
                return {
                    'id': cookie_data['id'],
                    'cookies': json.loads(cookie_data['cookies_json']),
                    'user_agent': cookie_data.get('user_agent'),
                    'proxy': cookie_data.get('proxy')
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting cookies for {platform}: {e}")
            return None
    
    async def mark_success(self, cookie_id: int) -> None:
        """Отмечает успешное использование куков"""
        try:
            query = """
                UPDATE platform_cookies 
                SET success_count = COALESCE(success_count, 0) + 1,
                    last_used = NOW()
                WHERE id = %s
            """
            await self.db.execute(query, (cookie_id,))
            
        except Exception as e:
            logger.error(f"Error marking success for cookie {cookie_id}: {e}")
    
    async def mark_error(self, cookie_id: int, error_message: str,
                        deactivate_threshold: int = 5) -> None:
        """
        Отмечает ошибку при использовании куков
        
        Args:
            cookie_id: ID куков
            error_message: Сообщение об ошибке
            deactivate_threshold: Порог ошибок для деактивации
        """
        try:
            # Увеличиваем счетчик ошибок
            query = """
                UPDATE platform_cookies 
                SET error_count = COALESCE(error_count, 0) + 1,
                    last_error = %s,
                    last_used = NOW()
                WHERE id = %s
                RETURNING COALESCE(error_count, 0) as error_count
            """
            result = await self.db.execute(query, (error_message, cookie_id), fetch=True)
            
            if result and result[0]['error_count'] >= deactivate_threshold:
                # Деактивируем куки если слишком много ошибок
                await self._mark_cookies_inactive(cookie_id)
                logger.warning(f"Cookies {cookie_id} deactivated due to {result[0]['error_count']} errors")
                
        except Exception as e:
            logger.error(f"Error marking error for cookie {cookie_id}: {e}")
    
    async def get_statistics(self) -> Dict:
        """Получает статистику по кукам"""
        try:
            query = """
                SELECT 
                    platform,
                    COUNT(*) as total,
                    SUM(CASE WHEN is_active AND deleted_at IS NULL THEN 1 ELSE 0 END) as active,
                    SUM(COALESCE(success_count, 0)) as total_success,
                    SUM(COALESCE(error_count, 0)) as total_errors,
                    MAX(last_used) as last_activity
                FROM platform_cookies
                WHERE deleted_at IS NULL
                GROUP BY platform
            """
            
            result = await self.db.execute(query, fetch=True)
            
            stats = {}
            for row in result:
                stats[row['platform']] = {
                    'total': row['total'],
                    'active': row['active'],
                    'total_success': row['total_success'] or 0,
                    'total_errors': row['total_errors'] or 0,
                    'last_activity': row['last_activity']
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting cookies statistics: {e}")
            return {}
    
    async def cleanup_expired(self) -> int:
        """Очищает истекшие куки (мягкое удаление)"""
        try:
            query = """
                UPDATE platform_cookies
                SET is_active = FALSE, deleted_at = NOW()
                WHERE expires_at < NOW() AND is_active = TRUE AND deleted_at IS NULL
                RETURNING id
            """
            
            result = await self.db.execute(query, fetch=True)
            count = len(result) if result else 0
            
            if count > 0:
                logger.info(f"Deactivated {count} expired cookies")
                # Сбрасываем кеш
                self.cache.clear()
                
            return count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired cookies: {e}")
            return 0
    
    async def _load_active_cookies(self, platform: str) -> List[Dict]:
        """Загружает активные куки из БД"""
        try:
            query = """
                SELECT id, cookies_json, user_agent, proxy, 
                       COALESCE(error_count, 0) as error_count, 
                       COALESCE(success_count, 0) as success_count, 
                       last_used, expires_at
                FROM platform_cookies
                WHERE platform = %s AND is_active = TRUE AND deleted_at IS NULL
                ORDER BY COALESCE(error_count, 0) ASC, COALESCE(success_count, 0) DESC
            """
            
            result = await self.db.execute(query, (platform,), fetch=True)
            
            if result:
                self.cache[platform] = result
                self.last_cache_update[platform] = datetime.now()
                return result
            
            return []
            
        except Exception as e:
            logger.error(f"Error loading cookies for {platform}: {e}")
            return []
    
    async def _update_last_used(self, cookie_id: int) -> None:
        """Обновляет время последнего использования"""
        try:
            query = "UPDATE platform_cookies SET last_used = NOW() WHERE id = %s"
            await self.db.execute(query, (cookie_id,))
        except Exception as e:
            logger.error(f"Error updating last_used for cookie {cookie_id}: {e}")
    
    async def _mark_cookies_inactive(self, cookie_id: int) -> None:
        """Деактивирует куки"""
        try:
            query = "UPDATE platform_cookies SET is_active = FALSE WHERE id = %s"
            await self.db.execute(query, (cookie_id,))
            # Сбрасываем кеш
            self.cache.clear()
        except Exception as e:
            logger.error(f"Error deactivating cookie {cookie_id}: {e}")
    
    def _netscape_to_json(self, netscape_data: str) -> str:
        """Конвертирует Netscape формат куков в JSON"""
        cookies = []
        
        for line in netscape_data.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            parts = line.split('\t')
            if len(parts) != 7:
                continue
            
            domain, _, path, secure, expiry, name, value = parts
            
            cookie = {
                'domain': domain,
                'path': path,
                'secure': secure.upper() == 'TRUE',
                'expirationDate': float(expiry) if expiry != '0' else 0,
                'name': name,
                'value': value,
                'hostOnly': False,
                'httpOnly': False
            }
            
            cookies.append(cookie)
        
        return json.dumps(cookies)
    
    def json_to_netscape(self, json_cookies: str) -> str:
        """Конвертирует JSON куки в Netscape формат"""
        try:
            cookies = json.loads(json_cookies)
            lines = ['# Netscape HTTP Cookie File\n']
            
            for cookie in cookies:
                domain = cookie.get('domain', '')
                path = cookie.get('path', '/')
                secure = 'TRUE' if cookie.get('secure', False) else 'FALSE'
                expiry = str(int(cookie.get('expirationDate', 0)))
                name = cookie.get('name', '')
                value = cookie.get('value', '')
                
                line = f"{domain}\tTRUE\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n"
                lines.append(line)
            
            return ''.join(lines)
            
        except Exception as e:
            logger.error(f"Error converting JSON to Netscape: {e}")
            return ""

    async def delete_cookie(self, cookie_id: int) -> bool:
        """Мягко удаляет куки по ID (soft delete)"""
        try:
            query = "UPDATE platform_cookies SET is_active = FALSE, deleted_at = NOW() WHERE id = %s"
            result = await self.db.execute(query, (cookie_id,))
            self.cache.clear()  # Сбрасываем кеш
            logger.info(f"Soft deleted cookie ID: {cookie_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting cookie {cookie_id}: {e}")
            return False
    
    async def delete_cookies_by_platform(self, platform: str) -> int:
        """Мягко удаляет все куки для платформы (soft delete)"""
        try:
            query = "UPDATE platform_cookies SET is_active = FALSE, deleted_at = NOW() WHERE platform = %s"
            result = await self.db.execute(query, (platform,))
            self.cache.clear()  # Сбрасываем кеш
            count = result.rowcount if hasattr(result, 'rowcount') else 0
            logger.info(f"Soft deleted {count} cookies for platform {platform}")
            return count
        except Exception as e:
            logger.error(f"Error deleting cookies for platform {platform}: {e}")
            return 0
    
    async def get_cookies_list(self, platform: str) -> List[Dict]:
        """Получает список всех куков для платформы (включая удаленные)"""
        try:
            query = """
                SELECT id, platform, notes, added_by, created_at, 
                       expires_at, is_active, error_count, success_count, last_used, deleted_at
                FROM platform_cookies
                WHERE platform = %s
                ORDER BY created_at DESC
            """
            result = await self.db.execute(query, (platform,), fetch=True)
            return result if result else []
        except Exception as e:
            logger.error(f"Error getting cookies list for {platform}: {e}")
            return []
        """Конвертирует JSON куки в Netscape формат"""
        try:
            cookies = json.loads(json_cookies)
            lines = ['# Netscape HTTP Cookie File\n']
            
            for cookie in cookies:
                domain = cookie.get('domain', '')
                path = cookie.get('path', '/')
                secure = 'TRUE' if cookie.get('secure', False) else 'FALSE'
                expiry = str(int(cookie.get('expirationDate', 0)))
                name = cookie.get('name', '')
                value = cookie.get('value', '')
                
                line = f"{domain}\tTRUE\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n"
                lines.append(line)
            
            return ''.join(lines)
            
        except Exception as e:
            logger.error(f"Error converting JSON to Netscape: {e}")
            return ""


class FingerprintGenerator:
    """Генератор отпечатков браузера для обхода детекции"""
    
    @staticmethod
    def generate(platform: str) -> Dict:
        """
        Генерирует отпечаток браузера для платформы
        
        Returns:
            Словарь с user-agent, headers и другими параметрами
        """
        
        # Списки User-Agent'ов для разных платформ
        USER_AGENTS = {
            'instagram': [
                'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
                'Instagram 292.0.0.16.107 Android (33/13; 420dpi; 1080x2400; samsung; SM-S911B; b0s; exynos2200; en_US; 499775603)',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            ],
            'tiktok': [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            ],
            'youtube': [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            ]
        }
        
        # Языки и их веса
        LANGUAGES = ['en-US', 'en-GB', 'en', 'ru-RU', 'ru', 'de-DE', 'fr-FR', 'es-ES']
        
        # Разрешения экранов
        SCREEN_RESOLUTIONS = ['1920x1080', '1366x768', '1440x900', '1536x864', '1280x720']
        
        # Выбираем случайные параметры
        user_agent = random.choice(USER_AGENTS.get(platform, USER_AGENTS['tiktok']))
        language = random.choice(LANGUAGES)
        resolution = random.choice(SCREEN_RESOLUTIONS)
        
        # Генерируем заголовки
        headers = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': f'{language},en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        }
        
        # Специфичные заголовки для платформ
        if platform == 'instagram':
            headers.update({
                'X-IG-App-ID': '936619743392459',
                'X-IG-WWW-Claim': '0',
                'X-Requested-With': 'XMLHttpRequest'
            })
        elif platform == 'tiktok':
            headers.update({
                'Referer': 'https://www.tiktok.com/',
            })
        elif platform == 'youtube':
            headers.update({
                'X-Youtube-Client-Name': '1',
                'X-Youtube-Client-Version': '2.20240109.01.00'
            })
        
        return {
            'user_agent': user_agent,
            'headers': headers,
            'language': language,
            'resolution': resolution,
            'platform': platform
        }
