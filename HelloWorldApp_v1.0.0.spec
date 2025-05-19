# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['c:\\GIT\\pyontrust\\gui_app\\hello_world/hello_world.py'],
    pathex=[],
    binaries=[],
    datas=[('c:\\GIT\\pyontrust\\gui_app\\hello_world/web', 'web'), ('c:\\GIT\\pyontrust/pyontrust_packages', 'pyontrust_packages')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='HelloWorldApp_v1.0.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
