"""
Сопоставляет исполнительные производства с кредиторами из НБКИ.
"""
import re
import json
from pathlib import Path
from difflib import SequenceMatcher


# Слова-заглушки, которые убираем при нормализации названий
_NOISE = re.compile(
    r'\b(ПАО|ООО|АО|ЗАО|МКК|МФК|ПКО|ОАО|НКО|СФО|БАНК|")\b',
    re.IGNORECASE
)


def normalize(name: str) -> str:
    """Убираем правовые формы и кавычки, приводим к нижнему регистру."""
    if not name:
        return ''
    name = _NOISE.sub('', name)
    name = re.sub(r'[«»"\'.,]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip().lower()
    return name


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def match_proceedings_to_creditors(
    creditors: list[dict],
    proceedings: list[dict],
    threshold: float = 0.55
) -> tuple[list[dict], list[dict]]:
    """
    Для каждого кредитора ищем связанные ИП по имени взыскателя.
    Если нашли — обновляем имя кредитора на имя взыскателя (актуальный держатель).
    Возвращает (matched_creditors, unmatched_proceedings).
    """
    used_ip_numbers = set()
    credit_procs = [p for p in proceedings if p['type'] in ('кредит', 'прочее') and p.get('claimant')]

    for creditor in creditors:
        creditor['proceedings'] = []
        cred_name = creditor.get('creditor_name', '')
        best_score = 0
        best_proc = None

        for proc in credit_procs:
            if proc['number'] in used_ip_numbers:
                continue
            claimant = proc.get('claimant') or ''
            score = similarity(cred_name, claimant)
            if score >= threshold and score > best_score:
                best_score = score
                best_proc = proc

        if best_proc:
            proc = best_proc
            claimant = proc.get('claimant') or ''
            creditor['proceedings'].append({
                'ip_number': proc['number'],
                'ip_date': proc['date_start'],
                'claimant': claimant,
                'amount_principal': proc.get('amount_principal'),
                'amount_fee': proc.get('amount_fee'),
                'basis_doc': proc.get('basis_doc'),
                'match_score': round(best_score, 2),
            })
            used_ip_numbers.add(proc['number'])
            # Обновляем имя кредитора на актуального взыскателя
            creditor['matched_claimant'] = claimant

    # Не сматченные ИП — это кредиторы из ИП которых нет в НБКИ
    unmatched_procs = [
        p for p in credit_procs
        if p['number'] not in used_ip_numbers
    ]

    # Добавляем таких взыскателей в список кредиторов (Раздел I)
    extra_creditors = []
    for proc in unmatched_procs:
        claimant = proc.get('claimant') or ''
        extra_creditors.append({
            'name': claimant,
            'creditor_name': claimant,
            'creditor_inn': '',
            'address': '',
            'current_debt': proc.get('amount_principal') or proc.get('amount_total') or 0,
            'uid': '',
            'contract_number': '',
            'contract_date': '',
            'source': 'ип',
            'proceedings': [{
                'ip_number': proc['number'],
                'ip_date': proc['date_start'],
                'claimant': claimant,
                'amount_principal': proc.get('amount_principal'),
                'amount_fee': proc.get('amount_fee'),
                'basis_doc': proc.get('basis_doc'),
                'match_score': 1.0,
            }],
        })

    all_creditors = creditors + extra_creditors

    # unmatched для ручной проверки = прочие типы которые мы не обработали
    unmatched = [
        p for p in proceedings
        if p['number'] not in used_ip_numbers
        and p['type'] in ('кредит', 'прочее')
        and not p.get('claimant')
    ]

    return all_creditors, unmatched


def _ip_office_lines(p: dict) -> list[str]:
    """Возвращает строки с отделением ФССП и адресом (если есть)."""
    lines = []
    office = (p.get('fssп_office') or '').replace('\xa0', ' ')
    address = p.get('fssп_address') or ''
    if office:
        lines.append(office)
    if address:
        lines.append(f"Адрес: {address}")
    return lines


def build_section2(proceedings: list[dict]) -> list[dict]:
    """
    Раздел II: исполнительские сборы + налоги + штрафы.
    Формат описания — многострочный, как у Елены.
    """
    section2 = []

    for p in proceedings:
        ip_line = f"ИП № {p['number']} от {p['date_start']}"
        office_lines = _ip_office_lines(p)

        if p['type'] == 'исполнительский_сбор':
            basis = p.get('basis_doc') or 'постановление судебного пристава'
            lines = ['Исполнительский сбор', basis] + office_lines
            section2.append({
                'type': 'исполнительский_сбор',
                'description': '\n'.join(lines),
                'amount': p.get('amount_fee') or p.get('amount_total'),
                'ip_number': p['number'],
            })

        elif p['type'] == 'налог':
            if p.get('amount_principal'):
                basis = p.get('basis_doc') or ''
                lines = ['Налог', basis] + office_lines
                section2.append({
                    'type': 'налог',
                    'description': '\n'.join(lines),
                    'amount': p['amount_principal'],
                    'ip_number': p['number'],
                })
            if p.get('amount_fee'):
                lines = ['Исполнительский сбор', ip_line] + office_lines
                section2.append({
                    'type': 'исполнительский_сбор',
                    'description': '\n'.join(lines),
                    'amount': p['amount_fee'],
                    'ip_number': p['number'],
                })

        elif p['type'] == 'штраф':
            if p.get('amount_principal'):
                # reason уже содержит "Штраф ГИБДД" — не дублируем
                reason = p.get('reason') or 'Штраф'
                lines = [reason, ip_line] + office_lines
                section2.append({
                    'type': 'штраф',
                    'description': '\n'.join(lines),
                    'amount': p['amount_principal'],
                    'ip_number': p['number'],
                })
            if p.get('amount_fee'):
                lines = ['Исполнительский сбор', ip_line] + office_lines
                section2.append({
                    'type': 'исполнительский_сбор',
                    'description': '\n'.join(lines),
                    'amount': p['amount_fee'],
                    'ip_number': p['number'],
                })

        elif p['type'] in ('кредит', 'прочее'):
            # Исполнительский сбор из кредитного ИП идёт в Раздел II
            if p.get('amount_fee'):
                lines = ['Исполнительский сбор', ip_line] + office_lines
                section2.append({
                    'type': 'исполнительский_сбор',
                    'description': '\n'.join(lines),
                    'amount': p['amount_fee'],
                    'ip_number': p['number'],
                })

    return section2


def main():
    base = Path(__file__).parent.parent

    with open(base / 'output' / 'creditors.json', encoding='utf-8') as f:
        creditors = json.load(f)
    with open(base / 'output' / 'proceedings.json', encoding='utf-8') as f:
        proceedings = json.load(f)

    print(f"Кредиторов: {len(creditors)}, ИП: {len(proceedings)}")

    # Матчинг кредиторов с ИП
    creditors, unmatched = match_proceedings_to_creditors(creditors, proceedings)

    matched_count = sum(1 for c in creditors if c['proceedings'])
    print(f"\nКредиторов с найденными ИП: {matched_count}/{len(creditors)}")

    if unmatched:
        print(f"\nНе сматченные ИП (требуют ручной проверки):")
        for p in unmatched:
            print(f"  {p['number']} | {(p.get('claimant') or '?')[:60]}")

    # Раздел II
    section2 = build_section2(proceedings)
    print(f"\nЗаписей в Разделе II: {len(section2)}")

    result = {
        'section1': creditors,
        'section2': section2,
        'unmatched': unmatched,
    }

    with open(base / 'output' / 'matched.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nСохранено в output/matched.json")


if __name__ == '__main__':
    main()
