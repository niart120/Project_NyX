from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QAction, QImage, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLineEdit, QListWidget, QListWidgetItem, 
    QTableWidget, QTableWidgetItem, QSplitter,
    QLabel, QTextEdit, QPushButton, QDialog, QMessageBox
)
from nyxpy.gui.settings_dialog import SettingsDialog
from nyxpy.framework.core.macro.executor import MacroExecutor
from nyxpy.cli.run_cli import create_hardware_components, create_protocol, create_command
from nyxpy.framework.core.macro.exceptions import MacroStopException
from nyxpy.framework.core.utils.helper import parse_define_args, extract_macro_tags
from nyxpy.framework.core.hardware.capture import CaptureManager
from nyxpy.framework.core.logger.log_manager import log_manager
from pathlib import Path
from datetime import datetime

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Switch Automation Macro GUI - Prototype")
        self.resize(1000, 600)

        # File menu → Settings
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.open_settings)
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(settings_action)

        # Central layout: Left (macros) / Right (log & preview)
        central = QWidget()
        main_layout = QHBoxLayout(central)
        self.setCentralWidget(central)

        # Left pane
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(5,5,5,5)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("検索…（マクロ名／タグ）")
        self.search_box.textChanged.connect(self.filter_macros)
        left_layout.addWidget(self.search_box)

        # Tags filter (populated after macros loaded)
        self.tag_list = QListWidget()
        self.tag_list.itemChanged.connect(self.filter_macros)
        left_layout.addWidget(self.tag_list)

        # Macro table
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["マクロ名", "説明文", "タグ"])
        left_layout.addWidget(self.table)

        # Load macros from framework
        self.executor = MacroExecutor()
        self.macros = self.executor.macros
        self.reload_macros()
        # Populate tag list based on loaded macros
        self.tag_list.clear()
        for tag in extract_macro_tags(self.macros):
            item = QListWidgetItem(tag)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.tag_list.addItem(item)

        # Preview capture setup
        self.capture_manager = CaptureManager()
        self.capture_manager.auto_register_devices()
        devices = self.capture_manager.list_devices()
        if devices:
            self.capture_manager.set_active(devices[0])
        # Preview refresh timer
        self.preview_timer = QTimer(self)
        self.preview_timer.setInterval(1000 // 30)  # 30fps
        self.preview_timer.timeout.connect(self.update_preview)
        self.preview_timer.start()

        # Execution controls
        ctrl_bar = QWidget()
        ctrl_layout = QHBoxLayout(ctrl_bar)
        self.run_btn = QPushButton("実行")
        self.cancel_btn = QPushButton("キャンセル")
        self.settings_btn2 = QPushButton("設定")
        self.cancel_btn.setEnabled(False)
        ctrl_layout.addWidget(self.run_btn)
        ctrl_layout.addWidget(self.cancel_btn)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(self.settings_btn2)
        left_layout.addWidget(ctrl_bar)

        # Disable run until a macro is selected
        self.run_btn.setEnabled(False)
        # Enable run button on table row selection
        self.table.selectionModel().selectionChanged.connect(self.on_table_selection_changed)
        self.run_btn.clicked.connect(self.start_macro)
        self.cancel_btn.clicked.connect(self.cancel_macro)
        # Snapshot button
        self.snapshot_btn = QPushButton("スナップショット")
        ctrl_layout.insertWidget(2, self.snapshot_btn)
        self.snapshot_btn.clicked.connect(self.take_snapshot)
        self.settings_btn2.clicked.connect(self.open_settings)

        # Right pane: splitter for preview / logs
        right_splitter = QSplitter(Qt.Vertical)
        # Preview placeholder
        self.preview_label = QLabel("プレビュー映像")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background: #222; color: #fff;")
        right_splitter.addWidget(self.preview_label)

        # Log view
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        right_splitter.addWidget(self.log_view)
        right_splitter.setSizes([300, 300])

        # Assemble split panes
        main_layout.addWidget(left_pane, 3)
        main_layout.addWidget(right_splitter, 5)

        # Integrate real-time logs from log_manager
        log_manager.add_handler(lambda record: self.log_view.append(str(record)), level="DEBUG")

        # Status bar
        self.status_label = QLabel("準備完了")
        self.statusBar().addWidget(self.status_label)

    def reload_macros(self):
        self.table.setRowCount(0)
        for name, macro in self.macros.items():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(macro.description))
            self.table.setItem(row, 2, QTableWidgetItem(", ".join(macro.tags)))

    def filter_macros(self):
        keyword = self.search_box.text().lower()
        checked = [self.tag_list.item(i).text() 
                   for i in range(self.tag_list.count()) 
                   if self.tag_list.item(i).checkState() == Qt.Checked]

        for row in range(self.table.rowCount()):
            name = self.table.item(row, 0).text().lower()
            tags = self.table.item(row, 2).text().split(", ")
            # 部分一致 AND 条件
            match_keyword = (keyword in name) or any(keyword in t.lower() for t in tags)
            match_tags = all(tag in tags for tag in checked)
            visible = match_keyword and match_tags
            self.table.setRowHidden(row, not visible)

    def append_log(self):
        self.log_counter += 1
        self.log_view.append(f"[{self.log_counter:03d}] ログメッセージ例: Macro処理中…")

    def open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec()

    def start_macro(self):
        # Open settings dialog for selected macro (for persistence)
        macro_name = self.table.item(self.table.currentRow(), 0).text()
        dlg = SettingsDialog(self, macro_name)
        if dlg.exec() != QDialog.Accepted:
            return
        # Retrieve settings
        serial = dlg.ser_device.currentText()
        capture = dlg.cap_device.currentText()
        fps = dlg.cap_fps.value()
        params = dlg.param_edit.text()
        # Update preview settings
        self.preview_timer.setInterval(1000 // fps)
        try:
            self.capture_manager.set_active(capture)
        except Exception:
            pass
        exec_args = parse_define_args(params)
        protocol = create_protocol("CH552")
        facade = create_hardware_components(serial, capture)
        cmd = create_command(facade, protocol, None)

        # Start background execution
        self.worker = WorkerThread(self.executor, cmd, macro_name, exec_args)
        self.worker.progress.connect(self.append_log)
        self.worker.finished.connect(self.on_finished)

        self.run_btn.setEnabled(False)
        self.settings_btn2.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.status_label.setText("実行中")
        self.worker.start()

    def cancel_macro(self):
        if hasattr(self, 'worker'):
            self.worker.cmd.stop()
            self.cancel_btn.setEnabled(False)

    def on_finished(self, status: str):
        self.status_label.setText(status)
        self.run_btn.setEnabled(True)
        self.settings_btn2.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        # Modal on exception
        if status.startswith("エラー"):
            dlg = QMessageBox(self)
            dlg.setWindowTitle("エラー")
            dlg.setText(f"マクロ実行中にエラーが発生しました:\n{status}")
            dlg.setStandardButtons(QMessageBox.Retry | QMessageBox.Close)
            ret = dlg.exec()
            if ret == QMessageBox.Retry:
                self.start_macro()
            elif ret == QMessageBox.Close:
                from PySide6.QtWidgets import QApplication
                QApplication.instance().quit()

    def update_preview(self):
        try:
            frame = self.capture_manager.get_active_device().get_frame()
        except Exception:
            return
        # Convert BGR numpy array to QImage
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        image = QImage(frame.data, w, h, bytes_per_line, QImage.Format_BGR888)
        pix = QPixmap.fromImage(image)
        self.preview_label.setPixmap(pix.scaled(
            self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def take_snapshot(self):
        # Ensure snapshots directory
        snaps_dir = Path.cwd() / "snapshots"
        snaps_dir.mkdir(exist_ok=True)
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = snaps_dir / f"{timestamp}.png"
        # Save pixmap
        pix = self.preview_label.pixmap()
        if pix:
            pix.save(str(filepath), 'PNG')
            self.status_label.setText(f"スナップショット保存: {filepath.name}")
        else:
            self.status_label.setText("プレビューがありません。スナップショットに失敗しました。")

    def on_table_selection_changed(self):
        self.run_btn.setEnabled(self.table.selectionModel().hasSelection())

class WorkerThread(QThread):
    progress = Signal(str)
    finished = Signal(str)

    def __init__(self, executor, cmd, macro_name, args):
        super().__init__()
        self.executor = executor
        self.cmd = cmd
        # Override cmd.log to emit progress updates
        orig_log = getattr(self.cmd, 'log', None)
        def _log_override(*values, sep=' ', end='\n', level='INFO'):
            msg = sep.join(map(str, values)) + end.rstrip('\n')
            self.progress.emit(msg)
            if orig_log:
                orig_log(*values, sep=sep, end=end, level=level)
        self.cmd.log = _log_override
        self.macro_name = macro_name
        self.args = args

    def run(self):
        try:
            self.executor.select_macro(self.macro_name)
            self.executor.execute(self.cmd, self.args)
            self.finished.emit("完了")
        except MacroStopException:
            self.finished.emit("中断")
        except Exception as e:
            self.finished.emit(f"エラー: {e}")
