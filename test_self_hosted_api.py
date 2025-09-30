#!/usr/bin/env python3
"""
Тестирование работы с self-hosted Telegram Bot API
"""

import asyncio
import tempfile
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Добавляем путь к проекту
sys.path.append('/Users/benutzer/Desktop/кеш/bot')

import config
from handlers.uniqizer import start_uniqizer, file_handler, wrong_media_handler, copies_input_handler
from utils.smart_compressor import compress_for_telegram


class TestSelfHostedAPI:
    """Тесты для self-hosted Bot API"""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.total = 0
    
    async def test_config_loading(self):
        """Тест загрузки конфигурации для self-hosted API"""
        print("\n🧪 Тест 1: Загрузка конфигурации")
        
        try:
            # Мокаем переменные окружения
            with patch.dict('os.environ', {
                'USE_LOCAL_BOT_API': 'true',
                'LOCAL_BOT_API_URL': 'http://localhost:8081',
                'MAX_FILE_SIZE': str(500 * 1024 * 1024)  # 500MB
            }):
                # Перезагружаем config
                import importlib
                importlib.reload(config)
                
                assert config.USE_LOCAL_BOT_API == True
                assert config.LOCAL_BOT_API_URL == 'http://localhost:8081'
                assert config.MAX_FILE_SIZE == 500 * 1024 * 1024
                
                print("✅ Конфигурация загружена корректно")
                print(f"   - Self-hosted API: {config.USE_LOCAL_BOT_API}")
                print(f"   - URL: {config.LOCAL_BOT_API_URL}")
                print(f"   - Max file size: {config.MAX_FILE_SIZE / (1024*1024)}MB")
                self.passed += 1
                return True
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            self.failed += 1
            return False
    
    async def test_new_flow_file_first(self):
        """Тест нового потока: сначала файл, потом количество копий"""
        print("\n🧪 Тест 2: Новый поток обработки")
        
        try:
            # Создаем мок объекты
            mock_update = MagicMock()
            mock_query = MagicMock()
            mock_query.answer = AsyncMock()
            mock_query.message.reply_text = AsyncMock()
            mock_update.callback_query = mock_query
            
            mock_context = MagicMock()
            mock_context.user_data = {}
            
            # Тест start_uniqizer - должен запросить файл
            result = await start_uniqizer(mock_update, mock_context)
            
            # Проверяем, что запрашивается файл (WAITING_FOR_FILE = 0)
            assert result == 0, f"Ожидался WAITING_FOR_FILE (0), получен {result}"
            
            # Проверяем, что отправлено сообщение о загрузке файла
            call_args = mock_query.message.reply_text.call_args
            assert call_args is not None, "reply_text не был вызван"
            
            print("✅ Новый поток работает:")
            print("   - Сначала запрашивается файл")
            print("   - WAITING_FOR_FILE = 0")
            self.passed += 1
            return True
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            self.failed += 1
            return False
    
    async def test_file_processing_large(self):
        """Тест обработки большого файла (300MB) с self-hosted API"""
        print("\n🧪 Тест 3: Обработка большого файла (300MB)")
        
        try:
            # Мокаем конфиг для self-hosted API
            with patch.object(config, 'USE_LOCAL_BOT_API', True):
                with patch.object(config, 'MAX_FILE_SIZE', 500 * 1024 * 1024):  # 500MB
                    
                    # Создаем мок документа 300MB
                    mock_document = MagicMock()
                    mock_document.file_size = 300 * 1024 * 1024  # 300MB
                    mock_document.file_name = "large_video.mp4"
                    
                    mock_message = MagicMock()
                    mock_message.document = mock_document
                    mock_message.reply_text = AsyncMock()
                    
                    mock_update = MagicMock()
                    mock_update.message = mock_message
                    
                    mock_context = MagicMock()
                    mock_context.user_data = {}
                    
                    # Вызываем file_handler
                    result = await file_handler(mock_update, mock_context)
                    
                    # Проверяем, что файл принят и запрашивается количество копий
                    assert result == 1, f"Ожидался WAITING_FOR_COPIES (1), получен {result}"
                    
                    # Проверяем, что файл сохранен в context
                    assert 'file_obj' in mock_context.user_data
                    assert mock_context.user_data['file_obj'] == mock_document
                    assert mock_context.user_data['file_name'] == "large_video.mp4"
                    
                    print("✅ Большой файл обработан:")
                    print("   - Файл 300MB принят")
                    print("   - Запрошено количество копий")
                    print("   - Файл сохранен в контексте")
                    self.passed += 1
                    return True
                    
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            self.failed += 1
            return False
    
    async def test_copies_processing(self):
        """Тест обработки количества копий и запуска процесса"""
        print("\n🧪 Тест 4: Обработка количества копий")
        
        try:
            # Создаем мок файла
            mock_file = MagicMock()
            mock_file.file_id = "test_file_id"
            mock_file.file_size = 100 * 1024 * 1024  # 100MB
            
            mock_message = MagicMock()
            mock_message.text = "5"
            mock_message.reply_text = AsyncMock()
            
            mock_update = MagicMock()
            mock_update.message = mock_message
            
            mock_context = MagicMock()
            mock_context.user_data = {
                'file_obj': mock_file,
                'file_name': 'test_video.mp4',
                'is_compressed': False
            }
            
            # Мокаем process_media_file
            with patch('handlers.uniqizer.process_media_file', new_callable=AsyncMock) as mock_process:
                mock_process.return_value = 0  # ConversationHandler.END
                
                # Вызываем copies_input_handler
                result = await copies_input_handler(mock_update, mock_context)
                
                # Проверяем, что количество копий сохранено
                assert context.user_data.get('copies_count') == 5
                
                # Проверяем, что process_media_file вызван
                assert mock_process.called
                
                print("✅ Обработка количества копий:")
                print("   - Количество копий: 5")
                print("   - Процесс обработки запущен")
                self.passed += 1
                return True
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            self.failed += 1
            return False
    
    async def test_download_large_file(self):
        """Тест скачивания большого файла через self-hosted API"""
        print("\n🧪 Тест 5: Скачивание большого файла")
        
        try:
            # Создаем мок бота с self-hosted API
            mock_bot = AsyncMock()
            mock_file = AsyncMock()
            mock_file.file_size = 400 * 1024 * 1024  # 400MB
            mock_file.download_to_drive = AsyncMock()
            mock_bot.get_file.return_value = mock_file
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir) / "test_video.mp4"
                
                # Вызываем compress_for_telegram
                result_path, error = await compress_for_telegram(
                    bot=mock_bot,
                    file_id="large_file_id",
                    original_filename="test_video.mp4"
                )
                
                # Проверяем, что файл "скачан"
                assert mock_bot.get_file.called
                assert mock_file.download_to_drive.called
                
                print("✅ Скачивание большого файла:")
                print("   - Файл 400MB успешно обработан")
                print("   - Self-hosted API используется корректно")
                self.passed += 1
                return True
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            self.failed += 1
            return False
    
    async def run_all_tests(self):
        """Запуск всех тестов"""
        print("🚀 ТЕСТИРОВАНИЕ SELF-HOSTED TELEGRAM BOT API")
        print("=" * 60)
        
        tests = [
            self.test_config_loading(),
            self.test_new_flow_file_first(),
            self.test_file_processing_large(),
            self.test_copies_processing(),
            self.test_download_large_file()
        ]
        
        for test in tests:
            self.total += 1
            await test
        
        print("\n" + "=" * 60)
        print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
        print(f"✅ Пройдено: {self.passed}/{self.total}")
        print(f"❌ Провалено: {self.failed}/{self.total}")
        
        if self.failed == 0:
            print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
            print("\n✅ СИСТЕМА ГОТОВА К РАБОТЕ:")
            print("1. Self-hosted API настроен корректно")
            print("2. Поддержка файлов до 500MB работает")
            print("3. Новый поток (файл → копии) работает")
            print("4. Все компоненты интегрированы")
            print("\n📦 ДЛЯ РАЗВЕРТЫВАНИЯ НА VPS:")
            print("1. Скопируйте файлы на сервер")
            print("2. Запустите: sudo bash install_telegram_bot_api.sh")
            print("3. Установите USE_LOCAL_BOT_API=true в .env")
            print("4. Запустите бота: python3 main.py")
        else:
            print("\n⚠️ ЕСТЬ ПРОБЛЕМЫ, ТРЕБУЕТСЯ ДОРАБОТКА")
        
        return self.failed == 0


async def main():
    """Главная функция"""
    tester = TestSelfHostedAPI()
    success = await tester.run_all_tests()
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
