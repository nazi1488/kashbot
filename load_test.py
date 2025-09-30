"""
Нагрузочное тестирование бота с использованием Locust
Установка: pip install locust faker
Запуск: locust -f load_test.py --host=https://your-domain.com
"""

import random
import json
import time
from datetime import datetime
from locust import HttpUser, task, between, events
from locust.env import Environment
from locust.stats import stats_printer, stats_history
from faker import Faker

fake = Faker('ru_RU')


class TelegramUpdate:
    """Генератор Telegram обновлений для тестирования"""
    
    def __init__(self, user_id=None):
        self.user_id = user_id or random.randint(100000, 999999)
        self.update_id = random.randint(1000000, 9999999)
        self.message_id = random.randint(1000, 9999)
        self.chat_id = user_id
    
    def start_command(self):
        """Команда /start"""
        return {
            "update_id": self.update_id,
            "message": {
                "message_id": self.message_id,
                "from": {
                    "id": self.user_id,
                    "is_bot": False,
                    "first_name": fake.first_name(),
                    "last_name": fake.last_name(),
                    "username": fake.user_name(),
                    "language_code": "ru"
                },
                "chat": {
                    "id": self.chat_id,
                    "type": "private"
                },
                "date": int(time.time()),
                "text": "/start"
            }
        }
    
    def callback_query(self, callback_data):
        """Нажатие inline кнопки"""
        return {
            "update_id": self.update_id,
            "callback_query": {
                "id": str(random.randint(100000, 999999)),
                "from": {
                    "id": self.user_id,
                    "is_bot": False,
                    "first_name": fake.first_name()
                },
                "message": {
                    "message_id": self.message_id,
                    "chat": {"id": self.chat_id, "type": "private"},
                    "date": int(time.time())
                },
                "data": callback_data
            }
        }
    
    def text_message(self, text):
        """Текстовое сообщение"""
        return {
            "update_id": self.update_id,
            "message": {
                "message_id": self.message_id,
                "from": {
                    "id": self.user_id,
                    "is_bot": False,
                    "first_name": fake.first_name()
                },
                "chat": {
                    "id": self.chat_id,
                    "type": "private"
                },
                "date": int(time.time()),
                "text": text
            }
        }
    
    def document_message(self, file_size_mb=5):
        """Сообщение с документом"""
        return {
            "update_id": self.update_id,
            "message": {
                "message_id": self.message_id,
                "from": {
                    "id": self.user_id,
                    "is_bot": False,
                    "first_name": fake.first_name()
                },
                "chat": {
                    "id": self.chat_id,
                    "type": "private"
                },
                "date": int(time.time()),
                "document": {
                    "file_name": f"test_video_{random.randint(1, 100)}.mp4",
                    "mime_type": "video/mp4",
                    "file_id": fake.sha256(),
                    "file_unique_id": fake.sha1(),
                    "file_size": file_size_mb * 1024 * 1024
                }
            }
        }


class BotUser(HttpUser):
    """Виртуальный пользователь бота"""
    
    wait_time = between(1, 3)  # Пауза между запросами
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id = random.randint(100000, 999999)
        self.update_gen = TelegramUpdate(self.user_id)
        self.webhook_secret = "test_secret_token"  # Должен совпадать с реальным
    
    def on_start(self):
        """Инициализация пользователя"""
        # Отправляем /start
        self.send_update(self.update_gen.start_command())
    
    @task(5)
    def browse_menu(self):
        """Просмотр главного меню"""
        # Проверяем подписку
        self.send_update(self.update_gen.callback_query("check_subscription"))
        
        # Переходим в меню
        menu_items = [
            "uniqueness_tool",
            "hide_text", 
            "smart_compress",
            "video_downloader",
            "roi_calculator"
        ]
        
        selected = random.choice(menu_items)
        self.send_update(self.update_gen.callback_query(selected))
    
    @task(3)
    def roi_calculator_flow(self):
        """Тестирование ROI калькулятора"""
        # Начинаем расчет
        self.send_update(self.update_gen.callback_query("roi_calculator"))
        time.sleep(0.5)
        
        self.send_update(self.update_gen.callback_query("roi_start"))
        time.sleep(0.5)
        
        # Вводим данные
        test_data = [
            str(random.randint(500, 5000)),      # Расход
            str(random.randint(1000, 10000)),    # Доход
            str(random.randint(10000, 100000)),  # Показы
            str(random.randint(100, 5000)),      # Клики
            str(random.randint(10, 500)),        # Лиды
            str(random.randint(5, 100))          # Продажи
        ]
        
        for value in test_data:
            self.send_update(self.update_gen.text_message(value))
            time.sleep(0.3)
    
    @task(2)
    def hide_text_flow(self):
        """Тестирование скрытия текста"""
        self.send_update(self.update_gen.callback_query("hide_text"))
        time.sleep(0.5)
        
        # Отправляем текст
        test_text = fake.text(max_nb_chars=200)
        self.send_update(self.update_gen.text_message(test_text))
    
    @task(4)
    def video_download_flow(self):
        """Тестирование скачивания видео"""
        self.send_update(self.update_gen.callback_query("video_downloader"))
        time.sleep(0.5)
        
        # Отправляем URL
        test_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.tiktok.com/@test/video/1234567890",
            "https://www.instagram.com/p/ABC123/"
        ]
        
        url = random.choice(test_urls)
        self.send_update(self.update_gen.text_message(url))
        time.sleep(0.5)
        
        # Выбираем действие
        action = random.choice(["download_video", "download_audio"])
        self.send_update(self.update_gen.callback_query(action))
    
    @task(6)
    def uniqueness_heavy_flow(self):
        """Тестирование уникализации (тяжелая операция)"""
        self.send_update(self.update_gen.callback_query("uniqueness_tool"))
        time.sleep(0.5)
        
        # Количество копий
        copies = random.randint(2, 5)
        self.send_update(self.update_gen.text_message(str(copies)))
        time.sleep(0.5)
        
        # Отправляем документ
        file_size = random.randint(5, 50)  # MB
        self.send_update(self.update_gen.document_message(file_size))
    
    @task(4)
    def compress_flow(self):
        """Тестирование сжатия"""
        self.send_update(self.update_gen.callback_query("smart_compress"))
        time.sleep(0.5)
        
        # Отправляем файл
        file_size = random.randint(10, 100)  # MB
        self.send_update(self.update_gen.document_message(file_size))
    
    @task(1)
    def health_check(self):
        """Проверка health endpoint"""
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")
    
    def send_update(self, update_data):
        """Отправка обновления на webhook"""
        headers = {
            "Content-Type": "application/json",
            "X-Telegram-Bot-Api-Secret-Token": self.webhook_secret
        }
        
        with self.client.post(
            "/telegram/webhook",
            json=update_data,
            headers=headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Webhook failed: {response.status_code}")


class AdminUser(HttpUser):
    """Админ пользователь для тестирования мониторинга"""
    
    wait_time = between(5, 10)
    weight = 1  # Меньший вес, чем у обычных пользователей
    
    @task
    def check_metrics(self):
        """Проверка метрик"""
        self.client.get("/metrics")
    
    @task
    def check_flower(self):
        """Проверка Flower мониторинга"""
        auth = ("admin", "admin")  # Замените на реальные credentials
        self.client.get("/flower/", auth=auth)


# Дополнительные настройки для отчетов
@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """Инициализация тестирования"""
    print(f"Starting load test at {datetime.now()}")
    print(f"Target host: {environment.host}")


@events.quitting.add_listener
def on_locust_quit(environment, **kwargs):
    """Завершение тестирования"""
    print(f"\nLoad test completed at {datetime.now()}")
    print(f"Total requests: {environment.stats.total.num_requests}")
    print(f"Failure rate: {environment.stats.total.fail_ratio:.2%}")
    print(f"Average response time: {environment.stats.total.avg_response_time:.2f}ms")
    print(f"Median response time: {environment.stats.total.median_response_time:.2f}ms")
    print(f"95%% response time: {environment.stats.total.get_response_time_percentile(0.95):.2f}ms")


# Запуск из командной строки
if __name__ == "__main__":
    from locust import run_single_user
    # Для отладки можно запустить одного пользователя
    run_single_user(BotUser)
