import pygame
import json
import sys
import math
import os
import re

SMART_QUOTES_TRANSLATION = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "‚": "'",
        "`": "'",
        "´": "'",
        "“": '"',
        "”": '"',
        "„": '"',
    }
)

# --- КОНФИГУРАЦИЯ ---
WIDTH, HEIGHT = 1000, 700
FPS = 60
SAVE_FILE = "froggy_save.json"

# Цвета
COLOR_UI_BG   = (60, 45, 30)
COLOR_BTN     = (100, 149, 237)
COLOR_BTN_HOV = (130, 170, 250)
COLOR_TEXT    = (255, 255, 255)
GOLD          = (255, 215, 0)
GRAY          = (128, 128, 128)
RED           = (220, 50, 50)
GREEN         = (50, 200, 50)
BLACK         = (0, 0, 0)
WHITE         = (255, 255, 255)
PINK          = (255, 192, 203)
BLUE          = (100, 149, 237)

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("Froggy Coder: Игра-тренажер")
clock = pygame.time.Clock()
font_splash = pygame.font.SysFont("Arial", 70, bold=True)

# ── ФОНЫ ────────────────────────────────────────────────────
try:
    BOLOTO_ORIGINAL = pygame.image.load("boloto.png").convert()
    WIN_ORIGINAL = pygame.image.load("win.jpg").convert()
except FileNotFoundError:
    BOLOTO_ORIGINAL = pygame.Surface((WIDTH, HEIGHT))
    WIN_ORIGINAL = pygame.Surface((WIDTH, HEIGHT))
    BOLOTO_ORIGINAL.fill((34, 139, 34))
    WIN_ORIGINAL.fill((34, 139, 34))

def _scale(src, w, h):
    return pygame.transform.scale(src, (w, h))

BOLOTO = _scale(BOLOTO_ORIGINAL, WIDTH, HEIGHT)
WIN = _scale(WIN_ORIGINAL, WIDTH, HEIGHT)

# ── ЛЯГУШКИ ─────────────────────────────────────────────────
def create_frog(size, color=GREEN, has_bow=False, has_tie=False, smaller=False):
    frog = pygame.Surface((size, size), pygame.SRCALPHA)
    if smaller:
        bw,bh,bx,by = int(size*.5),int(size*.35),int(size*.25),int(size*.4)
        hr,hx,hy = int(size*.18),int(size*.6),int(size*.45)
    else:
        bw,bh,bx,by = int(size*.625),int(size*.4375),int(size*.125),int(size*.3125)
        hr,hx,hy = int(size*.225),int(size*.6875),int(size*.375)
    pygame.draw.ellipse(frog, color, (bx,by,bw,bh))
    pygame.draw.circle(frog, color, (hx,hy), hr)
    er=int(hr*.33); ex=hx+int(hr*.28); ey=hy-int(hr*.28)
    pygame.draw.circle(frog, WHITE, (ex,ey), er)
    pygame.draw.circle(frog, BLACK, (ex+2,ey), int(er*.5))
    if smaller:
        pygame.draw.ellipse(frog,(34,139,34),(int(size*.1),int(size*.65),int(size*.25),int(size*.15)))
        pygame.draw.ellipse(frog,(34,139,34),(int(size*.5),int(size*.65),int(size*.2),int(size*.1)))
    else:
        pygame.draw.ellipse(frog,(34,139,34),(int(size*.0625),int(size*.5625),int(size*.3125),int(size*.1875)))
        pygame.draw.ellipse(frog,(34,139,34),(int(size*.5625),int(size*.5625),int(size*.25),int(size*.125)))
    if has_bow:
        bs=int(size*.15) if not smaller else int(size*.1)
        bwx=hx-int(hr*.7); bwy=hy-hr-bs//2
        pygame.draw.circle(frog,PINK,(bwx-bs//2,bwy),bs//2)
        pygame.draw.circle(frog,PINK,(bwx+bs//2,bwy),bs//2)
        pygame.draw.circle(frog,RED,(bwx,bwy),bs//3)
    if has_tie:
        ts=int(size*.12) if not smaller else int(size*.08)
        tx=hx; ty=hy+hr-int(hr*.3)
        pygame.draw.polygon(frog,BLUE,[(tx-ts//4,ty),(tx-ts,ty-ts//2),(tx-ts,ty+ts//2)])
        pygame.draw.polygon(frog,BLUE,[(tx+ts//4,ty),(tx+ts,ty-ts//2),(tx+ts,ty+ts//2)])
        pygame.draw.circle(frog,RED,(tx,ty),ts//4)
    return frog

# Всегда используем отрисованную лягушку (без frog.png)
FROG_IMG_RAW = create_frog(80)  # можно поменять размер/цвет тут

FROG_IMG  = pygame.transform.scale(FROG_IMG_RAW, (80, 80))
FROG_ICON = pygame.transform.scale(FROG_IMG_RAW, (40, 40))

# Базовые семейные (используются в других местах/как запас)
FROG_PAPA   = create_frog(100,GREEN,         has_tie=True)
FROG_MAMA   = create_frog(100,(100,200,100), has_bow=True)
FROG_SISTER = create_frog(80, (150,220,150), has_bow=True, smaller=True)
FROG_BRO    = create_frog(70, (80,180,80),   has_tie=True, smaller=True)

# ── ЗАДАНИЯ ─────────────────────────────────────────────────
def get_tasks(lang, difficulty):
    if lang == "Python":
        if difficulty == "Easy":
            return [
                [
                    {"type":"choice","q":"Что выведет print(2 + 2)?","options":["4","22","Ошибка"],"ans":"4","hint":"Сложение чисел"},
                    {"type":"input","q":"Выведите текст 'Hello'","ans":"print('Hello')","hint":"Используйте print()"},
                    {"type":"choice","q":"Как создать переменную?","options":["var x = 5","x = 5","int x = 5"],"ans":"x = 5","hint":"Просто имя и знак ="},
                    {"type":"input","q":"Создайте переменную a со значением 10","ans":"a = 10","hint":"Формат: имя = значение"},
                    {"type":"choice","q":"Что делает функция len()?","options":["Считает длину","Удаляет элемент","Создает список"],"ans":"Считает длину","hint":"От слова length"},
                ],
                [
                    {"type":"choice","q":"Как начать цикл for?","options":["for i in range(5):","for (i=0; i<5; i++)","loop i to 5"],"ans":"for i in range(5):","hint":"Используется 'in range'"},
                    {"type":"input","q":"Создайте список с числами 1, 2, 3","ans":"[1, 2, 3]","hint":"Квадратные скобки"},
                    {"type":"choice","q":"Какой тип данных у 'text'?","options":["str","int","char"],"ans":"str","hint":"Строка - string"},
                    {"type":"input","q":"Получите первый элемент списка lst","ans":"lst[0]","hint":"Индексация начинается с 0"},
                    {"type":"choice","q":"Как добавить элемент в список?","options":["lst.append(x)","lst.add(x)","lst.push(x)"],"ans":"lst.append(x)","hint":"Метод append"},
                ],
                [
                    {"type":"input","q":"Преобразуйте '5' в число","ans":"int('5')","hint":"Функция int()"},
                    {"type":"choice","q":"Как начать условие?","options":["if x > 5:","if (x > 5)","when x > 5:"],"ans":"if x > 5:","hint":"Ключевое слово if и двоеточие"},
                    {"type":"input","q":"Выведите числа от 0 до 4","ans":"for i in range(5): print(i)","hint":"Цикл for с range(5)"},
                    {"type":"choice","q":"Что вернет len('abc')?","options":["3","2","1"],"ans":"3","hint":"Считаем буквы: a, b, c"},
                    {"type":"input","q":"Создайте словарь с ключом 'name' и значением 'Bob'","ans":"{'name': 'Bob'}","hint":"Фигурные скобки"},
                ],
                [
                    {"type":"choice","q":"Как объявить функцию?","options":["def func():","function func():","func():"],"ans":"def func():","hint":"Ключевое слово def"},
                    {"type":"input","q":"Создайте функцию hello без параметров","ans":"def hello():","hint":"def название():"},
                    {"type":"choice","q":"Что делает return?","options":["Возвращает значение","Выводит на экран","Удаляет функцию"],"ans":"Возвращает значение","hint":"Возврат результата"},
                    {"type":"input","q":"Вызовите функцию test","ans":"test()","hint":"Название функции со скобками"},
                    {"type":"choice","q":"Как импортировать модуль math?","options":["import math","include math","using math"],"ans":"import math","hint":"Ключевое слово import"},
                ],
                [
                    {"type":"input","q":"Создайте цикл while с условием x < 10","ans":"while x < 10:","hint":"while условие:"},
                    {"type":"choice","q":"Что делает break в цикле?","options":["Прерывает цикл","Пропускает итерацию","Ничего"],"ans":"Прерывает цикл","hint":"Останавливает выполнение"},
                    {"type":"input","q":"Получите длину строки s","ans":"len(s)","hint":"Функция len()"},
                    {"type":"choice","q":"Что вернет type(5)?","options":["<class 'int'>","<class 'str'>","5"],"ans":"<class 'int'>","hint":"Тип целого числа"},
                    {"type":"input","q":"Прочитайте ввод пользователя","ans":"input()","hint":"Функция input()"},
                ],
            ]
        elif difficulty == "Medium":
            return [
                [
                    {"type":"choice","q":"Что выведет print([1,2,3][1])?","options":["2","1","3"],"ans":"2","hint":"Индекс 1 - второй элемент"},
                    {"type":"input","q":"Создайте список из 5 нулей","ans":"[0] * 5","hint":"Умножение списка"},
                    {"type":"choice","q":"Как проверить наличие элемента в списке?","options":["x in lst","lst.has(x)","lst.contains(x)"],"ans":"x in lst","hint":"Оператор in"},
                    {"type":"input","q":"Получите последний элемент списка lst","ans":"lst[-1]","hint":"Отрицательный индекс"},
                    {"type":"choice","q":"Что вернет '5' + '3'?","options":["'53'","8","Ошибка"],"ans":"'53'","hint":"Конкатенация строк"},
                ],
                [
                    {"type":"input","q":"Создайте функцию с параметром x","ans":"def func(x):","hint":"def имя(параметр):"},
                    {"type":"choice","q":"Что делает метод split()?","options":["Разделяет строку","Объединяет строки","Удаляет пробелы"],"ans":"Разделяет строку","hint":"Разбивает на части"},
                    {"type":"input","q":"Объедините список ['a','b'] в строку","ans":"''.join(['a','b'])","hint":"Метод join()"},
                    {"type":"choice","q":"Как удалить элемент из списка?","options":["lst.remove(x)","lst.delete(x)","lst.pop(x)"],"ans":"lst.remove(x)","hint":"Метод remove"},
                    {"type":"input","q":"Создайте срез списка lst с 1 по 3 элемент","ans":"lst[1:3]","hint":"Синтаксис [start:end]"},
                ],
                [
                    {"type":"choice","q":"Что такое lambda?","options":["Анонимная функция","Переменная","Цикл"],"ans":"Анонимная функция","hint":"Функция без имени"},
                    {"type":"input","q":"Создайте lambda, возвращающую x+1","ans":"lambda x: x+1","hint":"lambda параметр: выражение"},
                    {"type":"choice","q":"Что делает map()?","options":["Применяет функцию к элементам","Фильтрует список","Сортирует"],"ans":"Применяет функцию к элементам","hint":"Преобразует каждый элемент"},
                    {"type":"input","q":"Отфильтруйте список lst по условию x>5","ans":"filter(lambda x: x>5, lst)","hint":"Функция filter()"},
                    {"type":"choice","q":"Как открыть файл для чтения?","options":["open('file.txt', 'r')","read('file.txt')","file('file.txt')"],"ans":"open('file.txt', 'r')","hint":"Режим 'r' для чтения"},
                ],
                [
                    {"type":"input","q":"Создайте list comprehension для квадратов от 0 до 4","ans":"[x**2 for x in range(5)]","hint":"[выражение for переменная in последовательность]"},
                    {"type":"choice","q":"Что делает try-except?","options":["Обрабатывает ошибки","Создает цикл","Объявляет функцию"],"ans":"Обрабатывает ошибки","hint":"Обработка исключений"},
                    {"type":"input","q":"Создайте множество с элементами 1,2,3","ans":"{1, 2, 3}","hint":"Фигурные скобки"},
                    {"type":"choice","q":"Что вернет set([1,1,2])?","options":["{1, 2}","[1, 1, 2]","{1, 1, 2}"],"ans":"{1, 2}","hint":"Множество убирает дубликаты"},
                    {"type":"input","q":"Получите ключи словаря d","ans":"d.keys()","hint":"Метод keys()"},
                ],
                [
                    {"type":"choice","q":"Что такое *args?","options":["Произвольное число аргументов","Умножение","Указатель"],"ans":"Произвольное число аргументов","hint":"Переменное количество параметров"},
                    {"type":"input","q":"Создайте класс Car","ans":"class Car:","hint":"class Название:"},
                    {"type":"choice","q":"Что делает метод __init__?","options":["Инициализирует объект","Удаляет объект","Копирует объект"],"ans":"Инициализирует объект","hint":"Конструктор класса"},
                    {"type":"input","q":"Импортируйте функцию sqrt из math","ans":"from math import sqrt","hint":"from модуль import функция"},
                    {"type":"choice","q":"Что такое self?","options":["Ссылка на объект","Глобальная переменная","Функция"],"ans":"Ссылка на объект","hint":"Первый параметр методов"},
                ],
            ]
        else:  # Hard
            return [
                [
                    {"type":"input","q":"Создайте декоратор без параметров","ans":"def decorator(func):","hint":"Функция, принимающая функцию"},
                    {"type":"choice","q":"Что такое генератор?","options":["Функция с yield","Обычная функция","Класс"],"ans":"Функция с yield","hint":"Использует yield вместо return"},
                    {"type":"input","q":"Создайте генератор чисел от 0 до n","ans":"def gen(n): yield from range(n)","hint":"yield from последовательность"},
                    {"type":"choice","q":"Что делает enumerate()?","options":["Добавляет индексы","Удаляет элементы","Сортирует"],"ans":"Добавляет индексы","hint":"Нумерует элементы"},
                    {"type":"input","q":"Создайте словарь dict comprehension","ans":"{x: x**2 for x in range(5)}","hint":"{ключ: значение for переменная in последовательность}"},
                ],
                [
                    {"type":"choice","q":"Что такое замыкание?","options":["Функция внутри функции","Цикл","Класс"],"ans":"Функция внутри функции","hint":"Вложенная функция с доступом к внешним переменным"},
                    {"type":"input","q":"Создайте контекстный менеджер с with","ans":"with open('file.txt') as f:","hint":"with выражение as переменная:"},
                    {"type":"choice","q":"Что делает @property?","options":["Создает getter","Создает метод","Удаляет атрибут"],"ans":"Создает getter","hint":"Декоратор для свойств"},
                    {"type":"input","q":"Распакуйте список [1,2,3] в переменные a,b,c","ans":"a, b, c = [1,2,3]","hint":"Множественное присваивание"},
                    {"type":"choice","q":"Что такое итератор?","options":["Объект с __iter__ и __next__","Список","Функция"],"ans":"Объект с __iter__ и __next__","hint":"Протокол итерации"},
                ],
                [
                    {"type":"input","q":"Создайте метакласс","ans":"class Meta(type):","hint":"Наследуется от type"},
                    {"type":"choice","q":"Что делает functools.wraps?","options":["Сохраняет метаданные функции","Оборачивает функцию","Удаляет функцию"],"ans":"Сохраняет метаданные функции","hint":"Для декораторов"},
                    {"type":"input","q":"Создайте абстрактный класс","ans":"from abc import ABC","hint":"Импорт из модуля abc"},
                    {"type":"choice","q":"Что такое GIL?","options":["Global Interpreter Lock","Garbage In List","Get Input Line"],"ans":"Global Interpreter Lock","hint":"Глобальная блокировка интерпретатора"},
                    {"type":"input","q":"Используйте asyncio для создания корутины","ans":"async def func():","hint":"async def название():"},
                ],
                [
                    {"type":"choice","q":"Что делает __call__?","options":["Делает объект вызываемым","Инициализирует","Удаляет"],"ans":"Делает объект вызываемым","hint":"Позволяет вызывать объект как функцию"},
                    {"type":"input","q":"Создайте дескриптор","ans":"class Desc: def __get__(self, obj, type):","hint":"Методы __get__, __set__, __delete__"},
                    {"type":"choice","q":"Что такое monkey patching?","options":["Изменение кода во время выполнения","Отладка","Тестирование"],"ans":"Изменение кода во время выполнения","hint":"Динамическое изменение"},
                    {"type":"input","q":"Создайте одиночку (Singleton)","ans":"class Single(type): _instances = {}","hint":"Метакласс с контролем экземпляров"},
                    {"type":"choice","q":"Что делает __slots__?","options":["Ограничивает атрибуты","Создает слоты","Удаляет класс"],"ans":"Ограничивает атрибуты","hint":"Оптимизация памяти"},
                ],
                [
                    {"type":"input","q":"Создайте type hint для функции","ans":"def func(x: int) -> int:","hint":"параметр: тип -> возвращаемый_тип"},
                    {"type":"choice","q":"Что такое корутина?","options":["Асинхронная функция","Обычная функция","Класс"],"ans":"Асинхронная функция","hint":"Функция с async"},
                    {"type":"input","q":"Создайте data class","ans":"from dataclasses import dataclass","hint":"Импорт декоратора dataclass"},
                    {"type":"choice","q":"Что делает __enter__ и __exit__?","options":["Реализуют протокол контекстного менеджера","Входят в класс","Выходят из программы"],"ans":"Реализуют протокол контекстного менеджера","hint":"Для использования с with"},
                    {"type":"input","q":"Используйте walrus operator","ans":"if (x := 5) > 3:","hint":"Оператор :="},
                ],
            ]
    else:  # JavaScript
        if difficulty == "Easy":
            return [
                [
                    {"type":"choice","q":"Что выведет console.log(2 + 2)?","options":["4","22","Ошибка"],"ans":"4","hint":"Сложение чисел"},
                    {"type":"input","q":"Выведите текст 'Hello' в консоль","ans":"console.log('Hello')","hint":"Используйте console.log()"},
                    {"type":"choice","q":"Как объявить переменную?","options":["let x = 5","x = 5","var x := 5"],"ans":"let x = 5","hint":"Ключевое слово let"},
                    {"type":"input","q":"Создайте константу PI со значением 3.14","ans":"const PI = 3.14","hint":"Используйте const"},
                    {"type":"choice","q":"Что такое typeof?","options":["Оператор типа","Функция","Переменная"],"ans":"Оператор типа","hint":"Определяет тип данных"},
                ],
                [
                    {"type":"input","q":"Создайте массив с числами 1, 2, 3","ans":"[1, 2, 3]","hint":"Квадратные скобки"},
                    {"type":"choice","q":"Как начать цикл for?","options":["for (let i = 0; i < 5; i++)","for i in range(5)","loop i to 5"],"ans":"for (let i = 0; i < 5; i++)","hint":"for (инициализация; условие; шаг)"},
                    {"type":"input","q":"Получите первый элемент массива arr","ans":"arr[0]","hint":"Индексация с 0"},
                    {"type":"choice","q":"Как добавить элемент в массив?","options":["arr.push(x)","arr.append(x)","arr.add(x)"],"ans":"arr.push(x)","hint":"Метод push"},
                    {"type":"input","q":"Получите длину массива arr","ans":"arr.length","hint":"Свойство length"},
                ],
                [
                    {"type":"choice","q":"Как объявить функцию?","options":["function name() {}","def name():","func name() {}"],"ans":"function name() {}","hint":"Ключевое слово function"},
                    {"type":"input","q":"Создайте функцию hello без параметров","ans":"function hello() {}","hint":"function имя() {}"},
                    {"type":"choice","q":"Что делает return?","options":["Возвращает значение","Выводит в консоль","Удаляет функцию"],"ans":"Возвращает значение","hint":"Возврат результата"},
                    {"type":"input","q":"Создайте стрелочную функцию","ans":"() => {}","hint":"Синтаксис () => {}"},
                    {"type":"choice","q":"Как начать условие?","options":["if (x > 5) {}","if x > 5:","when x > 5 {}"],"ans":"if (x > 5) {}","hint":"if (условие) {}"},
                ],
                [
                    {"type":"input","q":"Создайте объект с полем name: 'Bob'","ans":"{name: 'Bob'}","hint":"Фигурные скобки"},
                    {"type":"choice","q":"Как получить значение из объекта?","options":["obj.key","obj[key]","Оба варианта"],"ans":"Оба варианта","hint":"Точечная и скобочная нотация"},
                    {"type":"input","q":"Преобразуйте '5' в число","ans":"Number('5')","hint":"Функция Number() или parseInt()"},
                    {"type":"choice","q":"Что такое null?","options":["Отсутствие значения","Ошибка","Функция"],"ans":"Отсутствие значения","hint":"Специальное значение"},
                    {"type":"input","q":"Объявите переменную x без инициализации","ans":"let x","hint":"let имя без значения"},
                ],
                [
                    {"type":"choice","q":"Что делает JSON.parse()?","options":["Парсит JSON строку","Создает JSON","Удаляет JSON"],"ans":"Парсит JSON строку","hint":"Преобразует строку в объект"},
                    {"type":"input","q":"Создайте цикл while с условием x < 10","ans":"while (x < 10) {}","hint":"while (условие) {}"},
                    {"type":"choice","q":"Что делает break?","options":["Прерывает цикл","Пропускает итерацию","Ничего"],"ans":"Прерывает цикл","hint":"Останавливает выполнение"},
                    {"type":"input","q":"Получите ключи объекта obj","ans":"Object.keys(obj)","hint":"Object.keys()"},
                    {"type":"choice","q":"Что вернет typeof []?","options":["object","array","list"],"ans":"object","hint":"Массив - это объект"},
                ],
            ]
        elif difficulty == "Medium":
            return [
                [
                    {"type":"input","q":"Создайте функцию с параметром x","ans":"function func(x) {}","hint":"function имя(параметр) {}"},
                    {"type":"choice","q":"Что делает метод map()?","options":["Преобразует массив","Фильтрует массив","Сортирует массив"],"ans":"Преобразует массив","hint":"Применяет функцию к каждому элементу"},
                    {"type":"input","q":"Используйте map для удвоения arr","ans":"arr.map(x => x * 2)","hint":"arr.map(функция)"},
                    {"type":"choice","q":"Что делает filter()?","options":["Фильтрует элементы","Преобразует элементы","Удаляет массив"],"ans":"Фильтрует элементы","hint":"Отбирает элементы по условию"},
                    {"type":"input","q":"Отфильтруйте arr по условию x > 5","ans":"arr.filter(x => x > 5)","hint":"arr.filter(условие)"},
                ],
                [
                    {"type":"choice","q":"Что такое деструктуризация?","options":["Извлечение значений","Удаление объекта","Создание копии"],"ans":"Извлечение значений","hint":"Распаковка структур"},
                    {"type":"input","q":"Деструктурируйте массив [1,2] в a,b","ans":"let [a, b] = [1, 2]","hint":"let [переменные] = массив"},
                    {"type":"choice","q":"Что делает spread оператор ...?","options":["Распыляет элементы","Удаляет элементы","Сортирует"],"ans":"Распыляет элементы","hint":"Раскрывает массив/объект"},
                    {"type":"input","q":"Объедините массивы [1,2] и [3,4]","ans":"[...[1,2], ...[3,4]]","hint":"Используйте spread ..."},
                    {"type":"choice","q":"Что такое промис (Promise)?","options":["Объект для асинхронности","Функция","Переменная"],"ans":"Объект для асинхронности","hint":"Для работы с асинхронным кодом"},
                ],
                [
                    {"type":"input","q":"Создайте промис, который резолвится","ans":"new Promise(resolve => resolve())","hint":"new Promise((resolve, reject) => {})"},
                    {"type":"choice","q":"Что делает async/await?","options":["Упрощает работу с промисами","Создает функцию","Удаляет промис"],"ans":"Упрощает работу с промисами","hint":"Синтаксический сахар"},
                    {"type":"input","q":"Создайте async функцию","ans":"async function func() {}","hint":"async перед function"},
                    {"type":"choice","q":"Что делает метод reduce()?","options":["Сворачивает массив в значение","Фильтрует","Сортирует"],"ans":"Сворачивает массив в значение","hint":"Аккумулирует результат"},
                    {"type":"input","q":"Суммируйте массив [1,2,3] через reduce","ans":"[1,2,3].reduce((a,b) => a+b, 0)","hint":"reduce((acc, val) => acc + val, начальное)"},
                ],
                [
                    {"type":"choice","q":"Что такое замыкание?","options":["Функция с доступом к внешним переменным","Цикл","Класс"],"ans":"Функция с доступом к внешним переменным","hint":"Closure - захват переменных"},
                    {"type":"input","q":"Создайте класс Car","ans":"class Car {}","hint":"class Название {}"},
                    {"type":"choice","q":"Что делает constructor?","options":["Инициализирует объект","Удаляет объект","Копирует"],"ans":"Инициализирует объект","hint":"Конструктор класса"},
                    {"type":"input","q":"Создайте геттер для свойства name","ans":"get name() {}","hint":"get имя() {}"},
                    {"type":"choice","q":"Что такое this?","options":["Ссылка на текущий объект","Функция","Переменная"],"ans":"Ссылка на текущий объект","hint":"Контекст выполнения"},
                ],
                [
                    {"type":"input","q":"Создайте модуль с экспортом","ans":"export const x = 5","hint":"export перед объявлением"},
                    {"type":"choice","q":"Что делает import?","options":["Импортирует модуль","Экспортирует","Удаляет"],"ans":"Импортирует модуль","hint":"Загружает зависимости"},
                    {"type":"input","q":"Импортируйте x из модуля 'mod'","ans":"import { x } from 'mod'","hint":"import { имя } from 'путь'"},
                    {"type":"choice","q":"Что такое Set?","options":["Множество уникальных значений","Массив","Объект"],"ans":"Множество уникальных значений","hint":"Коллекция без дубликатов"},
                    {"type":"input","q":"Создайте Set с элементами 1,2,3","ans":"new Set([1, 2, 3])","hint":"new Set(массив)"},
                ],
            ]
        else:  # Hard
            return [
                [
                    {"type":"choice","q":"Что такое Event Loop?","options":["Цикл обработки событий","Цикл for","Функция"],"ans":"Цикл обработки событий","hint":"Механизм асинхронности"},
                    {"type":"input","q":"Создайте генератор функцию","ans":"function* gen() {}","hint":"function* с yield"},
                    {"type":"choice","q":"Что делает yield?","options":["Приостанавливает выполнение","Возвращает значение","Удаляет функцию"],"ans":"Приостанавливает выполнение","hint":"Пауза в генераторе"},
                    {"type":"input","q":"Создайте Proxy для объекта obj","ans":"new Proxy(obj, {})","hint":"new Proxy(target, handler)"},
                    {"type":"choice","q":"Что такое Symbol?","options":["Уникальный примитив","Строка","Число"],"ans":"Уникальный примитив","hint":"Гарантированно уникальный идентификатор"},
                ],
                [
                    {"type":"input","q":"Создайте WeakMap","ans":"new WeakMap()","hint":"new WeakMap()"},
                    {"type":"choice","q":"Отличие WeakMap от Map?","options":["Ключи - только объекты","Нет отличий","Ключи - только строки"],"ans":"Ключи - только объекты","hint":"Слабые ссылки на объекты"},
                    {"type":"input","q":"Используйте Reflect.get на объекте obj","ans":"Reflect.get(obj, 'key')","hint":"Reflect.get(target, propertyKey)"},
                    {"type":"choice","q":"Что делает Object.freeze()?","options":["Замораживает объект","Копирует объект","Удаляет"],"ans":"Замораживает объект","hint":"Делает неизменяемым"},
                    {"type":"input","q":"Создайте итератор для объекта","ans":"obj[Symbol.iterator] = function() {}","hint":"Определите Symbol.iterator"},
                ],
                [
                    {"type":"choice","q":"Что такое Temporal Dead Zone?","options":["Зона до инициализации let/const","Временная функция","Удаленная зона"],"ans":"Зона до инициализации let/const","hint":"TDZ - недоступность до объявления"},
                    {"type":"input","q":"Создайте приватное поле #x в классе","ans":"class C { #x }","hint":"# перед именем поля"},
                    {"type":"choice","q":"Что делает Intl API?","options":["Интернационализация","Интеграция","Инициализация"],"ans":"Интернационализация","hint":"Форматирование по локали"},
                    {"type":"input","q":"Создайте ArrayBuffer размером 8","ans":"new ArrayBuffer(8)","hint":"new ArrayBuffer(размер)"},
                    {"type":"choice","q":"Что такое TypedArray?","options":["Массив с типизацией","Обычный массив","Строка"],"ans":"Массив с типизацией","hint":"Для бинарных данных"},
                ],
                [
                    {"type":"input","q":"Создайте SharedArrayBuffer","ans":"new SharedArrayBuffer(1024)","hint":"new SharedArrayBuffer(размер)"},
                    {"type":"choice","q":"Что делает Atomics?","options":["Атомарные операции","Создает атомы","Удаляет данные"],"ans":"Атомарные операции","hint":"Для многопоточности"},
                    {"type":"input","q":"Используйте BigInt для числа 9007199254740991","ans":"9007199254740991n","hint":"Добавьте n в конец"},
                    {"type":"choice","q":"Что такое WeakRef?","options":["Слабая ссылка на объект","Сильная ссылка","Функция"],"ans":"Слабая ссылка на объект","hint":"Не препятствует сборке мусора"},
                    {"type":"input","q":"Создайте FinalizationRegistry","ans":"new FinalizationRegistry(() => {})","hint":"new FinalizationRegistry(callback)"},
                ],
                [
                    {"type":"choice","q":"Что такое Web Workers?","options":["Фоновые потоки","Функции","Классы"],"ans":"Фоновые потоки","hint":"Многопоточность в браузере"},
                    {"type":"input","q":"Создайте async итератор","ans":"async function* gen() {}","hint":"async function* с yield"},
                    {"type":"choice","q":"Что делает Object.defineProperty?","options":["Определяет свойство с дескрипторами","Удаляет свойство","Копирует"],"ans":"Определяет свойство с дескрипторами","hint":"Тонкая настройка свойств"},
                    {"type":"input","q":"Используйте Optional chaining","ans":"obj?.prop","hint":"Оператор ?."},
                    {"type":"choice","q":"Что такое Nullish coalescing?","options":["Оператор ??","Оператор ||","Оператор &&"],"ans":"Оператор ??","hint":"Возвращает правую часть, если левая null/undefined"},
                ],
            ]

# ── СОХРАНЕНИЯ ───────────────────────────────────────────────
def load_progress():
    base = {"coins": 0, "inventory": ["default"], "active_skin": "default"}
    for l in ["Python", "JavaScript"]:
        base[l] = {d: {"level": 0, "task": 0} for d in ["Easy","Medium","Hard"]}
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not data: return base
        for k in ("coins","inventory","active_skin"):
            if k not in data: data[k] = base[k]
        if "PascalABC" in data:
            if "JavaScript" not in data: data["JavaScript"] = data["PascalABC"]
            del data["PascalABC"]
        if "JavaScript" not in data:
            data["JavaScript"] = {d: {"level":0,"task":0} for d in ["Easy","Medium","Hard"]}
        return data
    except:
        return base

def save_progress(data):
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def blit_text_outline(surf, text, font, color, outline_color, pos, outline=2):
    # pos = (x, y) — левый верхний угол
    base = font.render(text, True, color)
    x, y = pos

    # обводка
    for ox in range(-outline, outline + 1):
        for oy in range(-outline, outline + 1):
            if ox == 0 and oy == 0:
                continue
            surf.blit(font.render(text, True, outline_color), (x + ox, y + oy))

    # основной текст
    surf.blit(base, (x, y))
    return base.get_rect(topleft=pos)

# ── UI-КЛАССЫ ────────────────────────────────────────────────
class Button:
    def __init__(self, x, y, w, h, text, func, color=COLOR_BTN):
        self.rect  = pygame.Rect(x, y, w, h)
        self.text  = text
        self.func  = func
        self.color = color

    def draw(self, surf):
        col = COLOR_BTN_HOV if self.rect.collidepoint(pygame.mouse.get_pos()) else self.color
        pygame.draw.rect(surf, col,   self.rect, border_radius=10)
        pygame.draw.rect(surf, BLACK, self.rect, 2, border_radius=10)
        fs  = max(11, int(self.rect.h * 0.40))
        fnt = pygame.font.SysFont("Arial", fs)
        ts  = fnt.render(self.text, True, COLOR_TEXT)
        surf.blit(ts, ts.get_rect(center=self.rect.center))

    def check_click(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos) and self.func:
                self.func()

class InputBox:
    def __init__(self):
        self.rect   = pygame.Rect(0, 0, 400, 44)
        self.text   = ""
        self.active = False
        self.color  = GRAY

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
            self.color  = GOLD if self.active else GRAY
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_RETURN:
                return self.text
            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            else:
                self.text += event.unicode
        return None

    def draw(self, surf):
        pygame.draw.rect(surf, COLOR_UI_BG, self.rect)
        pygame.draw.rect(surf, self.color,  self.rect, 2)
        fs  = max(11, int(self.rect.h * 0.48))
        fnt = pygame.font.SysFont("Courier New", fs)
        ts  = fnt.render(self.text, True, COLOR_TEXT)
        surf.blit(ts, (self.rect.x+10, self.rect.y+(self.rect.h-ts.get_height())//2))


# ════════════════════════════════════════════════════════════
#  ИГРА
# ════════════════════════════════════════════════════════════
class Game:
    def __init__(self):
        self.state         = "SPLASH"
        self.data          = load_progress()
        self.cur_lang      = "Python"
        self.cur_diff      = "Easy"
        self.cur_level_idx = 0
        self.cur_task_idx  = 0
        self.tasks         = []
        self.hearts        = 3
        self.msg           = ""
        self.input_box     = InputBox()
        self.anim_timer    = 0.0
        self.splash_frames = 0
        self.max_splash    = int(FPS * 3.5)
        self.splash_bg     = pygame.Surface((WIDTH, HEIGHT)); self.splash_bg.fill(BLACK)
        self.splash_text   = font_splash.render("Froggy Coder", True, GREEN)

        self._menu_btns    = []
        self._shop_btns    = []
        self._diff_btns    = []
        self._map_circles  = []
        self._map_menu_r   = None
        self._choice_rects = []
        self._hint_btn     = None
        self._check_btn    = None
        self._pause_btns   = []
        self._win_menu_r   = None

        self._win_cache_size = (None, None)
        self._win_frogs = None

    # ── resize ──────────────────────────────────────────────
    def on_resize(self, w, h):
        global WIDTH, HEIGHT, BOLOTO, WIN, screen
        WIDTH, HEIGHT = w, h
        screen = pygame.display.set_mode((w, h), pygame.RESIZABLE)
        BOLOTO = _scale(BOLOTO_ORIGINAL, w, h)
        WIN    = _scale(WIN_ORIGINAL, w, h)

        # чтобы на SPLASH не было “старого” размера и артефактов
        self.splash_bg = pygame.Surface((w, h))
        self.splash_bg.fill(BLACK)

    # ── shortcuts ───────────────────────────────────────────
    def _f(self, sz, bold=False, mono=False):
        return pygame.font.SysFont("Courier New" if mono else "Arial", max(10, sz), bold=bold)

    def _ts(self): return max(18, int(40 * HEIGHT / 700))
    def _ms(self): return max(12, int(24 * HEIGHT / 700))

    def _mk_btn(self, cx, y, w, h, label, fn, color=COLOR_BTN):
        """Кнопка с центром по cx."""
        return Button(cx - w//2, y, w, h, label, fn, color)

    def _cx(self): return WIDTH // 2

    # ── “умная” проверка ответов (п.3) ──────────────────────
    def _norm(self, s: str) -> str:
        """Нормализация: убираем крайние пробелы + схлопываем любые пробелы/переносы."""
        s = (s or "").strip()
        s = " ".join(s.split())  # превращает \n и множественные пробелы в один пробел
        return s.lower().translate(SMART_QUOTES_TRANSLATION)

    def _norm_code(self, s: str) -> str:
        """Для кодовых ответов игнорируем пробелы вокруг пунктуации."""
        return re.sub(r"\s*([,.\[\]\(\)\{\}:+\-*/%=<>])\s*", r"\1", self._norm(s))

    def _is_correct(self, q: dict, user_ans: str) -> bool:
        """Поддерживает ans как строку или список строк."""
        if q["type"] == "choice":
            return user_ans.strip() == q["ans"]

        # input
        answers = q["ans"] if isinstance(q.get("ans"), list) else [q.get("ans", "")]
        ua = self._norm(user_ans)
        ua_code = self._norm_code(user_ans)
        for a in answers:
            if ua == self._norm(a) or ua_code == self._norm_code(a):
                return True
        return False

    # ── state ───────────────────────────────────────────────
    def change_state(self, s):
        self.state = s; self.msg = ""
        if s == "GAME":
            self.hearts = 3
            self.input_box.text = ""
        if s == "WIN":
            self.anim_timer = 0.0

    def set_lang(self, lang):  self.cur_lang = lang; self.change_state("DIFF")

    def set_diff(self, diff):
        self.cur_diff = diff
        self.tasks    = get_tasks(self.cur_lang, self.cur_diff)
        self.change_state("MAP")

    def reset_progress(self):
        try:
            if os.path.exists(SAVE_FILE): os.remove(SAVE_FILE)
        except: pass
        self.data = load_progress(); save_progress(self.data)
        self.msg  = "Прогресс сброшен!"

    def quit_game(self): pygame.quit(); sys.exit()

    def select_level(self, idx):
        prog = self.data[self.cur_lang][self.cur_diff]
        if idx <= prog["level"]:
            self.cur_level_idx = idx
            self.cur_task_idx  = 0 if idx < prog["level"] else prog["task"]
            if self.cur_level_idx == 4 and self.cur_task_idx >= 5:
                self.change_state("WIN")
            else:
                self.change_state("GAME")

    def show_hint(self):
        try:    self.msg = "Подсказка: " + self.tasks[self.cur_level_idx][self.cur_task_idx]["hint"]
        except: self.msg = "Нет задания"

    def buy_item(self, name, price):
        if name in self.data["inventory"]:
            self.data["active_skin"] = name; self.msg = f"{name} надет!"
        elif self.data["coins"] >= price:
            self.data["coins"] -= price; self.data["inventory"].append(name)
            self.data["active_skin"] = name; self.msg = f"Куплено: {name}!"
        else:
            self.msg = "Недостаточно монет!"
        save_progress(self.data)

    def check_answer(self, option_text=None):
        if self.cur_level_idx > 4: return
        tlist = self.tasks[self.cur_level_idx]
        if self.cur_task_idx >= len(tlist): return
        q = tlist[self.cur_task_idx]
        user_ans = self.input_box.text if option_text is None else option_text

        if self._is_correct(q, user_ans):
            self.msg = "Верно! +10 монет"; self.data["coins"] += 10
            self.cur_task_idx += 1
            prog = self.data[self.cur_lang][self.cur_diff]
            if self.cur_task_idx >= 5:
                self.cur_level_idx += 1; self.cur_task_idx = 0
                if self.cur_level_idx > prog["level"]:
                    prog["level"] = self.cur_level_idx; prog["task"] = 0
            else:
                if self.cur_level_idx == prog["level"]: prog["task"] = self.cur_task_idx
            save_progress(self.data)
            self.hearts = 3; self.input_box.text = ""
            if self.cur_level_idx == 5: self.change_state("WIN")
        else:
            self.hearts -= 1
            if self.hearts <= 0:
                self.msg = "0 сердец! Уровень начат заново."; self.hearts = 3
                self.cur_task_idx = 0
                prog = self.data[self.cur_lang][self.cur_diff]
                if self.cur_level_idx == prog["level"]: prog["task"] = 0
                save_progress(self.data)
            else:
                self.msg = f"Ошибка! Осталось сердец: {self.hearts}"

    # ── головные уборы (п.4) ────────────────────────────────
        # ── головные уборы (п.4) ────────────────────────────────
            # ── головные уборы (п.4) ────────────────────────────────
    def draw_hat(self, rect, kind="Cylinder", head_x_frac=0.5, head_y_frac=0.40, head_r_frac=0.22):
        """
        Рисует шляпу, привязанную к голове.
        head_x_frac/head_y_frac/head_r_frac — положение и радиус головы в долях от размера спрайта.
        """
        if kind == "None":
            return
        if kind != "Cylinder":
            return

        head_x = rect.x + rect.width  * head_x_frac
        head_y = rect.y + rect.height * head_y_frac
        head_r = rect.height * head_r_frac

        hw  = int(rect.width  * 0.40)
        hh  = int(rect.height * 0.45)
        brw = int(rect.width  * 0.62)

        brim_y = int(head_y - head_r * 0.85)
        top = brim_y - hh + 8
        cx = int(head_x)

        pygame.draw.rect(screen, BLACK, (cx - brw//2, brim_y, brw, 8))              # поля
        pygame.draw.rect(screen, BLACK, (cx - hw//2,  top,   hw, hh))               # тулово
        pygame.draw.rect(screen, RED,   (cx - hw//2,  top + int(hh*0.58), hw, 6))   # лента

    def draw_bow(self, rect, head_x_frac=0.5, head_y_frac=0.40, head_r_frac=0.22, side="left"):
        head_x = rect.x + rect.width  * head_x_frac
        head_y = rect.y + rect.height * head_y_frac
        head_r = rect.height * head_r_frac

        bs = int(rect.width * 0.12)
        bx = head_x - head_r * 0.55 if side == "left" else head_x + head_r * 0.55
        by = head_y - head_r * 0.85

        bx = int(bx); by = int(by)

        pygame.draw.circle(screen, PINK, (bx - bs//2, by), bs//2)
        pygame.draw.circle(screen, PINK, (bx + bs//2, by), bs//2)
        pygame.draw.circle(screen, RED,  (bx, by), bs//3)
    def _wrap_text(self, surf, text, rect, font, color, max_lines=4):
        words = text.split()
        lines, cur = [], []
        for w in words:
            test = font.render(" ".join(cur+[w]), True, color)
            if test.get_width() <= rect.width-20: cur.append(w)
            else:
                if cur: lines.append(" ".join(cur))
                cur = [w]
        if cur: lines.append(" ".join(cur))
        lines = lines[:max_lines]
        y = rect.y+10
        for line in lines:
            surf.blit(font.render(line, True, color), (rect.x+10, y))
            y += font.get_height()+4
        return y

    # ── win family cache (п.4) ───────────────────────────────
    def _get_win_frogs(self):
        """Генерирует увеличенную 'семью' под текущий размер окна (кеширует)."""
        if self._win_cache_size == (WIDTH, HEIGHT) and self._win_frogs is not None:
            return self._win_frogs

        base = min(WIDTH, HEIGHT)
        papa_sz = max(110, int(base * 0.18))
        mama_sz = max(110, int(base * 0.18))
        sis_sz  = max(90,  int(base * 0.14))
        bro_sz  = max(85,  int(base * 0.13))

        papa = create_frog(papa_sz, GREEN, has_tie=True)
        mama = create_frog(mama_sz, (100,200,100), has_bow=False)
        sis  = create_frog(sis_sz, (150,220,150), has_bow=False, smaller=True)
        bro  = create_frog(bro_sz, (80,180,80), has_tie=True, smaller=True)

        # игрок на WIN тоже слегка увеличен (празднично)
        player_sz = max(95, int(base * 0.15))
        player = pygame.transform.smoothscale(FROG_IMG_RAW, (player_sz, player_sz))

        self._win_cache_size = (WIDTH, HEIGHT)
        self._win_frogs = {"papa": papa, "mama": mama, "sis": sis, "bro": bro, "player": player}
        return self._win_frogs

    # ═══════════════════════════════════════════════════════
    #  DRAW
    # ═══════════════════════════════════════════════════════
    def draw(self):
        CX = self._cx()

        # SPLASH
        if self.state == "SPLASH":
            self.splash_frames += 1
            ft=FPS*1.5; fb=FPS*2.5
            at=max(0,255-int((max(0,self.splash_frames-ft)/FPS)*255))
            ab=max(0,255-int((max(0,self.splash_frames-fb)/FPS)*255))
            if self.splash_frames >= self.max_splash: self.change_state("MENU"); return
            screen.fill(BLACK)
            self.splash_bg.set_alpha(ab);   screen.blit(self.splash_bg,(0,0))
            self.splash_text.set_alpha(at); screen.blit(self.splash_text,(CX-self.splash_text.get_width()//2,HEIGHT//2-50))
            return

        # Фон — всегда болото (меню, игра, победа — один фон)
        screen.blit(BOLOTO, (0,0))

        ts=self._ts(); ms=self._ms()
        FT=self._f(ts,bold=True); FM=self._f(ms)

        # ── MENU ────────────────────────────────────────────
        if self.state == "MENU":
            BW,BH,GAP = 400,56,10
            t = "Froggy Coder"
            tmp = FT.render(t, True, GREEN)
            x = CX - tmp.get_width()//2
            y = int(HEIGHT*0.07)
            blit_text_outline(screen, t, FT, GREEN, BLACK, (x, y), outline=2)

            items=[
                ("Python",            lambda: self.set_lang("Python"),         COLOR_BTN),
                ("JavaScript",        lambda: self.set_lang("JavaScript"),      COLOR_BTN),
                ("Магазин",           lambda: self.change_state("SHOP"),        GOLD),
                ("Сбросить прогресс", self.reset_progress,                      RED),
                ("Выйти",             self.quit_game,                           GRAY),
            ]
            sy = int(HEIGHT*0.20)
            self._menu_btns=[]
            for label,fn,col in items:
                b=self._mk_btn(CX,sy,BW,BH,label,fn,col); b.draw(screen)
                self._menu_btns.append(b); sy+=BH+GAP

            if self.msg:
                ms_=FM.render(self.msg,True,GOLD); screen.blit(ms_,(CX-ms_.get_width()//2,int(HEIGHT*0.88)))

        # ── SHOP ────────────────────────────────────────────
        elif self.state == "SHOP":
            BW,BH,GAP=400,56,14
            # Заголовок с обводкой
            t = "Магазин аксессуаров"
            tmp = FT.render(t, True, GOLD)
            x = CX - tmp.get_width()//2
            y = int(HEIGHT*0.07)
            blit_text_outline(screen, t, FT, GOLD, BLACK, (x, y), outline=3)

            # Монеты с обводкой
            coins_text = f"Ваши монеты: {self.data['coins']}"
            tmp2 = FM.render(coins_text, True, WHITE)
            x2 = CX - tmp2.get_width()//2
            y2 = int(HEIGHT*0.18)
            blit_text_outline(screen, coins_text, FM, WHITE, BLACK, (x2, y2), outline=2)

            items=[
                ("Цилиндр (250 монет)", lambda: self.buy_item("Cylinder",250), GOLD),
                ("В меню",             lambda: self.change_state("MENU"),     COLOR_BTN),
            ]
            sy=int(HEIGHT*0.30); self._shop_btns=[]
            for label,fn,col in items:
                b=self._mk_btn(CX,sy,BW,BH,label,fn,col); b.draw(screen)
                self._shop_btns.append(b); sy+=BH+GAP

            if self.msg:
                ms_=FM.render(self.msg,True,GOLD); screen.blit(ms_,(CX-ms_.get_width()//2,int(HEIGHT*0.88)))

        # ── DIFF ────────────────────────────────────────────
        elif self.state == "DIFF":
            BW,BH,GAP=400,60,18
            t = f"Язык: {self.cur_lang}"
            tmp = FT.render(t, True, BLACK)
            x = CX - tmp.get_width()//2
            y = int(HEIGHT*0.10)
            blit_text_outline(screen, t, FT, BLACK, WHITE, (x, y), outline=2)

            items=[
                ("Легкая",  lambda: self.set_diff("Easy"),   (80,200,80)),
                ("Средняя", lambda: self.set_diff("Medium"),  GOLD),
                ("Сложная", lambda: self.set_diff("Hard"),    RED),
            ]
            sy=int(HEIGHT*0.28); self._diff_btns=[]
            for label,fn,col in items:
                b=self._mk_btn(CX,sy,BW,BH,label,fn,col); b.draw(screen)
                self._diff_btns.append(b); sy+=BH+GAP

        # ── MAP ─────────────────────────────────────────────
        elif self.state == "MAP":
            prog=self.data[self.cur_lang][self.cur_diff]; saved=prog["level"]

            # Шапка
            HDR=70
            pygame.draw.rect(screen,COLOR_UI_BG,(0,0,WIDTH,HDR))
            hdr=FT.render(f"Карта: {self.cur_lang} ({self.cur_diff})",True,COLOR_TEXT)
            screen.blit(hdr,(20,HDR//2-hdr.get_height()//2))
            pygame.draw.circle(screen,GOLD,(WIDTH-80,HDR//2),14)
            ct=FM.render(f"x {self.data['coins']}",True,GOLD)
            screen.blit(ct,(WIDTH-80+20,HDR//2-ct.get_height()//2))

            # Линия
            LY=HEIGHT//2
            pygame.draw.line(screen,COLOR_UI_BG,(100,LY),(WIDTH-100,LY),10)

            self._map_circles=[]
            for i in range(5):
                r=i/4.0; cxi=int(150+r*(WIDTH-300))
                col=GOLD if i<saved else (GRAY if i==saved else RED)
                pygame.draw.circle(screen,col,(cxi,LY),40)
                pygame.draw.circle(screen,BLACK,(cxi,LY),40,3)
                lbl=FT.render(str(i+1),True,BLACK)
                screen.blit(lbl,(cxi-lbl.get_width()//2,LY-lbl.get_height()//2))
                if i == saved:
                    frog_rect = FROG_ICON.get_rect(center=(cxi, LY-60))
                    screen.blit(FROG_ICON, frog_rect)

                    # если цилиндр активен — рисуем и тут
                    if self.data.get("active_skin") == "Cylinder":
                        self.draw_hat(
                            frog_rect,
                            "Cylinder",
                            head_x_frac=0.78,
                            head_y_frac=0.38,
                            head_r_frac=0.23
                        )

            # Подсказка
            hf=self._f(max(10,int(18*WIDTH/1000)))
            ht=hf.render("Нажми на уровень чтобы начать",True,COLOR_TEXT)
            hy=int(HEIGHT*0.74)
            pygame.draw.rect(screen,BLACK,(CX-ht.get_width()//2-10,hy,ht.get_width()+20,ht.get_height()+10),border_radius=6)
            screen.blit(ht,(CX-ht.get_width()//2,hy+5))

            # Кнопка «В меню»
            BW=min(280,int(WIDTH*0.28)); BH=50
            self._map_menu_r=pygame.Rect(CX-BW//2,int(HEIGHT*0.87),BW,BH)
            b=Button(self._map_menu_r.x,self._map_menu_r.y,BW,BH,"В меню",lambda:self.change_state("MENU"))
            b.rect=self._map_menu_r; b.draw(screen)

        # ── GAME ────────────────────────────────────────────
        elif self.state == "GAME":
            HDR  = 62
            M    = 14
            LEFT = 14
            MSG_H = 44
            BOTTOM_RESERVED = MSG_H + M

            pygame.draw.rect(screen, COLOR_UI_BG, (0, 0, WIDTH, HDR))
            info = FT.render(f"Уровень: {self.cur_level_idx+1}  |  Задание: {self.cur_task_idx+1}/5", True, COLOR_TEXT)
            screen.blit(info, (LEFT + M, HDR//2 - info.get_height()//2))

            HEART_R = 14; HEART_GAP = 36
            for i in range(self.hearts):
                pygame.draw.circle(screen, RED, (WIDTH - HEART_R - 10 - i*HEART_GAP, HDR//2), HEART_R)

            HW = 155; HH = 40
            hint_x = WIDTH - HW - M
            hint_y = HDR + M
            self._hint_btn = Button(hint_x, hint_y, HW, HH, "💡 Подсказка", self.show_hint, GOLD)
            self._hint_btn.draw(screen)

            iy  = HEIGHT - 90 + math.sin(pygame.time.get_ticks()/200.) * 5
            hr_ = FROG_IMG.get_rect(center=(50, iy))
            screen.blit(FROG_IMG, hr_)
            if self.data.get("active_skin") == "Cylinder":
                self.draw_hat(hr_, "Cylinder", head_x_frac=0.78, head_y_frac=0.38, head_r_frac=0.23)

            CONT_LEFT  = 105
            CONT_RIGHT = WIDTH - M
            CONT_W     = CONT_RIGHT - CONT_LEFT

            QT = hint_y + HH + M
            CONT_BOTTOM = HEIGHT - BOTTOM_RESERVED - M

            QH = max(80, int(HEIGHT * 0.15))
            if QT + QH > CONT_BOTTOM - 10:
                QH = max(60, CONT_BOTTOM - QT - 10)
            qr = pygame.Rect(CONT_LEFT, QT, CONT_W, QH)
            pygame.draw.rect(screen, (0, 0, 0), qr, border_radius=10)
            pygame.draw.rect(screen, (80, 80, 80), qr, 1, border_radius=10)
            qf = self._f(max(13, int(23 * WIDTH/1000)), bold=True)

            tlist = self.tasks[self.cur_level_idx]
            if self.cur_task_idx < len(tlist):
                q = tlist[self.cur_task_idx]
                self._wrap_text(screen, q["q"], qr, qf, COLOR_TEXT, max_lines=4)

                CT = QT + QH + M
                AVAIL_H = CONT_BOTTOM - CT

                if q["type"] == "choice":
                    n_opts = len(q["options"])
                    OG = 10
                    OH = max(44, min(70, (AVAIL_H - OG*(n_opts-1)) // n_opts))
                    self._choice_rects = []
                    for idx, opt in enumerate(q["options"]):
                        by = CT + idx * (OH + OG)
                        if by + OH > CONT_BOTTOM:
                            break
                        br  = pygame.Rect(CONT_LEFT, by, CONT_W, OH)
                        col = COLOR_BTN_HOV if br.collidepoint(pygame.mouse.get_pos()) else COLOR_BTN
                        pygame.draw.rect(screen, col,   br, border_radius=10)
                        pygame.draw.rect(screen, BLACK, br, 2, border_radius=10)
                        of  = self._f(max(12, int(20 * WIDTH/1000)))
                        ots = of.render(opt, True, COLOR_TEXT)
                        screen.blit(ots, ots.get_rect(center=br.center))
                        self._choice_rects.append((br, opt))

                elif q["type"] == "input":
                    IH  = 48
                    CKW = 170
                    G   = 10
                    self.input_box.rect = pygame.Rect(CONT_LEFT, CT, CONT_W - CKW - G, IH)
                    self.input_box.draw(screen)
                    self._check_btn = Button(CONT_LEFT + CONT_W - CKW, CT, CKW, IH, "✔ Проверить", self.check_answer, GREEN)
                    self._check_btn.draw(screen)

            if self.msg:
                my   = HEIGHT - MSG_H - 10
                good = "Верно" in self.msg or "Подсказка" in self.msg
                mf   = FM.render(self.msg, True, GOLD if good else RED)
                bg   = pygame.Rect(CX - mf.get_width()//2 - 16, my, mf.get_width() + 32, MSG_H)
                pygame.draw.rect(screen, BLACK, bg, border_radius=10)
                screen.blit(mf, (bg.x + 16, my + (MSG_H - mf.get_height())//2))

        # ── PAUSE ───────────────────────────────────────────
        elif self.state=="PAUSE":
            ov=pygame.Surface((WIDTH,HEIGHT),pygame.SRCALPHA); ov.fill((0,0,0,180))
            screen.blit(ov,(0,0))
            pt=FT.render("ПАУЗА",True,WHITE); screen.blit(pt,(CX-pt.get_width()//2,100))
            BW,BH,GAP=300,54,14
            self._pause_btns=[
                self._mk_btn(CX,200,  BW,BH,"Продолжить",lambda:self.change_state("GAME")),
                self._mk_btn(CX,200+BH+GAP,BW,BH,"В меню",lambda:self.change_state("MENU")),
            ]
            for b in self._pause_btns: b.draw(screen)

        # ── WIN ─────────────────────────────────────────────
        elif self.state == "WIN":
            # фон победы (теперь ресайзится в on_resize)
            screen.blit(WIN, (0,0))

            # получаем увеличенных лягушек (п.4)
            wf = self._get_win_frogs()
            papa = wf["papa"]; mama = wf["mama"]; sis = wf["sis"]; bro = wf["bro"]
            player_img = wf["player"]
                        # Семья лягушек внизу экрана (увеличено)
            family = [
                # name, surface, ox, hat_kind, hx, hy, hr, bow, bow_side
                ("papa", papa, 110, "Cylinder", 0.3125, 0.375, 0.225, False, None),
                ("mama", mama, 220, "None",     0.3125, 0.375, 0.225, True,  "left"),
                ("sis",  sis,  320, "None",     0.40,   0.45,  0.18,  True,  "left"),
                ("bro",  bro,  410, "Cylinder", 0.40,   0.45,  0.18,  False, None),
            ]

            base_y = HEIGHT - 70
            for _, srf, ox, hat_kind, hx, hy, hr, has_bow, bow_side in family:
                fl = pygame.transform.flip(srf, True, False)
                r = fl.get_rect(midbottom=(WIDTH//2 + ox, base_y))
                screen.blit(fl, r)

                if hat_kind != "None":
                    self.draw_hat(r, hat_kind, head_x_frac=hx, head_y_frac=hy, head_r_frac=hr)

                if has_bow:
                    self.draw_bow(r, head_x_frac=hx, head_y_frac=hy, head_r_frac=hr, side=bow_side)
            self.anim_timer += 0.05
            jcx = WIDTH//2 - int(min(WIDTH, HEIGHT) * 0.22)
            amp = int(min(WIDTH, HEIGHT) * 0.22)

            fx  = jcx + math.sin(self.anim_timer) * amp
            fy  = (HEIGHT - 120) - abs(math.cos(self.anim_timer)) * int(min(WIDTH, HEIGHT) * 0.22)

            nx  = jcx + math.sin(self.anim_timer + 0.1) * amp
            ny  = (HEIGHT - 120) - abs(math.cos(self.anim_timer + 0.1)) * int(min(WIDTH, HEIGHT) * 0.22)

            dx  = nx - fx; dy = ny - fy

            fs_ = pygame.transform.flip(player_img, True, False) if dx < 0 else player_img
            rot = pygame.transform.rotate(fs_, math.degrees(math.atan2(-dy, abs(dx))))
            rr  = rot.get_rect(center=(fx, fy))
            screen.blit(rot, rr)
            # игроку — шляпа, если куплен Cylinder
            if self.data.get("active_skin") == "Cylinder":
                self.draw_hat(rr, "Cylinder", head_x_frac=0.5, head_y_frac=0.35, head_r_frac=0.22)

            txt = FT.render("ПОЗДРАВЛЯЕМ! КУРС ПРОЙДЕН!", True, GOLD)
            tw  = txt.get_width(); th = txt.get_height()
            tpx = CX - tw//2; tpy = int(HEIGHT * 0.12)
            pygame.draw.rect(screen, (0, 0, 0), (tpx - 16, tpy - 10, tw + 32, th + 20), border_radius=12)
            screen.blit(txt, (tpx, tpy))

            # Кнопка «В меню»
            BW = 260; BH = 50
            btn_y = int(HEIGHT * 0.30)
            self._win_menu_r = pygame.Rect(CX - BW//2, btn_y, BW, BH)
            b = Button(self._win_menu_r.x, self._win_menu_r.y, BW, BH, "В меню", lambda: self.change_state("MENU"))
            b.rect = self._win_menu_r; b.draw(screen)

    # ═══════════════════════════════════════════════════════
    #  EVENTS
    # ═══════════════════════════════════════════════════════
    def handle_events(self):
        for ev in pygame.event.get():
            if ev.type==pygame.VIDEORESIZE:   self.on_resize(*ev.size)
            if ev.type==pygame.QUIT:           self.quit_game()
            if self.state=="SPLASH":           continue

            if ev.type==pygame.KEYDOWN and ev.key==pygame.K_ESCAPE:
                if   self.state=="GAME":  self.state="PAUSE"
                elif self.state=="PAUSE": self.state="GAME"

            if self.state=="MENU":
                for b in self._menu_btns: b.check_click(ev)

            elif self.state=="SHOP":
                for b in self._shop_btns: b.check_click(ev)

            elif self.state=="DIFF":
                for b in self._diff_btns: b.check_click(ev)

            elif self.state=="MAP":
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    mx, my = ev.pos

                    # кнопка "В меню"
                    if self._map_menu_r and self._map_menu_r.collidepoint(mx, my):
                        self.change_state("MENU")
                    else:
                        # пересчитываем уровни прямо тут (не зависим от self._map_circles)
                        LY = HEIGHT // 2
                        for i in range(5):
                            r = i / 4.0
                            cxi = int(150 + r * (WIDTH - 300))
                            if math.hypot(mx - cxi, my - LY) < 40:
                                self.select_level(i)
                                break
            elif self.state=="GAME":
                if self._hint_btn:  self._hint_btn.check_click(ev)
                if self.cur_level_idx<len(self.tasks):
                    row=self.tasks[self.cur_level_idx]
                    if self.cur_task_idx<len(row):
                        q=row[self.cur_task_idx]
                        if q["type"]=="input":
                            ret = self.input_box.handle_event(ev)
                            # (п.2) Enter теперь = проверить
                            if ret is not None:
                                self.check_answer()
                            if self._check_btn: self._check_btn.check_click(ev)
                        elif q["type"]=="choice":
                            if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                                for br,opt in getattr(self,"_choice_rects",[]):
                                    if br.collidepoint(ev.pos): self.check_answer(opt)

            elif self.state=="PAUSE":
                for b in self._pause_btns: b.check_click(ev)

            elif self.state=="WIN":
                if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                    if self._win_menu_r and self._win_menu_r.collidepoint(ev.pos):
                        self.change_state("MENU")

# ── ЗАПУСК ──────────────────────────────────────────────────
if __name__ == "__main__":
    game = Game()
    print(f"Папка игры: {os.path.dirname(os.path.abspath(__file__))}")
    while True:
        game.handle_events()
        game.draw()
        pygame.display.flip()
        clock.tick(FPS)
