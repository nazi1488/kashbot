#!/usr/bin/env python3
"""
Помощник для работы с системой cookies
"""

import asyncio
import asyncpg
import json
import config
import sys

async def show_menu():
    """Показывает главное меню"""
    print("\n" + "=" * 50)
    print("🍪 ПОМОЩНИК СИСТЕМЫ COOKIES")
    print("=" * 50)
    print("\n1. Проверить статус системы")
    print("2. Добавить cookies из файла")
    print("3. Показать статистику")
    print("4. Очистить истекшие cookies")
    print("5. Выход")
    
    choice = input("\nВыберите действие (1-5): ")
    return choice

async def check_status():
    """Проверяет статус системы"""
    print("\n🔍 Проверка системы...")
    
    try:
        # Преобразуем URL для asyncpg
        db_url = config.DATABASE_URL
        if '+psycopg' in db_url:
            db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')
        
        conn = await asyncpg.connect(db_url)
        
        # Проверяем таблицы
        tables = await conn.fetchval('''
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('platform_cookies', 'download_logs')
        ''')
        
        if tables == 2:
            print("✅ Таблицы созданы")
        else:
            print("❌ Таблицы не найдены. Примените миграции!")
            await conn.close()
            return
        
        # Статистика по платформам
        stats = await conn.fetch('''
            SELECT platform, 
                   COUNT(*) as total,
                   SUM(CASE WHEN is_active THEN 1 ELSE 0 END) as active
            FROM platform_cookies
            GROUP BY platform
        ''')
        
        print("\n📊 Cookies по платформам:")
        for row in stats:
            print(f"   • {row['platform']}: {row['active']}/{row['total']} активных")
        
        if not stats:
            print("   ⚠️ Нет cookies в базе")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

async def add_cookies_from_file():
    """Добавляет cookies из файла"""
    platform = input("\nПлатформа (instagram/tiktok/youtube): ").lower()
    
    if platform not in ['instagram', 'tiktok', 'youtube']:
        print("❌ Неверная платформа!")
        return
    
    file_path = input("Путь к файлу с cookies (JSON): ")
    
    try:
        with open(file_path, 'r') as f:
            cookies_data = f.read()
        
        # Проверяем что это валидный JSON
        json.loads(cookies_data)
        
        # Добавляем в БД
        db_url = config.DATABASE_URL
        if '+psycopg' in db_url:
            db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')
        
        conn = await asyncpg.connect(db_url)
        
        await conn.execute('''
            INSERT INTO platform_cookies 
            (platform, cookies_json, is_active, success_count, error_count)
            VALUES ($1, $2, true, 0, 0)
        ''', platform, cookies_data)
        
        await conn.close()
        
        print(f"✅ Cookies для {platform} добавлены!")
        
    except FileNotFoundError:
        print("❌ Файл не найден!")
    except json.JSONDecodeError:
        print("❌ Неверный формат JSON!")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

async def show_statistics():
    """Показывает статистику"""
    print("\n📊 Статистика системы...")
    
    try:
        db_url = config.DATABASE_URL
        if '+psycopg' in db_url:
            db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')
        
        conn = await asyncpg.connect(db_url)
        
        # Статистика по cookies
        cookies_stats = await conn.fetch('''
            SELECT platform,
                   COUNT(*) as total,
                   SUM(CASE WHEN is_active THEN 1 ELSE 0 END) as active,
                   SUM(success_count) as successes,
                   SUM(error_count) as errors
            FROM platform_cookies
            GROUP BY platform
            ORDER BY platform
        ''')
        
        print("\n🍪 Cookies:")
        for row in cookies_stats:
            print(f"\n{row['platform'].upper()}:")
            print(f"  Всего: {row['total']} (активных: {row['active']})")
            print(f"  Успехов: {row['successes'] or 0}")
            print(f"  Ошибок: {row['errors'] or 0}")
        
        # Статистика по скачиваниям
        downloads_stats = await conn.fetchval('''
            SELECT COUNT(*) FROM download_logs
        ''')
        
        success_rate = await conn.fetchval('''
            SELECT 
                CASE 
                    WHEN COUNT(*) > 0 
                    THEN ROUND(100.0 * SUM(CASE WHEN success THEN 1 ELSE 0 END) / COUNT(*), 2)
                    ELSE 0
                END as rate
            FROM download_logs
        ''')
        
        print(f"\n📥 Скачивания:")
        print(f"  Всего попыток: {downloads_stats}")
        print(f"  Успешность: {success_rate}%")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

async def cleanup_expired():
    """Очищает истекшие cookies"""
    print("\n🗑 Очистка истекших cookies...")
    
    try:
        db_url = config.DATABASE_URL
        if '+psycopg' in db_url:
            db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')
        
        conn = await asyncpg.connect(db_url)
        
        # Деактивируем истекшие
        result = await conn.execute('''
            UPDATE platform_cookies
            SET is_active = FALSE
            WHERE expires_at < NOW() AND is_active = TRUE
        ''')
        
        # Деактивируем с большим количеством ошибок
        result2 = await conn.execute('''
            UPDATE platform_cookies
            SET is_active = FALSE
            WHERE error_count > 5 AND is_active = TRUE
        ''')
        
        await conn.close()
        
        print("✅ Очистка завершена")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

async def main():
    """Главная функция"""
    print("\n" + "=" * 50)
    print("🍪 ПОМОЩНИК СИСТЕМЫ COOKIES")
    print("=" * 50)
    
    while True:
        choice = await show_menu()
        
        if choice == "1":
            await check_status()
        elif choice == "2":
            await add_cookies_from_file()
        elif choice == "3":
            await show_statistics()
        elif choice == "4":
            await cleanup_expired()
        elif choice == "5":
            print("\n👋 До свидания!")
            break
        else:
            print("\n❌ Неверный выбор!")
        
        input("\nНажмите Enter для продолжения...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Выход...")
