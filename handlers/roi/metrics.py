"""
Расчет метрик для ROI-калькулятора
"""

from typing import Dict, Optional, Any
from .validators import format_money, format_percent

class ROIMetrics:
    """Класс для расчета метрик арбитража"""
    
    def __init__(self, data: Dict[str, Optional[float]]):
        self.spend = data.get('spend')      # Расход
        self.income = data.get('income')    # Доход
        self.shows = data.get('shows')      # Показы
        self.clicks = data.get('clicks')    # Клики
        self.leads = data.get('leads')      # Заявки
        self.sales = data.get('sales')      # Продажи
        
        self.metrics = {}
        self.descriptions = {}
        
    def calculate_all(self) -> Dict[str, Any]:
        """Рассчитывает все возможные метрики"""
        
        # Основные финансовые метрики
        if self.income is not None and self.spend is not None and self.spend > 0:
            roi = (self.income - self.spend) / self.spend * 100
            self.metrics['ROI'] = format_percent(roi)
            self.descriptions['ROI'] = "окупаемость расходов (выше — лучше)"
            
            profit = self.income - self.spend
            self.metrics['Профит'] = format_money(profit)
            self.descriptions['Профит'] = "прибыль (Доход − Расход)"
            
            roas = self.income / self.spend
            self.metrics['ROAS'] = f"{roas:.2f}"
            self.descriptions['ROAS'] = "во сколько раз доход больше расхода"
        
        # Конверсионные метрики
        if self.shows is not None and self.clicks is not None and self.shows > 0:
            ctr = self.clicks / self.shows * 100
            self.metrics['CTR'] = format_percent(ctr)
            self.descriptions['CTR'] = "какой % показов превратился в клики"
            
        if self.clicks is not None and self.leads is not None and self.clicks > 0:
            ctc = self.leads / self.clicks * 100
            self.metrics['CTC'] = format_percent(ctc)
            self.descriptions['CTC'] = "какой % кликов стал заявками"
            
        if self.leads is not None and self.sales is not None and self.leads > 0:
            ctb = self.sales / self.leads * 100
            self.metrics['CTB'] = format_percent(ctb)
            self.descriptions['CTB'] = "какой % заявок дошёл до покупки"
        
        # Стоимостные метрики
        if self.spend is not None and self.shows is not None and self.shows > 0:
            cpm = self.spend / (self.shows / 1000)
            self.metrics['CPM'] = format_money(cpm)
            self.descriptions['CPM'] = "цена 1000 показов"
            
        if self.spend is not None and self.clicks is not None and self.clicks > 0:
            cpc = self.spend / self.clicks
            self.metrics['CPC'] = format_money(cpc)
            self.descriptions['CPC'] = "цена клика"
            
        if self.spend is not None and self.leads is not None and self.leads > 0:
            cpa = self.spend / self.leads
            self.metrics['CPA'] = format_money(cpa)
            self.descriptions['CPA'] = "цена заявки (лида)"
            
        if self.spend is not None and self.sales is not None and self.sales > 0:
            cps = self.spend / self.sales
            self.metrics['CPS'] = format_money(cps)
            self.descriptions['CPS'] = "цена продажи"
        
        # Средние чеки
        if self.income is not None and self.sales is not None and self.sales > 0:
            apv = self.income / self.sales
            self.metrics['APV'] = format_money(apv)
            self.descriptions['APV'] = "средний чек покупки"
            
        if self.income is not None and self.leads is not None and self.leads > 0:
            apc = self.income / self.leads
            self.metrics['APC'] = format_money(apc)
            self.descriptions['APC'] = "средний доход на заявку"
        
        return {
            'metrics': self.metrics,
            'descriptions': self.descriptions
        }
    
    def format_results_card(self) -> str:
        """Форматирует результаты в виде красивой карточки"""
        result = self.calculate_all()
        metrics = result['metrics']
        descriptions = result['descriptions']
        
        if not metrics:
            return "🚫 Недостаточно данных для расчета метрик.\nВведите хотя бы расход и доход."
        
        # Формируем карточку результатов
        card = "📊 **Результаты расчета**\n\n"
        
        # Основные финансовые метрики
        financial_line = []
        if 'ROI' in metrics:
            sign = "+" if not metrics['ROI'].startswith('-') else ""
            financial_line.append(f"ROI: {sign}{metrics['ROI']}")
        if 'Профит' in metrics:
            financial_line.append(f"Профит: {metrics['Профит']}")
        if 'ROAS' in metrics:
            financial_line.append(f"ROAS: {metrics['ROAS']}")
            
        if financial_line:
            card += " | ".join(financial_line) + "\n\n"
        
        # Конверсии
        conversion_line = []
        for metric in ['CTR', 'CTC', 'CTB']:
            if metric in metrics:
                conversion_line.append(f"{metric}: {metrics[metric]}")
                
        if conversion_line:
            card += "    ".join(conversion_line) + "\n\n"
        
        # Стоимости
        cost_line = []
        for metric in ['CPM', 'CPC', 'CPA', 'CPS']:
            if metric in metrics:
                cost_line.append(f"{metric}: {metrics[metric]}")
                
        if cost_line:
            card += "    ".join(cost_line) + "\n\n"
        
        # Средние чеки
        avg_line = []
        for metric in ['APV', 'APC']:
            if metric in metrics:
                avg_line.append(f"{metric}: {metrics[metric]}")
                
        if avg_line:
            card += "    ".join(avg_line) + "\n\n"
        
        # Расшифровки
        if descriptions:
            card += "📋 **Расшифровка:**\n"
            for metric, desc in descriptions.items():
                card += f"• **{metric}** — {desc}\n"
        
        return card
