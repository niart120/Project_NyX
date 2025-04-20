import pathlib
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QAction, QImage, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLineEdit, QListWidget, QListWidgetItem, 
    QTableWidget, QTableWidgetItem, QSplitter,
    QLabel, QTextEdit, QPushButton, QDialog, QMessageBox,
    QSizePolicy
)
import cv2
import numpy as np
from nyxpy.framework.core.hardware.protocol import CH552SerialProtocol
from nyxpy.framework.core.hardware.resource import StaticResourceIO
from nyxpy.framework.core.macro.command import DefaultCommand
from nyxpy.framework.core.utils.cancellation import CancellationToken
from nyxpy.gui.settings_dialog import SettingsDialog
from nyxpy.framework.core.macro.executor import MacroExecutor
from nyxpy.framework.core.macro.exceptions import MacroStopException
from nyxpy.framework.core.utils.helper import parse_define_args, extract_macro_tags
from nyxpy.framework.core.hardware.capture import CaptureManager
from nyxpy.framework.core.hardware.serial_comm import SerialManager
from nyxpy.framework.core.hardware.facade import HardwareFacade
from nyxpy.framework.core.logger.log_manager import log_manager
from nyxpy.framework.core.global_settings import GlobalSettings
from nyxpy.gui.device_settings_dialog import DeviceSettingsDialog
from pathlib import Path
from datetime import datetime

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Switch Automation Macro GUI - Prototype")
        self.resize(1000, 600)

        # Global settings load
        self.global_settings = GlobalSettings()

        # Serial manager setup
        self.serial_manager = SerialManager()
        self.serial_manager.auto_register_devices()
        ser_list = self.serial_manager.list_devices()
        default_ser = self.global_settings.get("serial_device", "")
        default_baud = self.global_settings.get("serial_baud", 9600)
        # Attempt to set active serial device, ignore failures
        try:
            if default_ser and default_ser in ser_list:
                self.serial_manager.set_active(default_ser, default_baud)
            elif ser_list:
                self.serial_manager.set_active(ser_list[0], default_baud)
        except Exception:
            pass

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
        # 左側は上下方向のみストレッチ
        left_pane.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        left_pane.setMinimumWidth(280)  # 必要に応じて調整

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
        # 右側は上下左右にストレッチ
        right_splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Preview placeholder
        self.preview_label = QLabel("プレビュー映像")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background: #222; color: #fff;")
        right_splitter.addWidget(self.preview_label)

        # Preview capture setup
        self.capture_manager = CaptureManager()
        self.capture_manager.auto_register_devices()
        devices = self.capture_manager.list_devices()
        # Attempt to set active capture device, ignore failures
        try:
            default_cap = self.global_settings.get("capture_device", "")
            if default_cap and default_cap in devices:
                self.capture_manager.set_active(default_cap)
            elif devices:
                self.capture_manager.set_active(devices[0])
        except Exception:
            pass

        # QTimerでプレビュー更新
        self.preview_timer = QTimer(self)
        self.preview_timer.timeout.connect(self.update_preview)
        self.preview_timer.start(33)  # 約30fps

        # Log view
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        right_splitter.addWidget(self.log_view)
        right_splitter.setSizes([300, 300])

        # Assemble split panes
        main_layout.addWidget(left_pane)
        main_layout.addWidget(right_splitter, stretch=1)

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

    def append_log(self, message: str):
        # Append log message to view
        self.log_view.append(message)

    def open_settings(self):
        dlg = DeviceSettingsDialog(self, self.global_settings)
        # Execute settings dialog and apply changes immediately
        if dlg.exec() != QDialog.Accepted:
            return
        # Apply updated capture device
        new_cap = self.global_settings.get("capture_device")
        try:
            self.capture_manager.set_active(new_cap)
        except Exception:
            pass
        # Apply updated serial device
        new_ser = self.global_settings.get("serial_device")
        new_baud = self.global_settings.get("serial_baud", 9600)
        try:
            self.serial_manager.set_active(new_ser, new_baud)
        except Exception:
            pass
        # Apply updated FPS to preview timer
        new_fps = self.global_settings.get("capture_fps", 30)
        interval = int(1000 / new_fps) if new_fps > 0 else 1000 / 60
        self.preview_timer.start(interval)

    def start_macro(self):
        # Execution parameters dialog
        macro_name = self.table.item(self.table.currentRow(), 0).text()
        dlg = SettingsDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        # Retrieve execution parameters
        params = dlg.param_edit.text()
        exec_args = parse_define_args(params)
        resource_io = StaticResourceIO(pathlib.Path.cwd() / "static")
        protocol = CH552SerialProtocol()
        ct = CancellationToken()
        # Use existing managers rather than creating new ones
        facade = HardwareFacade(self.serial_manager, self.capture_manager)
        cmd = DefaultCommand(facade, resource_io, protocol, ct)

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
        # 16:9アスペクト比でリサイズ
        size = self.preview_label.size()
        target_w, target_h = calc_aspect_size(size, 16, 9)
        if not frame.flags['C_CONTIGUOUS']:
            frame = np.ascontiguousarray(frame)
        resized = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
        image = QImage(resized.data, target_w, target_h, target_w * 3, QImage.Format_BGR888)
        pix = QPixmap.fromImage(image)
        self.preview_label.setPixmap(pix)

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

    def set_preview_pixmap(self, pix):
        self.preview_label.setPixmap(pix)

    def closeEvent(self, event):
        if hasattr(self, 'preview_timer'):
            self.preview_timer.stop()
        super().closeEvent(event)

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

def calc_aspect_size(size, aspect_w=16, aspect_h=9):
    w, h = size.width(), size.height()
    target_w = w
    target_h = int(w * aspect_h / aspect_w)
    if target_h > h:
        target_h = h
        target_w = int(h * aspect_w / aspect_h)
    return target_w, target_h
