# Build in the BE checkout: python -m PyInstaller --clean --noconfirm BE.spec
from pathlib import Path
root = str(Path(SPECPATH))
a = Analysis(['app.py'], pathex=[root], binaries=[], datas=[],
             hiddenimports=['local_web', 'backup', 'runtime', 'web_api', 'web_demo', 'waitress', 'marshmallow.validate'],
             hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='BE', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=True)
