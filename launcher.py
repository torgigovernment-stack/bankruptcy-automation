"""
Запуск приложения для конечного пользователя.
Открывает браузер автоматически. При закрытии консоли сервер останавливается.
"""
import os
import sys
import time
import threading
import traceback
import webbrowser
from pathlib import Path

# Путь, рядом с которым будем писать логи и где лежит .exe
EXE_DIR = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
LOG_FILE = EXE_DIR / 'launcher_log.txt'


def log(msg: str):
    """Пишем и в консоль, и в файл — чтобы можно было посмотреть пост-фактум."""
    line = f'[{time.strftime("%H:%M:%S")}] {msg}'
    print(line, flush=True)
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


def main():
    log('=' * 56)
    log(' Список кредиторов — банкротство')
    log('=' * 56)
    log(f' Python: {sys.version.split()[0]}')
    log(f' frozen: {getattr(sys, "frozen", False)}')
    log(f' _MEIPASS: {getattr(sys, "_MEIPASS", "—")}')
    log(f' EXE_DIR: {EXE_DIR}')

    # Если упакован PyInstaller — переходим в папку с ресурсами
    if hasattr(sys, '_MEIPASS'):
        os.chdir(sys._MEIPASS)
        log(f' Working dir: {os.getcwd()}')

    log(' Импортируем веб-приложение...')
    from web import app
    log(' OK')

    PORT = 5001
    URL = f'http://localhost:{PORT}'

    def open_browser():
        time.sleep(1.5)
        log(f' Открываем браузер: {URL}')
        webbrowser.open(URL)

    log('=' * 56)
    log(f' Адрес: {URL}')
    log(' Чтобы выключить программу — закройте это окно')
    log('=' * 56)

    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host='127.0.0.1', port=PORT, debug=False, use_reloader=False)


if __name__ == '__main__':
    # Очищаем старый лог
    try:
        if LOG_FILE.exists():
            LOG_FILE.unlink()
    except Exception:
        pass

    try:
        main()
    except Exception:
        err = traceback.format_exc()
        log('!!! ПРОИЗОШЛА ОШИБКА !!!')
        log(err)
        try:
            input('\nЧтобы закрыть окно — нажмите Enter...')
        except Exception:
            # Если stdin недоступен — ждём 60 секунд, чтобы успеть прочитать
            time.sleep(60)
        sys.exit(1)
