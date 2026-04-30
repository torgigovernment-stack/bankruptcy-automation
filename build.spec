# PyInstaller spec — собирает один .exe со всем нужным
# Сборка (на Windows-машине):
#   pip install pyinstaller
#   pyinstaller build.spec
# Готовый файл появится в dist/Список_кредиторов.exe
#
# ПЕРЕД СБОРКОЙ: положить pdftotext.exe + libpoppler*.dll в папку bin/
# (взять из https://github.com/oschwartz10612/poppler-windows/releases)

block_cipher = None

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('input/creditors_template.docx', 'input'),
        ('bin', 'bin'),  # папка с pdftotext.exe и .dll
        ('src', 'src'),
    ],
    hiddenimports=['flask', 'docx', 'lxml.etree'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Список_кредиторов',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # окно с логами (закрытие = выход)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
