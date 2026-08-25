# -*- mode: python ; coding: utf-8 -*-
import os
import sys

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

datas = [("templates", "templates"), ("static", "static")]
if os.path.isfile("gdrive_oauth.json"):
    datas.append(("gdrive_oauth.json", "."))

binaries = []
hiddenimports = [
    "google.oauth2",
    "google.oauth2.credentials",
    "google.auth",
    "google.auth.transport",
    "google.auth.transport.requests",
    "googleapiclient",
    "googleapiclient.discovery",
    "googleapiclient.http",
    "google_auth_oauthlib",
    "google_auth_oauthlib.flow",
    "cryptography",
    "cryptography.hazmat",
    "cryptography.hazmat.bindings._rust",
    "rsa",
    "requests.packages",
    "urllib3",
    "urllib3.util",
    "urllib3.util.ssl_",
]

for pkg in (
    "googleapiclient",
    "google_auth_oauthlib",
    "google.auth",
    "google.oauth2",
    "httplib2",
    "certifi",
    "cryptography",
):
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hidden
    except Exception:
        try:
            hiddenimports += collect_submodules(pkg)
        except Exception:
            pass
        try:
            datas += collect_data_files(pkg)
        except Exception:
            pass

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# UPX on macOS corrupts the PYZ archive (zlib "incorrect header check")
# and can strip OpenSSL symbols Drive OAuth needs.
if sys.platform == "darwin":
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="QuickPOS",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name="QuickPOS",
    )
    app = BUNDLE(
        coll,
        name="QuickPOS.app",
        icon=None,
        bundle_identifier="com.quickpos.app",
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name="QuickPOS",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
