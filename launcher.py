"""
Запуск приложения для конечного пользователя.
Открывает браузер автоматически. При закрытии консоли сервер останавливается.
"""
import os
import sys
import time
import threading
import webbrowser
from pathlib import Path

# Если упакован PyInstaller — добавим путь к ресурсам
if hasattr(sys, '_MEIPASS'):
    os.chdir(sys._MEIPASS)
elif getattr(sys, 'frozen', False):
    os.chdir(Path(sys.executable).parent)

from web import app

PORT = 5001
URL = f'http://localhost:{PORT}'


def open_browser():
    time.sleep(1.5)  # ждём, пока сервер запустится
    webbrowser.open(URL)


if __name__ == '__main__':
    print('=' * 56)
    print(' Список кредиторов — банкротство')
    print('=' * 56)
    print(f' Открываем браузер: {URL}')
    print(' Чтобы выключить программу — закройте это окно')
    print('=' * 56)

    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host='127.0.0.1', port=PORT, debug=False, use_reloader=False)
