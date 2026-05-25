# Build `.exe` with PySide6 included

Use this file when you want a real Windows `.exe` version of MasumPDF Reader.

## Important idea

PySide6 is already listed in `requirements.txt`, but for a Windows `.exe` you also need PyInstaller to **collect the PySide6/Qt6 DLLs, plugins, translations, and shiboken6 files**.

The updated script does this automatically:

```bat
developer\install.bat
developer\build-exe.bat
```

After build, your app will be here:

```text
developer\app_exe\MasumPDFReader.exe
```

## Do not move only the exe

Because this is a Qt/PySide6 app, the safest build is **one-folder mode**. Keep the whole folder together:

```text
developer\app_exe\
  MasumPDFReader.exe
  _internal\
  resources\
```

If you move only `MasumPDFReader.exe`, it may not open because Qt DLLs/plugins are beside it in the same folder.

## PySide6 dependency

The required dependency is in `requirements.txt`:

```text
PySide6>=6.7,<6.10
shiboken6>=6.7,<6.10
```

## Build command used internally

The build script uses PyInstaller with these important options:

```bat
--collect-all PySide6
--collect-all shiboken6
--hidden-import PySide6.QtPrintSupport
--hidden-import PySide6.QtSvg
--hidden-import PySide6.QtXml
```

These options are what make PySide6 included in the generated app folder.
