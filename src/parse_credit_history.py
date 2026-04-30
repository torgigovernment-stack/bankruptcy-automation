"""
Парсинг кредитной истории из НБКИ (PDF).
Извлекает список кредиторов с суммами долга.
"""
import subprocess
import sys
import re
import json
import os
from pathlib import Path


def _find_pdftotext() -> str:
    """Ищем pdftotext: сначала в bundled `bin/` (для PyInstaller), потом в PATH."""
    # Внутри PyInstaller-сборки sys._MEIPASS указывает на временную папку с ресурсами
    candidates = []
    if hasattr(sys, '_MEIPASS'):
        candidates.append(Path(sys._MEIPASS) / 'bin' / ('pdftotext.exe' if os.name == 'nt' else 'pdftotext'))
    # Рядом с исполняемым файлом
    exe_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent.parent
    candidates.append(exe_dir / 'bin' / ('pdftotext.exe' if os.name == 'nt' else 'pdftotext'))
    for c in candidates:
        if c.exists():
            return str(c)
    return 'pdftotext'  # fallback на системный


def extract_text(pdf_path: str) -> str:
    pdftotext_bin = _find_pdftotext()
    result = subprocess.run(
        [pdftotext_bin, pdf_path, '-'],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftotext failed: {result.stderr}")
    return result.stdout


def parse_creditors(text: str) -> list[dict]:
    creditors = []

    # Split into creditor blocks by numbered sections
    blocks = re.split(r'\n(?=\d+\. .+ - Договор)', text)

    for block in blocks[1:]:
        creditor = {}

        # --- Название кредитора (из первой строки) ---
        first_line = block.split('\n')[0]
        name_match = re.match(r'\d+\. (.+?) - Договор', first_line)
        if not name_match:
            continue
        creditor['name'] = name_match.group(1).strip()

        # --- ОГРН / ИНН (ищем пару 13-значный + 10-значный) ---
        ogrn_inn = re.search(r'(\d{13})\s*\n(\d{10,12})', block)
        if ogrn_inn:
            creditor['ogrn'] = ogrn_inn.group(1)
            creditor['inn'] = ogrn_inn.group(2)

        # --- УИд договора ---
        uid_match = re.search(r'УИд договора:\s*([a-f0-9\-]+-\w+)', block)
        if uid_match:
            creditor['uid'] = uid_match.group(1)

        # --- Номер договора ---
        contract_match = re.search(r'Номер договора:\s*([^\n]+)', block)
        if contract_match:
            creditor['contract_number'] = contract_match.group(1).strip()

        # --- Дата сделки ---
        date_match = re.search(r'(\d{2}-\d{2}-\d{4})\s*\nДоговор займа', block)
        if date_match:
            creditor['contract_date'] = date_match.group(1)

        # --- Переуступка долга: берём нового кредитора ---
        # Формат: Сведения о приобретателе → имя (ООО/АО/...) → 13-значный ОГРН → "ИНН РФ" → 10-значный ИНН
        transfer_start = block.find('Сведения о приобретателе прав кредитора')
        transfer_found = False
        if transfer_start >= 0:
            transfer_tail = block[transfer_start:]
            # Ограничиваем секцию до маркеров конца блока приобретателя
            for end_marker in ('Сведения о прекращении передачи', 'Сведения о судебных', 'Сведения об источнике формирования'):
                idx = transfer_tail.find(end_marker)
                if idx > 0:
                    transfer_tail = transfer_tail[:idx]
                    break
            # ОГРН+ИНН приобретателя разделены строкой "ИНН РФ"
            ogr_inn = re.search(r'(\d{13})\s*\nИНН РФ\s*\n(\d{10,12})', transfer_tail)
            if ogr_inn:
                before_ogrn = transfer_tail[:ogr_inn.start()]
                # Берём наиболее длинное сокращённое название (ООО/АО/...) до ОГРН
                names = re.findall(r'((?:ООО|АО|ЗАО|ПАО|ПКО|МКК|МФК|СФО|НКО)[^\n]{2,60})', before_ogrn)
                if names:
                    # Выбираем самый длинный вариант — обычно содержит полное сокращённое название
                    best = max(names, key=len)
                    transferred_name = re.sub(r'[«»]', '"', best.strip())
                    creditor['transferred_to'] = transferred_name
                    creditor['transferred_to_ogrn'] = ogr_inn.group(1)
                    creditor['transferred_to_inn'] = ogr_inn.group(2)
                    creditor['creditor_name'] = transferred_name
                    creditor['creditor_inn'] = ogr_inn.group(2)
                    transfer_found = True
        if not transfer_found:
            creditor['creditor_name'] = creditor['name']
            creditor['creditor_inn'] = creditor.get('inn', '')

        # --- Текущий остаток долга (последняя строка в таблице Задолженность) ---
        # Ищем последнюю запись: дата + суммы
        debt_rows = re.findall(
            r'\d{2}-\d{2}-\d{4}\s+(?:Да|Нет|Н/Д)\s+([\d\s]+,\d{2})',
            block
        )
        if debt_rows:
            last_amount_str = debt_rows[-1].replace(' ', '').replace(',', '.')
            try:
                creditor['current_debt'] = float(last_amount_str)
            except ValueError:
                pass

        # Если не нашли через таблицу — берём сумму из "Сумма и валюта"
        if 'current_debt' not in creditor:
            amount_match = re.search(r'([\d\s]+,\d{2}) RUB', block)
            if amount_match:
                amount_str = amount_match.group(1).replace(' ', '').replace(',', '.')
                try:
                    creditor['loan_amount'] = float(amount_str)
                    creditor['current_debt'] = float(amount_str)
                except ValueError:
                    pass

        # --- Тип займа (для "Содержание обязательства" в заявлении) ---
        loan_type_match = re.search(
            r'Договор займа \(кредита\)\s*\n([^\n]+)',
            block
        )
        if loan_type_match:
            creditor['loan_type'] = loan_type_match.group(1).strip()

        creditors.append(creditor)

    # Дедупликация по UID: если два блока имеют одинаковый UID — это переуступка.
    # Оставляем ПОСЛЕДНЮЮ запись (самый актуальный держатель долга).
    seen_uids: dict[str, int] = {}
    for i, c in enumerate(creditors):
        uid = c.get('uid')
        if uid:
            seen_uids[uid] = i  # перезаписываем — последний индекс побеждает

    deduped = []
    for i, c in enumerate(creditors):
        uid = c.get('uid')
        if not uid or seen_uids.get(uid) == i:
            deduped.append(c)

    return deduped


def main():
    input_path = Path(__file__).parent.parent / 'input' / 'credit_history.pdf'
    output_path = Path(__file__).parent.parent / 'output' / 'creditors.json'
    output_path.parent.mkdir(exist_ok=True)

    print(f"Читаем PDF: {input_path}")
    text = extract_text(str(input_path))

    print("Парсим кредиторов...")
    creditors = parse_creditors(text)

    print(f"\nНайдено кредиторов: {len(creditors)}")
    for i, c in enumerate(creditors, 1):
        print(f"  {i}. {c['creditor_name']} | ИНН: {c.get('creditor_inn', '?')} | Долг: {c.get('current_debt', '?')} руб.")

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(creditors, f, ensure_ascii=False, indent=2)

    print(f"\nСохранено в {output_path}")


if __name__ == '__main__':
    main()
