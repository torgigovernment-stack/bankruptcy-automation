"""
Пайплайн целиком: НБКИ + ИП → список кредиторов.
Запуск: python run.py
"""
import time
from pathlib import Path

start = time.time()
print("=" * 60)
print("Автоматизация списка кредиторов для банкротства")
print("=" * 60)

from src.parse_credit_history import extract_text, parse_creditors
from src.parse_proceedings import parse_proceedings
from src.matcher import match_proceedings_to_creditors, build_section2
from src.build_document import build_document
import json

base = Path(__file__).parent

# Шаг 1: Парсинг НБКИ
print("\n[1/4] Парсинг кредитной истории (НБКИ)...")
text = extract_text(str(base / 'input' / 'credit_history.pdf'))
creditors = parse_creditors(text)
print(f"      Найдено кредиторов: {len(creditors)}")

with open(base / 'output' / 'creditors.json', 'w', encoding='utf-8') as f:
    json.dump(creditors, f, ensure_ascii=False, indent=2)

# Шаг 2: Парсинг исполнительных производств
print("\n[2/4] Парсинг исполнительных производств...")
proceedings = parse_proceedings(str(base / 'input' / 'enforcement_proceedings.docx'))
print(f"      Найдено ИП: {len(proceedings)}")
by_type = {}
for p in proceedings:
    by_type.setdefault(p['type'], []).append(p)
for t, items in by_type.items():
    print(f"      • {t}: {len(items)}")

with open(base / 'output' / 'proceedings.json', 'w', encoding='utf-8') as f:
    json.dump(proceedings, f, ensure_ascii=False, indent=2)

# Шаг 3: Матчинг
print("\n[3/4] Сопоставление ИП с кредиторами...")
creditors, unmatched = match_proceedings_to_creditors(creditors, proceedings)
matched_count = sum(1 for c in creditors if c['proceedings'])
print(f"      Кредиторов со связанными ИП: {matched_count}/{len(creditors)}")
if unmatched:
    print(f"      Не сматчено (в unmatched.json): {len(unmatched)}")

section2 = build_section2(proceedings)  # кредитные ИП тоже дают исп.сборы в Раздел II
print(f"      Записей в Разделе II: {len(section2)}")

matched = {'section1': creditors, 'section2': section2, 'unmatched': unmatched}
with open(base / 'output' / 'matched.json', 'w', encoding='utf-8') as f:
    json.dump(matched, f, ensure_ascii=False, indent=2)
with open(base / 'output' / 'unmatched.json', 'w', encoding='utf-8') as f:
    json.dump(unmatched, f, ensure_ascii=False, indent=2)

# Шаг 4: Генерация документа
print("\n[4/4] Генерация документа Word...")
output_path = base / 'output' / 'final_creditors_list.docx'
build_document(matched, str(base / 'input' / 'creditors_template.docx'), str(output_path))

elapsed = time.time() - start
print(f"\n{'=' * 60}")
print(f"Готово за {elapsed:.1f} секунд!")
print(f"Документ: {output_path}")
print(f"{'=' * 60}")
