"""
Юнит тесты для utils.otp_extract
"""

import unittest
from utils.otp_extract import extract_codes, extract_links, extract_verification_info, clean_html


class TestOTPExtraction(unittest.TestCase):
    """Тесты извлечения OTP кодов"""
    
    def test_extract_simple_numeric_codes(self):
        """Тест извлечения простых цифровых кодов"""
        content = "Your verification code is 123456"
        codes = extract_codes(content)
        self.assertIn("123456", codes)
        
        content = "Code: 4567"
        codes = extract_codes(content)
        self.assertIn("4567", codes)
    
    def test_extract_alphanumeric_codes(self):
        """Тест извлечения буквенно-цифровых кодов"""
        content = "Your OTP code is ABC123"
        codes = extract_codes(content)
        self.assertIn("ABC123", codes)
        
        content = "Verification: XY7Z89"
        codes = extract_codes(content)
        self.assertIn("XY7Z89", codes)
    
    def test_filter_invalid_codes(self):
        """Тест фильтрации недопустимых кодов"""
        content = "Year 2024 and 0000 and 1111 and 1234"
        codes = extract_codes(content)
        
        # Эти коды должны быть отфильтрованы
        self.assertNotIn("2024", codes)  # Год
        self.assertNotIn("0000", codes)  # Только нули
        self.assertNotIn("1111", codes)  # Повторяющиеся цифры
        self.assertNotIn("1234", codes)  # Простая последовательность
    
    def test_code_relevance_scoring(self):
        """Тест ранжирования кодов по релевантности"""
        content = "Your verification code is 123456. The year is 2024."
        subject = "Email verification"
        codes = extract_codes(content, subject)
        
        # Код с маркером должен быть первым
        if len(codes) > 0:
            self.assertEqual(codes[0], "123456")
    
    def test_extract_from_html_content(self):
        """Тест извлечения кодов из HTML"""
        html_content = """
        <html>
        <body>
            <p>Your verification code is <strong>567890</strong></p>
            <div style="display:none">Hidden: 111111</div>
        </body>
        </html>
        """
        codes = extract_codes(html_content)
        self.assertIn("567890", codes)
    
    def test_codes_with_separators(self):
        """Тест извлечения кодов с разделителями"""
        content = "Code: 12-34 or 56 78"
        codes = extract_codes(content)
        self.assertTrue(any("12" in code and "34" in code for code in codes))
    
    def test_multiple_codes_in_content(self):
        """Тест обработки нескольких кодов в тексте"""
        content = "First code: 123456, second OTP: ABC789"
        codes = extract_codes(content)
        self.assertIn("123456", codes)
        self.assertIn("ABC789", codes)
    
    def test_code_extraction_with_markers(self):
        """Тест извлечения с учетом маркеров"""
        test_cases = [
            ("Verification code: 987654", "987654"),
            ("OTP: 456789", "456789"),
            ("Код подтверждения: 111222", "111222"),
            ("PIN code is 5678", "5678"),
        ]
        
        for content, expected_code in test_cases:
            with self.subTest(content=content):
                codes = extract_codes(content)
                self.assertIn(expected_code, codes)


class TestLinkExtraction(unittest.TestCase):
    """Тесты извлечения ссылок"""
    
    def test_extract_simple_links(self):
        """Тест извлечения простых ссылок"""
        html_content = '<a href="https://google.com/verify">Click here</a>'
        links = extract_links(html_content)
        self.assertIn("https://google.com/verify", links)
    
    def test_extract_multiple_links(self):
        """Тест извлечения нескольких ссылок"""
        html_content = '''
        <a href="https://site1.com">Link 1</a>
        <a href="https://site2.com">Link 2</a>
        '''
        links = extract_links(html_content)
        self.assertIn("https://site1.com", links)
        self.assertIn("https://site2.com", links)
    
    def test_filter_mailto_links(self):
        """Тест фильтрации mailto ссылок"""
        html_content = '''
        <a href="mailto:test@example.com">Email</a>
        <a href="https://google.com">Website</a>
        '''
        links = extract_links(html_content)
        self.assertNotIn("mailto:test@example.com", links)
        self.assertIn("https://google.com", links)
    
    def test_extract_links_from_text(self):
        """Тест извлечения ссылок из текста"""
        content = "Visit https://google.com for more info"
        links = extract_links(content)
        self.assertIn("https://google.com", links)
    
    def test_clean_tracking_parameters(self):
        """Тест очистки tracking параметров"""
        html_content = '<a href="https://google.com/page?utm_source=email&id=123">Link</a>'
        links = extract_links(html_content)
        # Должна остаться ссылка без utm параметров, но с обычными
        found_clean_link = any("utm_source" not in link and "id=123" in link for link in links)
        self.assertTrue(found_clean_link)
    
    def test_remove_duplicate_links(self):
        """Тест удаления дублирующихся ссылок"""
        html_content = '''
        <a href="https://google.com">Link 1</a>
        <a href="https://google.com">Link 2</a>
        '''
        links = extract_links(html_content)
        self.assertEqual(links.count("https://google.com"), 1)


class TestHTMLCleaning(unittest.TestCase):
    """Тесты очистки HTML"""
    
    def test_clean_simple_html(self):
        """Тест очистки простого HTML"""
        html = "<p>Hello <strong>world</strong>!</p>"
        cleaned = clean_html(html)
        self.assertEqual(cleaned, "Hello world!")
    
    def test_remove_script_tags(self):
        """Тест удаления script тегов"""
        html = '<p>Text</p><script>alert("hack")</script><p>More text</p>'
        cleaned = clean_html(html)
        self.assertNotIn("alert", cleaned)
        self.assertIn("Text", cleaned)
        self.assertIn("More text", cleaned)
    
    def test_remove_style_tags(self):
        """Тест удаления style тегов"""
        html = '<p>Text</p><style>body{color:red}</style><p>More text</p>'
        cleaned = clean_html(html)
        self.assertNotIn("color:red", cleaned)
        self.assertIn("Text", cleaned)
    
    def test_handle_empty_html(self):
        """Тест обработки пустого HTML"""
        self.assertEqual(clean_html(""), "")
        self.assertEqual(clean_html(None), "")
    
    def test_unescape_html_entities(self):
        """Тест обработки HTML сущностей"""
        html = "<p>Code: &lt;123456&gt;</p>"
        cleaned = clean_html(html)
        self.assertIn("<123456>", cleaned)


class TestVerificationInfo(unittest.TestCase):
    """Тесты комплексного извлечения информации"""
    
    def test_extract_verification_info_complete(self):
        """Тест полного извлечения информации"""
        html_content = '''
        <html>
        <body>
            <p>Your verification code is <strong>123456</strong></p>
            <p><a href="https://google.com/verify?token=abc">Verify here</a></p>
        </body>
        </html>
        '''
        subject = "Email verification required"
        
        info = extract_verification_info(html_content, subject)
        
        self.assertIn("123456", info['codes'])
        self.assertTrue(any("google.com" in link for link in info['links']))
        self.assertTrue(info['has_verification_keywords'])
        self.assertIn("verification", info['cleaned_text'].lower())
    
    def test_detect_verification_keywords(self):
        """Тест обнаружения ключевых слов верификации"""
        test_cases = [
            ("Please verify your account", True),
            ("Verification code", True),
            ("Подтверждение регистрации", True),
            ("Welcome to our service", False),
            ("Your order confirmation", False),
        ]
        
        for content, should_have_keywords in test_cases:
            with self.subTest(content=content):
                info = extract_verification_info(content)
                self.assertEqual(info['has_verification_keywords'], should_have_keywords)


if __name__ == '__main__':
    unittest.main()
