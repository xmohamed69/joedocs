# -*- mode: python ; coding: utf-8 -*-
# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.

import os
from pathlib import Path

# ── Path resolution ───────────────────────────────────────────────────────────
PROJECT_ROOT = Path(os.path.abspath(os.path.join(SPECPATH, '..'))).resolve()
VENV_DIR     = PROJECT_ROOT / 'venv312'
WEBVIEW_DIR  = VENV_DIR / 'Lib' / 'site-packages' / 'webview'

def collect_project_files(src_dir_name):
    result = []
    src = PROJECT_ROOT / src_dir_name
    if not src.exists():
        return result
    for f in src.rglob('*'):
        if f.is_file() and '__pycache__' not in f.parts:
            dest = str(f.parent.relative_to(PROJECT_ROOT))
            result.append((str(f), dest))
    return result


# ── Data files ────────────────────────────────────────────────────────────────
datas = []

# Manually bundle the entire webview package so nothing is missed
for f in WEBVIEW_DIR.rglob('*'):
    if f.is_file() and '__pycache__' not in f.parts:
        dest = str(f.parent.relative_to(VENV_DIR / 'Lib' / 'site-packages'))
        datas.append((str(f), dest))

for app in ['joedocs', 'accounts', 'docs', 'website', 'client']:
    datas += collect_project_files(app)

datas += collect_project_files('templates')
datas += collect_project_files('static')
datas += collect_project_files('media')

env_file = PROJECT_ROOT / '.env'
if env_file.exists():
    datas.append((str(env_file), '.'))

datas.append((str(PROJECT_ROOT / 'manage.py'), '.'))

# ── Hidden imports ────────────────────────────────────────────────────────────
hidden = [
    # Django
    'django', 'django.contrib.admin', 'django.contrib.auth',
    'django.contrib.contenttypes', 'django.contrib.sessions',
    'django.contrib.messages', 'django.contrib.staticfiles',
    'django.template.backends.django', 'django.db.backends.postgresql',
    'django.middleware.locale',
    # Third-party
    'whitenoise', 'whitenoise.middleware', 'whitenoise.storage',
    'dotenv',
    'psycopg2',
    'PIL', 'PIL.Image',
    'docx', 'openpyxl', 'pypdf', 'requests',
    # webview + .NET bridge
    'webview',
    'webview.platforms',
    'webview.platforms.edgechromium',
    'webview.platforms.winforms',
    'webview.dom',
    'clr', 'clr_loader',
    # Project apps
    'accounts', 'docs', 'website', 'client',
]

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    [str(PROJECT_ROOT / 'launcher.py')],
    pathex=[
        str(PROJECT_ROOT),
        str(VENV_DIR / 'Lib' / 'site-packages'),
    ],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    # Point PyInstaller at webview's own hook so it handles clr/pythonnet too
    hookspath=[str(WEBVIEW_DIR / '__pyinstaller')],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='JoeDocsClient',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(PROJECT_ROOT / 'installer' / 'joelinkai.ico')],
)
