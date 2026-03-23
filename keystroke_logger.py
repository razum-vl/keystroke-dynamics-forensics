"""
Кейлоггер для исследования динамики клавиатурного почерка
УрГЮУ - Судебная лингвистика
Фиксирует: задержки между нажатиями, силу нажатия (время удержания), спецклавиши
"""

import keyboard
import time
import json
import threading
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict
import os
import hashlib
import csv
from collections import deque


@dataclass
class KeyEvent:
    """Класс для хранения данных о событии клавиши"""
    key: str
    event_type: str  # 'down' или 'up'
    timestamp: float
    scan_code: Optional[int] = None
    
    def to_dict(self):
        return asdict(self)


class KeystrokeDynamicsLogger:
    """
    Основной класс кейлоггера для записи динамики нажатий клавиш
    """
    
    def __init__(self, session_name: str = "default", output_dir: str = "keystroke_data"):
        """
        Инициализация логгера
        
        Args:
            session_name: Имя сессии для идентификации
            output_dir: Директория для сохранения данных
        """
        self.session_name = session_name
        self.output_dir = output_dir
        self.events: List[KeyEvent] = []
        self.active_keys: Dict[str, KeyEvent] = {}  # Текущие нажатые клавиши
        self.is_recording = False
        self.session_start_time = None
        self.lock = threading.Lock()
        
        # Статистика для анализа
        self.hold_times = []  # Время удержания клавиш
        self.latencies = []   # Задержки между нажатиями
        self.digraphs = []    # Пары клавиш и задержки между ними
        
        # Создаем директорию для данных
        os.makedirs(output_dir, exist_ok=True)
        
        # Специальные клавиши для отдельного учета
        self.special_keys = {
            'backspace', 'delete', 'enter', 'space', 'tab', 'caps lock',
            'shift', 'ctrl', 'alt', 'cmd', 'windows', 'esc',
            'up', 'down', 'left', 'right', 'insert', 'home', 'end',
            'page up', 'page down'
        }
    
    def get_key_name(self, event: keyboard.KeyboardEvent) -> str:
        """Нормализует имя клавиши"""
        if event.name:
            # Преобразуем специальные клавиши
            key_name = event.name.lower()
            
            # Обработка модификаторов
            if event.event_type == keyboard.KEY_DOWN:
                if key_name == 'shift':
                    keyboard.press_and_release('shift')
            
            return key_name
        return str(event.scan_code)
    
    def on_key_event(self, event: keyboard.KeyboardEvent):
        """Обработчик событий клавиатуры"""
        if not self.is_recording:
            return
        
        with self.lock:
            key_name = self.get_key_name(event)
            timestamp = time.time()
            
            if event.event_type == keyboard.KEY_DOWN:
                # Нажатие клавиши
                key_event = KeyEvent(
                    key=key_name,
                    event_type='down',
                    timestamp=timestamp,
                    scan_code=event.scan_code
                )
                self.events.append(key_event)
                self.active_keys[key_name] = key_event
                
            elif event.event_type == keyboard.KEY_UP:
                # Отпускание клавиши
                if key_name in self.active_keys:
                    # Рассчитываем время удержания
                    down_event = self.active_keys[key_name]
                    hold_time = timestamp - down_event.timestamp
                    self.hold_times.append({
                        'key': key_name,
                        'hold_time': hold_time,
                        'timestamp': timestamp
                    })
                    
                    # Если это не спецклавиша, записываем в статистику
                    if key_name not in self.special_keys:
                        # Добавляем в задержки между клавишами
                        if len(self.events) >= 2:
                            last_event = self.events[-2]
                            latency = timestamp - last_event.timestamp
                            self.latencies.append({
                                'from': last_event.key,
                                'to': key_name,
                                'latency': latency
                            })
                            
                            # Записываем диграфы
                            if last_event.key not in self.special_keys and key_name not in self.special_keys:
                                self.digraphs.append({
                                    'pair': f"{last_event.key}->{key_name}",
                                    'latency': latency
                                })
                    
                    del self.active_keys[key_name]
                
                key_event = KeyEvent(
                    key=key_name,
                    event_type='up',
                    timestamp=timestamp,
                    scan_code=event.scan_code
                )
                self.events.append(key_event)
    
    def start_recording(self):
        """Начинает запись нажатий"""
        self.is_recording = True
        self.session_start_time = datetime.now()
        self.events = []
        self.active_keys = {}
        self.hold_times = []
        self.latencies = []
        self.digraphs = []
        
        # Регистрируем обработчики
        keyboard.hook(self.on_key_event)
        
        print(f"Запись начата в {self.session_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("Нажмите Ctrl+Shift+S для остановки записи")
    
    def stop_recording(self):
        """Останавливает запись и сохраняет данные"""
        self.is_recording = False
        keyboard.unhook_all()
        
        if self.events:
            self.save_data()
            self.generate_report()
        else:
            print("Нет данных для сохранения")
    
    def save_data(self):
        """Сохраняет собранные данные в файлы"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"{self.session_name}_{timestamp}"
        
        # Сохраняем полные события
        events_file = os.path.join(self.output_dir, f"{base_filename}_events.json")
        with open(events_file, 'w', encoding='utf-8') as f:
            json.dump({
                'session_info': {
                    'name': self.session_name,
                    'start_time': self.session_start_time.isoformat(),
                    'end_time': datetime.now().isoformat(),
                    'total_events': len(self.events)
                },
                'events': [e.to_dict() for e in self.events]
            }, f, indent=2, ensure_ascii=False)
        
        # Сохраняем статистику удержаний
        holds_file = os.path.join(self.output_dir, f"{base_filename}_hold_times.json")
        with open(holds_file, 'w', encoding='utf-8') as f:
            json.dump(self.hold_times, f, indent=2, ensure_ascii=False)
        
        # Сохраняем латентности
        latency_file = os.path.join(self.output_dir, f"{base_filename}_latencies.json")
        with open(latency_file, 'w', encoding='utf-8') as f:
            json.dump(self.latencies, f, indent=2, ensure_ascii=False)
        
        # Сохраняем диграфы
        digraph_file = os.path.join(self.output_dir, f"{base_filename}_digraphs.json")
        with open(digraph_file, 'w', encoding='utf-8') as f:
            json.dump(self.digraphs, f, indent=2, ensure_ascii=False)
        
        # Сохраняем CSV для анализа
        csv_file = os.path.join(self.output_dir, f"{base_filename}_analysis.csv")
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Event_Number', 'Key', 'Type', 'Timestamp', 'Hold_Time', 'Latency_To_Next'])
            
            for i, event in enumerate(self.events):
                hold_time = ''
                if event.event_type == 'up':
                    # Находим время удержания
                    for hold in self.hold_times:
                        if hold['key'] == event.key and abs(hold['timestamp'] - event.timestamp) < 0.1:
                            hold_time = hold['hold_time']
                            break
                
                latency = ''
                if i < len(self.events) - 1:
                    latency = self.events[i+1].timestamp - event.timestamp
                
                writer.writerow([
                    i + 1,
                    event.key,
                    event.event_type,
                    f"{event.timestamp:.6f}",
                    f"{hold_time:.6f}" if hold_time else '',
                    f"{latency:.6f}" if latency else ''
                ])
        
        print(f"\nДанные сохранены в: {self.output_dir}")
        print(f"- События: {events_file}")
        print(f"- Удержания: {holds_file}")
        print(f"- Латентности: {latency_file}")
        print(f"- Диграфы: {digraph_file}")
        print(f"- CSV анализ: {csv_file}")
    
    def generate_report(self):
        """Генерирует статистический отчет"""
        print("\n" + "="*60)
        print("СТАТИСТИЧЕСКИЙ ОТЧЕТ ПО КЛАВИАТУРНОМУ ПОЧЕРКУ")
        print("="*60)
        
        print(f"\nСессия: {self.session_name}")
        print(f"Длительность: {(datetime.now() - self.session_start_time).total_seconds():.2f} сек")
        print(f"Всего событий: {len(self.events)}")
        
        # Анализ времени удержания
        if self.hold_times:
            hold_times_values = [h['hold_time'] for h in self.hold_times]
            print(f"\n📊 ВРЕМЯ УДЕРЖАНИЯ КЛАВИШ:")
            print(f"  Среднее: {sum(hold_times_values)/len(hold_times_values)*1000:.2f} мс")
            print(f"  Медиана: {sorted(hold_times_values)[len(hold_times_values)//2]*1000:.2f} мс")
            print(f"  Мин: {min(hold_times_values)*1000:.2f} мс")
            print(f"  Макс: {max(hold_times_values)*1000:.2f} мс")
            print(f"  Стандартное отклонение: {(sum((x - sum(hold_times_values)/len(hold_times_values))**2 for x in hold_times_values)/len(hold_times_values))**0.5*1000:.2f} мс")
        
        # Анализ задержек между нажатиями
        if self.latencies:
            latencies_values = [l['latency'] for l in self.latencies if l['latency'] < 2.0]  # Фильтруем аномалии > 2 сек
            if latencies_values:
                print(f"\n⏱️ ЗАДЕРЖКИ МЕЖДУ НАЖАТИЯМИ:")
                print(f"  Средняя: {sum(latencies_values)/len(latencies_values)*1000:.2f} мс")
                print(f"  Медиана: {sorted(latencies_values)[len(latencies_values)//2]*1000:.2f} мс")
                print(f"  Мин: {min(latencies_values)*1000:.2f} мс")
                print(f"  Макс: {max(latencies_values)*1000:.2f} мс")
        
        # Анализ диграфов
        if self.digraphs:
            print(f"\n🔤 НАИБОЛЕЕ ЧАСТЫЕ ДИГРАФЫ:")
            from collections import Counter
            digraph_counter = Counter([d['pair'] for d in self.digraphs])
            for digraph, count in digraph_counter.most_common(10):
                # Находим среднюю задержку для этого диграфа
                avg_latency = sum(d['latency'] for d in self.digraphs if d['pair'] == digraph) / count
                print(f"  {digraph}: {count} раз, средняя задержка {avg_latency*1000:.2f} мс")
        
        # Анализ использования специальных клавиш
        special_keys_used = [e.key for e in self.events if e.key in self.special_keys and e.event_type == 'down']
        if special_keys_used:
            print(f"\n🎯 ИСПОЛЬЗОВАНИЕ СПЕЦИАЛЬНЫХ КЛАВИШ:")
            special_counter = Counter(special_keys_used)
            for key, count in special_counter.most_common():
                print(f"  {key}: {count} раз")
        
        print("\n" + "="*60)
        print("Для судебно-лингвистической экспертизы рекомендуется:")
        print("1. Сохранить JSON файлы для дальнейшего анализа")
        print("2. Сравнить с эталонными образцами почерка")
        print("3. Провести статистический анализ диграфов")
        print("4. Вычислить уникальные ритмические паттерны")
        print("="*60)
    
    def stop_hotkey(self):
        """Хоткей для остановки"""
        keyboard.add_hotkey('ctrl+shift+s', self.stop_recording)


class ForensicKeystrokeAnalyzer:
    """
    Класс для судебного анализа клавиатурного почерка
    """
    
    def __init__(self):
        self.sessions: Dict[str, List[Dict]] = {}
    
    def load_session(self, filepath: str) -> Dict:
        """Загружает сессию из JSON файла"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    
    def calculate_signature(self, events_file: str) -> Dict:
        """
        Вычисляет уникальную подпись пользователя на основе динамики
        """
        with open(events_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        events = data['events']
        
        # Извлекаем временные метки
        timestamps = [e['timestamp'] for e in events]
        
        # Вычисляем ритмические паттерны
        if len(timestamps) > 1:
            intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
            
            signature = {
                'mean_typing_speed': sum(intervals)/len(intervals),
                'typing_rhythm_std': (sum((x - sum(intervals)/len(intervals))**2 for x in intervals)/len(intervals))**0.5,
                'total_events': len(events),
                'session_duration': timestamps[-1] - timestamps[0] if timestamps else 0
            }
            
            return signature
        return {}
    
    def compare_sessions(self, session1: str, session2: str) -> Dict:
        """
        Сравнивает две сессии для определения вероятности принадлежности одному автору
        """
        sig1 = self.calculate_signature(session1)
        sig2 = self.calculate_signature(session2)
        
        if not sig1 or not sig2:
            return {'error': 'Недостаточно данных для сравнения'}
        
        # Вычисляем коэффициент сходства
        speed_diff = abs(sig1['mean_typing_speed'] - sig2['mean_typing_speed'])
        rhythm_diff = abs(sig1['typing_rhythm_std'] - sig2['typing_rhythm_std'])
        
        similarity_score = 100 - (speed_diff / 0.01 * 50 + rhythm_diff / 0.005 * 50)
        similarity_score = max(0, min(100, similarity_score))
        
        return {
            'similarity_score': similarity_score,
            'session1_signature': sig1,
            'session2_signature': sig2,
            'analysis': f"Вероятность принадлежности одному автору: {similarity_score:.1f}%",
            'forensic_conclusion': "Высокая вероятность" if similarity_score > 80 else 
                                   "Средняя вероятность" if similarity_score > 50 else 
                                   "Низкая вероятность"
        }


def main():
    """Главная функция для запуска приложения"""
    print("="*60)
    print("КЕЙЛОГГЕР ДЛЯ ИССЛЕДОВАНИЯ ДИНАМИКИ КЛАВИАТУРНОГО ПОЧЕРКА")
    print("УрГЮУ - Судебная лингвистика")
    print("="*60)
    print("\nИнструмент для фиксации:")
    print("✓ Задержки между нажатиями клавиш")
    print("✓ Время удержания клавиш (сила нажатия)")
    print("✓ Использование специальных клавиш")
    print("✓ Ритмические паттерны печати")
    print("\nДанные могут быть использованы для:")
    print("✓ Доказательства авторства текста")
    print("✓ Судебно-лингвистической экспертизы")
    print("✓ Идентификации личности по почерку")
    print("="*60)
    
    # Создаем логгер
    session_id = input("\nВведите идентификатор сессии (например, suspect_001): ")
    logger = KeystrokeDynamicsLogger(session_name=session_id)
    
    print("\nИнструкция:")
    print("1. Программа будет записывать все нажатия клавиш")
    print("2. Для остановки записи нажмите Ctrl+Shift+S")
    print("3. После остановки данные будут сохранены для анализа")
    print("\nНажмите Enter для начала записи...")
    input()
    
    # Запускаем запись
    logger.start_recording()
    logger.stop_hotkey()
    
    # Ожидаем остановки
    try:
        while logger.is_recording:
            time.sleep(0.1)
    except KeyboardInterrupt:
        logger.stop_recording()
    
    print("\nЗапись завершена. Данные сохранены.")


if __name__ == "__main__":
    main()
