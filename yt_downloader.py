import random
import asyncio
import tkinter as tk
from tkinter import filedialog, messagebox
from pytubefix import YouTube
from pytubefix.cli import on_progress
import threading
import sys
import os
import pyperclip  # Для работы с буфером обмена
from tkinter import ttk  # Для Progress Bar
from tkinter import PhotoImage
import time

# Глобальные переменные для фильтрации
def resource_path(relative_path):
    """Возвращает абсолютный путь к ресурсу, совместимый с PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        # Если программа упакована, ищем в _MEIPASS
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# Обновляем путь к файлу blacklist.txt
blacklist_path = resource_path("blacklist.txt")

# Читаем файл
BLOCKED = [line.rstrip().encode() for line in open(blacklist_path, 'r', encoding='utf-8')]
TASKS = []

# Функция загрузки видео
def download_video(url, save_path, start_button, url_entry, progress_label, paste_button, save_path_button, save_path_entry, max_retries=3, delay=5):
    attempt = 0  # Счётчик попыток
    while attempt < max_retries:
        try:
            yt = YouTube(
                proxies={"http": "http://127.0.0.1:8881", "https": "http://127.0.0.1:8881"},
                url=url,
                on_progress_callback=on_progress
            )
            stream = yt.streams.get_highest_resolution()
            stream.download(save_path)
            messagebox.showinfo("Успех", f"Видео успешно загружено в: {save_path}")
            break  # Если загрузка успешна, выходим из цикла
        except Exception as e:
            attempt += 1
            if attempt < max_retries:
                #messagebox.showwarning("Предупреждение", f"Ошибка при загрузке видео: {e}. Повторная попытка через {delay} секунд.")
                print(f"Ошибка при загрузке видео: {e}. Повторная попытка через {delay} секунд.")
                break
            else:
                messagebox.showerror("Ошибка", f"Не удалось загрузить видео после {max_retries} попыток: {e}")
                print(f"Не удалось загрузить видео после {max_retries} попыток: {e}")
                break
        finally:
            # Включаем кнопки после завершения загрузки (успешной или с ошибкой)
            start_button.config(state="normal")
            url_entry.config(state="normal")
            save_path_entry.config(state="normal")
            paste_button.config(state="normal")
            save_path_button.config(state="normal")
            progress_label.config(text="Загрузка завершена")

# Асинхронный сервер
async def main(host, port):
    server = await asyncio.start_server(new_conn, host, port)
    await server.serve_forever()

async def pipe(reader, writer):
    while not reader.at_eof() and not writer.is_closing():
        try:
            writer.write(await reader.read(1500))
            await writer.drain()
        except:
            break
    writer.close()

async def new_conn(local_reader, local_writer):
    http_data = await local_reader.read(1500)
    try:
        type, target = http_data.split(b"\r\n")[0].split(b" ")[0:2]
        host, port = target.split(b":")
    except:
        local_writer.close()
        return
    if type != b"CONNECT":
        local_writer.close()
        return
    local_writer.write(b'HTTP/1.1 200 OK\n\n')
    await local_writer.drain()
    try:
        remote_reader, remote_writer = await asyncio.open_connection(host, port)
    except:
        local_writer.close()
        return
    if port == b'443':
        await fragment_data(local_reader, remote_writer)
    TASKS.append(asyncio.create_task(pipe(local_reader, remote_writer)))
    TASKS.append(asyncio.create_task(pipe(remote_reader, local_writer)))

async def fragment_data(local_reader, remote_writer):
    head = await local_reader.read(5)
    data = await local_reader.read(1500)
    parts = []
    if all([data.find(site) == -1 for site in BLOCKED]):
        remote_writer.write(head + data)
        await remote_writer.drain()
        return
    while data:
        part_len = random.randint(1, len(data))
        parts.append(bytes.fromhex("1603") + bytes([random.randint(0, 255)]) + int(
            part_len).to_bytes(2, byteorder='big') + data[0:part_len])
        data = data[part_len:]
    remote_writer.write(b''.join(parts))
    await remote_writer.drain()

# Запуск асинхронного сервера в отдельном потоке
def start_proxy():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main(host='127.0.0.1', port=8881))

# GUI-приложение
def main_gui():
    def start_download():
        url = url_entry.get()
        save_path = save_path_entry.get()
        if not url:
            messagebox.showwarning("Предупреждение", "Введите ссылку на видео.")
            return
        if not save_path:
            save_path = filedialog.askdirectory(title="Выберите папку для сохранения")
            if not save_path:
                messagebox.showwarning("Предупреждение", "Выберите папку для сохранения.")
                return
            save_path_entry.insert(0, save_path)

        # Блокируем интерфейс на время загрузки
        start_button.config(state="disabled")
        url_entry.config(state="disabled")
        save_path_entry.config(state="disabled")
        progress_label.config(text="Загрузка...")
        paste_button.config(state="disabled")
        save_path_button.config(state="disabled")
        # Запускаем загрузку в отдельном потоке с параметрами повторных попыток
        threading.Thread(target=download_video, args=(url, save_path, start_button, url_entry, progress_label, paste_button, save_path_button, save_path_entry), daemon=True).start()

    def insert_from_clipboard():
        clipboard_text = pyperclip.paste()
        if clipboard_text:
            url_entry.delete(0, tk.END)
            url_entry.insert(tk.END, clipboard_text)

    # Создание окна
    root = tk.Tk()
    root.title("Видео-загрузчик и прокси-сервер")
    root.geometry("400x350")
    icon_path = resource_path("icon.png")  # Путь к вашему файлу иконки (должен быть в формате PNG)
    icon = PhotoImage(file=icon_path)
    root.iconphoto(False, icon)

    # Поля ввода
    tk.Label(root, text="Введите ссылку на видео:").pack(pady=5)
    url_entry = tk.Entry(root, width=50)
    url_entry.pack(pady=5)

    tk.Label(root, text="Укажите путь для сохранения видео:").pack(pady=5)
    save_path_entry = tk.Entry(root, width=50)
    save_path_entry.pack(pady=5)
    save_path_button = tk.Button(root, text="Выбрать папку", command=lambda: save_path_entry.insert(0, filedialog.askdirectory()))
    save_path_button.pack(pady=5)

    # Кнопки
    start_button = tk.Button(root, text="Скачать видео", command=start_download)
    start_button.pack(pady=10)

    # Кнопка вставки текста из буфера обмена
    paste_button = tk.Button(root, text="Вставить из буфера обмена", command=insert_from_clipboard)
    paste_button.pack(pady=5)

    # Progress Bar
    progress_label = tk.Label(root, text="")
    progress_label.pack(pady=5)
    
    # Информация о прокси-сервере
    tk.Label(root, text="Прокси-сервер запущен на 127.0.0.1:8881").pack(pady=5)

    # Информация о разработчике
    developer_label = tk.Label(root, text="Разработано: Shubnechkin", font=("Arial", 8))
    developer_label.pack(pady=5)

    root.mainloop()

if __name__ == "__main__":
    # Скрытие консоли (только для Windows)
    if os.name == 'nt':
        import ctypes
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

    # Запуск прокси-сервера в фоновом режиме
    threading.Thread(target=start_proxy, daemon=True).start()

    # Запуск GUI
    main_gui()
