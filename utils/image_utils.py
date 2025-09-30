"""
Утилиты для уникализации изображений
"""

import os
import random
import string
import logging
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
from typing import List, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_random_filename(extension: str) -> str:
    """Генерирует случайное имя файла"""
    random_name = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    return f"{random_name}{extension}"


def add_noise_to_image(image: Image.Image, intensity: int = 3) -> Image.Image:
    """
    Добавляет шум к изображению
    
    Args:
        image: Изображение PIL
        intensity: Интенсивность шума (1-10)
    
    Returns:
        Image: Изображение с шумом
    """
    # Конвертируем в numpy array
    img_array = np.array(image)
    
    # Генерируем шум
    noise = np.random.normal(0, intensity, img_array.shape)
    
    # Добавляем шум к изображению
    noisy_img = img_array + noise
    
    # Обрезаем значения до диапазона [0, 255]
    noisy_img = np.clip(noisy_img, 0, 255).astype(np.uint8)
    
    return Image.fromarray(noisy_img)


def process_image_uniqueness(
    input_path: str,
    output_dir: str,
    params: dict
) -> str:
    """
    Применяет случайные методы уникализации к изображению
    
    Args:
        input_path: Путь к исходному изображению
        output_dir: Директория для сохранения результата
        params: Параметры уникализации из конфига
    
    Returns:
        str: Путь к обработанному файлу
    """
    try:
        # Открываем изображение
        image = Image.open(input_path)
        
        # Конвертируем в RGB если нужно
        if image.mode in ('RGBA', 'LA', 'P'):
            # Создаем белый фон
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if 'A' in image.mode else None)
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Применяем случайные трансформации
        
        # 1. Зеркальное отражение убрано по требованию пользователя
        
        # 2. Изменение яркости
        brightness_factor = random.uniform(*params['brightness_range'])
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(brightness_factor)
        logger.debug(f"Applied brightness: {brightness_factor}")
        
        # 3. Изменение контраста
        contrast_factor = random.uniform(*params['contrast_range'])
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(contrast_factor)
        logger.debug(f"Applied contrast: {contrast_factor}")
        
        # 4. Добавление шума
        noise_intensity = random.randint(*params['noise_range'])
        image = add_noise_to_image(image, noise_intensity)
        logger.debug(f"Applied noise: {noise_intensity}")
        
        # 5. Микро-обрезка (изменение размера)
        crop_pixels = random.randint(*params['crop_pixels'])
        width, height = image.size
        image = image.crop((
            crop_pixels,
            crop_pixels,
            width - crop_pixels,
            height - crop_pixels
        ))
        logger.debug(f"Applied crop: {crop_pixels} pixels")
        
        # 6. Легкое размытие (20% шанс)
        if random.random() > 0.8:
            image = image.filter(ImageFilter.GaussianBlur(radius=0.5))
            logger.debug("Applied slight blur")
        
        # Генерируем случайное имя файла
        extension = Path(input_path).suffix
        output_filename = generate_random_filename(extension)
        output_path = os.path.join(output_dir, output_filename)
        
        # Сохраняем с случайным качеством JPEG
        if extension.lower() in ['.jpg', '.jpeg']:
            quality = random.randint(85, 95)
            image.save(output_path, quality=quality, optimize=True)
        else:
            image.save(output_path, optimize=True)
        
        logger.info(f"Image processed: {output_filename}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error processing image: {e}")
        raise


def create_multiple_unique_images(
    input_path: str,
    output_dir: str,
    count: int,
    params: dict
) -> List[str]:
    """
    Создает несколько уникальных копий изображения
    
    Args:
        input_path: Путь к исходному изображению
        output_dir: Директория для сохранения
        count: Количество копий
        params: Параметры уникализации
    
    Returns:
        List[str]: Список путей к созданным файлам
    """
    results = []
    
    for i in range(count):
        try:
            output_path = process_image_uniqueness(input_path, output_dir, params)
            results.append(output_path)
            logger.info(f"Created unique image {i+1}/{count}")
        except Exception as e:
            logger.error(f"Failed to create unique image {i+1}: {e}")
    
    return results
