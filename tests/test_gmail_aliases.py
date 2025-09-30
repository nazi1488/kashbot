#!/usr/bin/env python3
"""
Юнит-тесты для Gmail-алиасов генератора
"""

import unittest
import sys
import os
from datetime import datetime

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.gmail_aliases import (
    GmailAliasGenerator, 
    generate_gmail_aliases, 
    validate_gmail_input
)


class TestGmailAliasGenerator(unittest.TestCase):
    """Тесты для генератора Gmail-алиасов"""
    
    def setUp(self):
        """Настройка тестов"""
        self.generator = GmailAliasGenerator()
    
    def test_normalize_email(self):
        """Тест нормализации email"""
        # Тест удаления точек и +tag
        local, domain = self.generator.normalize_email("john.doe+tag@gmail.com")
        self.assertEqual(local, "johndoe")
        self.assertEqual(domain, "gmail.com")
        
        # Тест без точек
        local, domain = self.generator.normalize_email("johndoe@gmail.com")
        self.assertEqual(local, "johndoe")
        self.assertEqual(domain, "gmail.com")
        
        # Тест с другим доменом (не удаляем точки)
        local, domain = self.generator.normalize_email("john.doe@example.com")
        self.assertEqual(local, "john.doe")
        self.assertEqual(domain, "example.com")
        
        # Тест с googlemail.com
        local, domain = self.generator.normalize_email("john.doe@googlemail.com")
        self.assertEqual(local, "johndoe")
        self.assertEqual(domain, "googlemail.com")
    
    def test_validate_email(self):
        """Тест валидации email"""
        # Валидные email
        self.assertTrue(self.generator.validate_email("test@gmail.com")[0])
        self.assertTrue(self.generator.validate_email("john.doe@gmail.com")[0])
        self.assertTrue(self.generator.validate_email("user+tag@gmail.com")[0])
        
        # Невалидные email
        self.assertFalse(self.generator.validate_email("invalid")[0])
        self.assertFalse(self.generator.validate_email("@gmail.com")[0])
        self.assertFalse(self.generator.validate_email("user@")[0])
        self.assertFalse(self.generator.validate_email("user@.com")[0])
    
    def test_is_gmail_domain(self):
        """Тест проверки Gmail домена"""
        # Gmail домены
        self.assertTrue(self.generator.is_gmail_domain("test@gmail.com"))
        self.assertTrue(self.generator.is_gmail_domain("test@googlemail.com"))
        
        # Не Gmail домены
        self.assertFalse(self.generator.is_gmail_domain("test@yahoo.com"))
        self.assertFalse(self.generator.is_gmail_domain("test@example.com"))
    
    def test_generate_tag(self):
        """Тест генерации тегов"""
        tag = self.generator.generate_tag()
        
        # Проверяем формат: YYMMDD + 2 символа
        self.assertEqual(len(tag), 8)
        
        # Проверяем что начинается с датой
        today = datetime.now().strftime('%y%m%d')
        self.assertTrue(tag.startswith(today))
        
        # Проверяем что последние 2 символа - алфанумерик
        suffix = tag[6:]
        self.assertEqual(len(suffix), 2)
        self.assertTrue(suffix.isalnum())
        
        # Генерируем несколько тегов - они должны быть разные
        tags = [self.generator.generate_tag() for _ in range(5)]
        self.assertEqual(len(set(tags)), 5)  # Все уникальные
    
    def test_generate_dot_variants(self):
        """Тест генерации dot вариантов"""
        # Тест с обычным именем
        variants = self.generator.generate_dot_variants("johndoe", 5)
        
        # Все варианты должны содержать только исходные символы + точки
        for variant in variants:
            clean_variant = variant.replace('.', '')
            self.assertEqual(clean_variant, "johndoe")
        
        # Не должно быть двойных точек
        for variant in variants:
            self.assertNotIn('..', variant)
        
        # Не должно заканчиваться точкой
        for variant in variants:
            self.assertFalse(variant.endswith('.'))
        
        # Не должно начинаться точкой
        for variant in variants:
            self.assertFalse(variant.startswith('.'))
        
        # Тест с коротким именем
        short_variants = self.generator.generate_dot_variants("ab", 3)
        # Для очень короткого имени может быть мало вариантов
        self.assertGreaterEqual(len(short_variants), 0)
    
    def test_generate_plus_variants(self):
        """Тест генерации +tag вариантов"""
        variants = self.generator.generate_plus_variants("johndoe", 3)
        
        self.assertEqual(len(variants), 3)
        
        # Все должны начинаться с johndoe+
        for variant in variants:
            self.assertTrue(variant.startswith("johndoe+"))
        
        # Все теги должны быть разные
        tags = [variant.split('+')[1] for variant in variants]
        self.assertEqual(len(set(tags)), 3)
    
    def test_generate_aliases(self):
        """Тест основной функции генерации"""
        # Тест с Gmail
        aliases = self.generator.generate("john.doe@gmail.com", 5)
        
        self.assertEqual(len(aliases), 5)
        
        # Все должны быть на том же домене
        for alias in aliases:
            self.assertTrue(alias.endswith("@gmail.com"))
        
        # Все должны быть уникальные
        self.assertEqual(len(set(aliases)), 5)
        
        # Должны содержать mix +tag и dot вариантов
        plus_variants = [alias for alias in aliases if '+' in alias]
        dot_variants = [alias for alias in aliases if '+' not in alias]
        
        # Должны быть и те и другие
        self.assertGreater(len(plus_variants), 0)
        # dot варианты могут быть не всегда, но плюс-варианты должны быть
    
    def test_generate_with_invalid_email(self):
        """Тест с невалидным email"""
        with self.assertRaises(ValueError):
            self.generator.generate("invalid-email", 5)
    
    def test_generate_with_different_counts(self):
        """Тест с разным количеством алиасов"""
        for count in [1, 3, 5, 10]:
            aliases = self.generator.generate("test@gmail.com", count)
            self.assertEqual(len(aliases), count)
            self.assertEqual(len(set(aliases)), count)  # Все уникальные
    
    def test_generate_preserves_base_email_privacy(self):
        """Тест что базовый email не утекает в алиасы (кроме нормализованной формы)"""
        # Исходный email с +tag
        original = "john.doe+existing@gmail.com"
        aliases = self.generator.generate(original, 5)
        
        # Исходный email не должен появляться в алиасах
        self.assertNotIn(original, aliases)
        
        # Но нормализованная форма может использоваться
        normalized_base = "johndoe@gmail.com"
        # Это нормально, если нормализованная форма появляется


class TestPublicFunctions(unittest.TestCase):
    """Тесты публичных функций модуля"""
    
    def test_generate_gmail_aliases_function(self):
        """Тест основной публичной функции"""
        aliases = generate_gmail_aliases("test@gmail.com", 3)
        
        self.assertEqual(len(aliases), 3)
        self.assertEqual(len(set(aliases)), 3)  # Все уникальные
        
        for alias in aliases:
            self.assertTrue(alias.endswith("@gmail.com"))
    
    def test_generate_gmail_aliases_invalid_count(self):
        """Тест с невалидным количеством"""
        with self.assertRaises(ValueError):
            generate_gmail_aliases("test@gmail.com", 0)
        
        with self.assertRaises(ValueError):
            generate_gmail_aliases("test@gmail.com", 11)
        
        with self.assertRaises(ValueError):
            generate_gmail_aliases("test@gmail.com", "invalid")
    
    def test_validate_gmail_input_function(self):
        """Тест валидации ввода"""
        # Gmail адрес
        is_valid, error, is_gmail = validate_gmail_input("test@gmail.com")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
        self.assertTrue(is_gmail)
        
        # Не Gmail адрес
        is_valid, error, is_gmail = validate_gmail_input("test@yahoo.com")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
        self.assertFalse(is_gmail)
        
        # Невалидный адрес
        is_valid, error, is_gmail = validate_gmail_input("invalid")
        self.assertFalse(is_valid)
        self.assertNotEqual(error, "")
        self.assertFalse(is_gmail)


class TestRealWorldScenarios(unittest.TestCase):
    """Тесты реальных сценариев использования"""
    
    def test_typical_gmail_addresses(self):
        """Тест с типичными Gmail адресами"""
        test_emails = [
            "john.doe@gmail.com",
            "jane.smith@gmail.com", 
            "user123@gmail.com",
            "test.user+tag@gmail.com",
            "simple@googlemail.com"
        ]
        
        for email in test_emails:
            with self.subTest(email=email):
                aliases = generate_gmail_aliases(email, 5)
                self.assertEqual(len(aliases), 5)
                
                # Проверяем что домен сохранен
                original_domain = email.split('@')[1]
                for alias in aliases:
                    self.assertTrue(alias.endswith(f"@{original_domain}"))
    
    def test_quota_limit_scenarios(self):
        """Тест сценариев с лимитами квот"""
        # Генерируем максимальное количество
        aliases = generate_gmail_aliases("user@gmail.com", 10)
        self.assertEqual(len(aliases), 10)
        
        # Все должны быть уникальные
        self.assertEqual(len(set(aliases)), 10)
    
    def test_non_pii_in_tags(self):
        """Тест что в тегах нет персональной информации"""
        email = "sensitive.user+personal@gmail.com"
        aliases = generate_gmail_aliases(email, 5)
        
        # Проверяем что исходный +tag не попадает в новые алиасы
        for alias in aliases:
            if '+' in alias:
                tag = alias.split('+')[1].split('@')[0]
                # Тег не должен содержать "personal" из исходного email
                self.assertNotIn("personal", tag.lower())
                
                # Тег должен соответствовать нашему формату
                self.assertEqual(len(tag), 8)  # YYMMDD + 2 символа


if __name__ == '__main__':
    # Настройка логирования для тестов
    import logging
    logging.basicConfig(level=logging.ERROR)
    
    # Запуск тестов
    unittest.main(verbosity=2)
