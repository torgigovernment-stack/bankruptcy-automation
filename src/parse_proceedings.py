"""
Парсинг исполнительных производств из выгрузки Госуслуг (DOCX).
"""
import re
import json
from pathlib import Path
from docx import Document


def parse_amount_str(text: str) -> float | None:
    clean = re.sub(r'[₽РP\xa0\s]', '', text).replace(',', '.')
    try:
        return float(clean)
    except ValueError:
        return None


def parse_proceedings(doc_path: str) -> list[dict]:
    doc = Document(doc_path)
    paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

    # Разбиваем на блоки по заголовку каждого ИП
    block_starts = [
        i for i, p in enumerate(paras)
        if re.match(r'Оплата задолженности по ИП', p)
    ]

    proceedings = []

    for b_idx, start in enumerate(block_starts):
        end = block_starts[b_idx + 1] if b_idx + 1 < len(block_starts) else len(paras)
        block = paras[start:end]

        ip = {
            'number': None,
            'date_start': None,
            'claimant': None,
            'reason': None,
            'basis_doc': None,
            'fssп_office': None,
            'fssп_address': None,
            'amount_total': None,
            'amount_principal': None,
            'amount_fee': None,
            'type': None,
        }

        # Номер ИП из заголовка
        header_match = re.search(r'ИП [№#]?\s*([\d/]+-ИП)\s*от\s*([\d.]+)', block[0])
        if header_match:
            ip['number'] = header_match.group(1)
            ip['date_start'] = header_match.group(2)

        for i, line in enumerate(block):
            # Текущая задолженность (итоговая сумма)
            if line == 'Текущая задолженность' and i + 1 < len(block):
                ip['amount_total'] = parse_amount_str(block[i + 1])

            # Точные суммы из "Расчёты по задолженности":
            # "СуммаX ₽" followed by "Назначение платежаТип"
            sum_match = re.match(r'Сумма([\d\s,₽\xa0]+)', line)
            if sum_match and i + 1 < len(block):
                amount = parse_amount_str(sum_match.group(1))
                next_line = block[i + 1]
                pay_type_match = re.match(r'Назначение платежа(.+)', next_line)
                if pay_type_match and amount:
                    pay_type = pay_type_match.group(1).strip().lower()
                    if 'основной долг' in pay_type:
                        ip['amount_principal'] = amount
                    elif 'исполнительский сбор' in pay_type:
                        ip['amount_fee'] = amount

            # Основной долг (склеен в итоговой строке)
            if ip['amount_principal'] is None:
                bd_match = re.match(r'Основной долг([\d\s,₽\xa0Р]+)', line)
                if bd_match:
                    ip['amount_principal'] = parse_amount_str(bd_match.group(1))

            # Исполнительский сбор (склеен в итоговой строке)
            if ip['amount_fee'] is None:
                fee_match = re.match(r'Исполнительский сбор([\d\s,₽\xa0]+)', line)
                if fee_match:
                    ip['amount_fee'] = parse_amount_str(fee_match.group(1))

            # Причина (склеена: "ПричинаТекст")
            reason_match = re.match(r'Причина(.+)', line)
            if reason_match:
                ip['reason'] = reason_match.group(1).strip()

            # Основание (исполнительный документ)
            basis_match = re.match(r'Основание \(исполнительный документ\)(.+)', line)
            if basis_match:
                ip['basis_doc'] = basis_match.group(1).strip()

            # Взыскатель (либо следующая строка, либо склеен)
            claimant_match = re.match(r'Взыскатель(.+)', line)
            if claimant_match:
                ip['claimant'] = claimant_match.group(1).strip()
            elif line == 'Взыскатель' and i + 1 < len(block):
                ip['claimant'] = block[i + 1].strip()

            # Отделение ФССП
            fssп_match = re.match(r'Отделение ФССП(.+)', line)
            if fssп_match:
                ip['fssп_office'] = fssп_match.group(1).strip()

            # Адрес ФССП
            addr_match = re.match(r'Адрес(\d.+)', line)
            if addr_match:
                ip['fssп_address'] = addr_match.group(1).strip()

        # Классификация
        reason = (ip.get('reason') or '').lower()
        claimant = (ip.get('claimant') or '').upper()

        if 'исполнительский сбор' in reason:
            ip['type'] = 'исполнительский_сбор'
        elif 'взыскание налогов' in reason or 'ИНСПЕКЦИЯ' in claimant or 'ИФНС' in claimant or 'ФНС' in claimant:
            ip['type'] = 'налог'
        elif 'штраф гибдд' in reason or 'штраф' in reason:
            ip['type'] = 'штраф'
        elif 'кредитным платежам' in reason or 'займ' in reason or 'кредит' in reason:
            ip['type'] = 'кредит'
        else:
            ip['type'] = 'прочее'

        if ip['number']:
            proceedings.append(ip)

    return proceedings


def main():
    input_path = Path(__file__).parent.parent / 'input' / 'enforcement_proceedings.docx'
    output_path = Path(__file__).parent.parent / 'output' / 'proceedings.json'
    output_path.parent.mkdir(exist_ok=True)

    print(f"Читаем ИП: {input_path}")
    proceedings = parse_proceedings(str(input_path))

    by_type = {}
    for p in proceedings:
        by_type.setdefault(p['type'], []).append(p)

    print(f"\nВсего ИП: {len(proceedings)}")
    for t, items in by_type.items():
        print(f"  {t}: {len(items)}")

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(proceedings, f, ensure_ascii=False, indent=2)
    print(f"\nСохранено в {output_path}")

    print("\n--- Примеры по типам ---")
    for t, items in by_type.items():
        p = items[0]
        print(f"\n[{t}] ИП {p['number']}")
        print(f"  Взыскатель: {(p.get('claimant') or '—')[:70]}")
        print(f"  Причина: {(p.get('reason') or '—')[:70]}")
        print(f"  Основной долг: {p.get('amount_principal')} | Сбор: {p.get('amount_fee')} | Итого: {p.get('amount_total')}")


if __name__ == '__main__':
    main()
