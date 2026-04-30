"""
Локальный веб-интерфейс: загружаем НБКИ + ИП → скачиваем готовый список кредиторов.
Запуск: python3 web.py  →  http://localhost:5001
"""
import io
import json
from pathlib import Path
from flask import Flask, request, send_file

from src.parse_credit_history import extract_text, parse_creditors
from src.parse_proceedings import parse_proceedings
from src.matcher import match_proceedings_to_creditors, build_section2
from src.build_document import build_document

app = Flask(__name__)
BASE = Path(__file__).parent
TEMPLATE = BASE / 'input' / 'creditors_template.docx'

HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Список кредиторов — банкротство</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f5f5f5; min-height: 100vh;
         display: flex; align-items: center; justify-content: center; }
  .card { background: white; border-radius: 12px; padding: 40px;
          width: 100%; max-width: 520px; box-shadow: 0 4px 24px rgba(0,0,0,.08); }
  h1 { font-size: 20px; font-weight: 600; margin-bottom: 6px; }
  .subtitle { color: #888; font-size: 14px; margin-bottom: 32px; }
  .field { margin-bottom: 20px; }
  label { display: block; font-size: 13px; font-weight: 500;
          color: #444; margin-bottom: 6px; }
  .badge { font-size: 11px; background: #f0f0f0; color: #666;
           padding: 2px 6px; border-radius: 4px; margin-left: 6px; }
  input[type=file] { width: 100%; padding: 10px 12px;
                     border: 1.5px dashed #d0d0d0; border-radius: 8px;
                     font-size: 13px; color: #444; cursor: pointer;
                     background: #fafafa; }
  input[type=file]:hover { border-color: #999; background: #f5f5f5; }
  button { width: 100%; padding: 13px; background: #1a1a1a; color: white;
           border: none; border-radius: 8px; font-size: 15px; font-weight: 500;
           cursor: pointer; margin-top: 8px; transition: background .15s; }
  button:hover { background: #333; }
  button:disabled { background: #aaa; cursor: not-allowed; }
  .status { display: none; text-align: center; margin-top: 16px;
            font-size: 13px; color: #666; }
  .error { color: #c0392b; background: #fdf0ef; border-radius: 6px;
           padding: 10px 14px; margin-top: 16px; font-size: 13px;
           display: none; }
</style>
</head>
<body>
<div class="card">
  <h1>Список кредиторов</h1>
  <p class="subtitle">Загрузите два документа — получите готовый список для заявления о банкротстве</p>

  <form id="form" action="/process" method="post" enctype="multipart/form-data">
    <div class="field">
      <label>Кредитная история НБКИ <span class="badge">PDF</span></label>
      <input type="file" name="credit_history" accept=".pdf" required>
    </div>
    <div class="field">
      <label>Исполнительные производства (Госуслуги) <span class="badge">DOCX</span></label>
      <input type="file" name="proceedings" accept=".docx" required>
    </div>
    <button type="submit" id="btn">Создать документ</button>
  </form>

  <p class="status" id="status">⏳ Обрабатываем документы…</p>
  <p class="error" id="error"></p>
</div>

<script>
document.getElementById('form').addEventListener('submit', function(e) {
  e.preventDefault();
  var btn = document.getElementById('btn');
  var status = document.getElementById('status');
  var errEl = document.getElementById('error');
  btn.disabled = true;
  btn.textContent = 'Обрабатываем…';
  status.style.display = 'block';
  errEl.style.display = 'none';

  var data = new FormData(this);
  fetch('/process', { method: 'POST', body: data })
    .then(function(r) {
      if (!r.ok) return r.text().then(function(t) { throw new Error(t); });
      return r.blob();
    })
    .then(function(blob) {
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url;
      a.download = 'creditors_list.docx';
      a.click();
      btn.disabled = false;
      btn.textContent = 'Создать документ';
      status.style.display = 'none';
    })
    .catch(function(err) {
      errEl.textContent = 'Ошибка: ' + err.message;
      errEl.style.display = 'block';
      btn.disabled = false;
      btn.textContent = 'Создать документ';
      status.style.display = 'none';
    });
});
</script>
</body>
</html>"""


@app.route('/')
def index():
    return HTML


@app.route('/process', methods=['POST'])
def process():
    pdf_file = request.files.get('credit_history')
    docx_file = request.files.get('proceedings')

    if not pdf_file or not docx_file:
        return 'Оба файла обязательны', 400

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        pdf_path = tmp / 'credit_history.pdf'
        docx_path = tmp / 'proceedings.docx'
        output_path = tmp / 'result.docx'

        pdf_file.save(str(pdf_path))
        docx_file.save(str(docx_path))

        # Пайплайн
        text = extract_text(str(pdf_path))
        creditors = parse_creditors(text)
        proceedings = parse_proceedings(str(docx_path))
        creditors, unmatched = match_proceedings_to_creditors(creditors, proceedings)
        section2 = build_section2(proceedings)
        matched = {'section1': creditors, 'section2': section2, 'unmatched': unmatched}
        build_document(matched, str(TEMPLATE), str(output_path))

        # Читаем в память до закрытия tmpdir
        with open(output_path, 'rb') as f:
            result = io.BytesIO(f.read())

    result.seek(0)
    return send_file(
        result,
        as_attachment=True,
        download_name='creditors_list.docx',
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )


if __name__ == '__main__':
    print("Открой: http://localhost:5001")
    app.run(debug=False, port=5001)
