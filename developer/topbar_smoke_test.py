import os, sys
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from utils.settings import AppSettings
import fitz
pdf=ROOT/'developer'/'topbar_test_sample.pdf'
doc=fitz.open(); page=doc.new_page(); page.insert_text((72,72),'Top bar smoke test'); doc.save(str(pdf)); doc.close()
app=QApplication.instance() or QApplication(sys.argv)
win=MainWindow(AppSettings())
win.open_pdf(str(pdf))
app.processEvents()
assert not win.compact_toolbar.isHidden(), 'compact toolbar should be shown after opening PDF'
assert win.toolbar.isHidden(), 'full toolbar should auto-hide after opening PDF'
assert win.tab_widget.tabText(win.tab_widget.currentIndex()).endswith('.pdf'), 'PDF tab should be visible'
win._toggle_top_tools_bar(); app.processEvents()
assert not win.toolbar.isHidden(), 'full toolbar restore failed'
assert win.compact_toolbar.isHidden(), 'compact toolbar should hide when full toolbar restored'
print('topbar_smoke_test PASS')
