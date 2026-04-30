# Список кредиторов — автоматизация для банкротства

Извлекает данные о кредиторах из НБКИ (PDF) и исполнительных производств с Госуслуг (DOCX), сопоставляет их и формирует готовый Word-документ для заявления о банкротстве.

## Запуск локально (для разработки)

```bash
pip install -r requirements.txt
python3 web.py
# открыть http://localhost:5001
```

## Сборка Windows EXE

Сборка идёт автоматически через GitHub Actions при push в main. Готовый `.exe` появляется в **Actions → последний run → Artifacts**.

Ручная сборка на Windows:
```powershell
pip install -r requirements.txt pyinstaller
# скачать pdftotext.exe + .dll из poppler-windows в bin/
pyinstaller build.spec
# результат: dist/Список_кредиторов.exe
```

## Структура

- `src/parse_credit_history.py` — парсинг PDF из НБКИ
- `src/parse_proceedings.py` — парсинг DOCX из Госуслуг
- `src/matcher.py` — сопоставление кредиторов и ИП
- `src/build_document.py` — генерация финального Word-документа
- `web.py` — Flask-интерфейс для пользователя
- `launcher.py` — точка входа для PyInstaller
- `run.py` — CLI-запуск всего пайплайна

## Конфиденциальность

Все данные обрабатываются локально, ничего не отправляется в интернет.
