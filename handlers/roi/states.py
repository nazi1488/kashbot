"""
Состояния для ROI-калькулятора
"""

from enum import Enum, auto

class ROIStates(Enum):
    """Состояния диалога ROI-калькулятора"""
    MENU = auto()          # Показ меню с объяснением
    INPUT_SPEND = auto()   # Ввод расхода
    INPUT_INCOME = auto()  # Ввод дохода 
    INPUT_SHOWS = auto()   # Ввод показов
    INPUT_CLICKS = auto()  # Ввод кликов
    INPUT_LEADS = auto()   # Ввод заявок
    INPUT_SALES = auto()   # Ввод продаж
    RESULTS = auto()       # Показ результатов
