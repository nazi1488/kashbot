"""
Random Face Keyboards

Конструкторы inline-клавиатур для интерфейса генерации случайных лиц.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


class RandomFaceKeyboard:
    """Конструктор клавиатур для Random Face"""
    
    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        """
        Главное меню раздела Random Face
        
        Returns:
            InlineKeyboardMarkup с кнопками генерации и навигации
        """
        keyboard = [
            [InlineKeyboardButton("🎲 Сгенерировать", callback_data="random_face_generate")],
            [InlineKeyboardButton("🔁 Ещё", callback_data="random_face_more")],
            [InlineKeyboardButton("↩️ Назад", callback_data="main_menu")]
        ]
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def after_generation() -> InlineKeyboardMarkup:
        """
        Клавиатура после успешной генерации лица
        
        Returns:
            InlineKeyboardMarkup с кнопками повтора и навигации
        """
        keyboard = [
            [InlineKeyboardButton("🔁 Ещё одно", callback_data="random_face_more")],
            [InlineKeyboardButton("↩️ Назад в меню", callback_data="main_menu")]
        ]
        
        return InlineKeyboardMarkup(keyboard)
