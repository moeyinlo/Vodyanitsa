from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QStyleFactory,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .hotkeys import GlobalHotkeys
from .mapping import PROFILES, map_voices, suggest_voice_transposition
from .midi import MidiDocument, MidiTrack, load_midi
from .playback import PlaybackEngine, PlaybackState
from .windows_input import WindowsKeySink


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setStyle(QStyleFactory.create("Fusion"))
        self._apply_dark_palette()
        self.setWindowTitle("原神乐器 MIDI 播放器")
        self.setMinimumSize(700, 540)
        self.resize(780, 610)
        self.document: MidiDocument | None = None
        self.engine = PlaybackEngine(WindowsKeySink())
        self._build_ui()

        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setInterval(5)
        self.timer.timeout.connect(self._tick)

        self.hotkeys = GlobalHotkeys(
            {"F7": self._play, "F8": self._pause, "F9": self._reset}
        )
        app = self.app = self._application()
        app.installNativeEventFilter(self.hotkeys)
        if self.hotkeys.error:
            self.status_label.setText(self.hotkeys.error + " 请使用窗口内的控制按钮。")

    def _application(self):
        from PyQt6.QtWidgets import QApplication

        return QApplication.instance()

    def _apply_dark_palette(self) -> None:
        palette = QPalette()
        colors = {
            QPalette.ColorRole.Window: "#171d1f",
            QPalette.ColorRole.WindowText: "#e5ece9",
            QPalette.ColorRole.Base: "#1d2629",
            QPalette.ColorRole.AlternateBase: "#222d30",
            QPalette.ColorRole.ToolTipBase: "#283437",
            QPalette.ColorRole.ToolTipText: "#edf3f1",
            QPalette.ColorRole.Text: "#e5ece9",
            QPalette.ColorRole.Button: "#283437",
            QPalette.ColorRole.ButtonText: "#e5ece9",
            QPalette.ColorRole.BrightText: "#ff8c82",
            QPalette.ColorRole.Highlight: "#237e74",
            QPalette.ColorRole.HighlightedText: "#ffffff",
            QPalette.ColorRole.PlaceholderText: "#849590",
            QPalette.ColorRole.Link: "#63c8b8",
            QPalette.ColorRole.LinkVisited: "#82bfb5",
        }
        for role, color in colors.items():
            palette.setColor(role, QColor(color))
        palette.setColor(
            QPalette.ColorGroup.Disabled,
            QPalette.ColorRole.WindowText,
            QColor("#788681"),
        )
        palette.setColor(
            QPalette.ColorGroup.Disabled,
            QPalette.ColorRole.Text,
            QColor("#788681"),
        )
        palette.setColor(
            QPalette.ColorGroup.Disabled,
            QPalette.ColorRole.ButtonText,
            QColor("#788681"),
        )
        self.setPalette(palette)

    def _build_ui(self) -> None:
        self.setStyleSheet(
            "QMainWindow, QWidget { background: #171d1f; color: #e5ece9; "
            "font-family: 'Segoe UI'; font-size: 10pt; }"
            "QLabel { background: transparent; color: #e5ece9; }"
            "QPushButton { min-height: 34px; padding: 0 14px; border: 1px solid #3a484b; "
            "border-radius: 4px; background: #283437; color: #e5ece9; }"
            "QPushButton:hover { background: #334245; border-color: #526462; }"
            "QPushButton:pressed { background: #202a2d; }"
            "QPushButton:disabled { color: #788681; background: #20282b; border-color: #303b3e; }"
            "QPushButton#primary { color: #f4fffc; background: #187f73; border-color: #26988b; "
            "font-weight: 600; }"
            "QPushButton#primary:hover { background: #209487; }"
            "QComboBox, QSpinBox { min-height: 32px; padding: 0 9px; border: 1px solid #3a484b; "
            "border-radius: 4px; background: #202a2d; color: #e5ece9; selection-background-color: #237e74; }"
            "QComboBox:hover, QSpinBox:hover { border-color: #647875; }"
            "QComboBox:focus, QSpinBox:focus { border: 1px solid #43b5a5; }"
            "QComboBox#trackApproximationMode { min-height: 20px; padding: 0 6px; }"
            "QComboBox::drop-down { width: 28px; border: 0; border-left: 1px solid #3a484b; }"
            "QComboBox QAbstractItemView { background: #202a2d; color: #e5ece9; "
            "selection-background-color: #237e74; selection-color: #ffffff; border: 1px solid #3a484b; }"
            "QSpinBox::up-button, QSpinBox::down-button { width: 20px; background: #283437; "
            "border: 0; border-left: 1px solid #3a484b; }"
            "QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: #354447; }"
            "QTableWidget { background: #1d2629; alternate-background-color: #222d30; "
            "color: #e5ece9; gridline-color: #303d40; border: 1px solid #3a484b; "
            "border-radius: 4px; selection-background-color: #285d57; selection-color: #ffffff; }"
            "QTableWidget::item { padding: 4px 6px; color: #e5ece9; }"
            "QTableWidget::item:selected { background: #285d57; color: #ffffff; }"
            "QHeaderView::section { background: #252f32; color: #b8c5c1; padding: 6px 8px; "
            "border: 0; border-right: 1px solid #354245; border-bottom: 1px solid #354245; }"
            "QPlainTextEdit { border: 1px solid #3a484b; border-radius: 4px; background: #1d2629; "
            "color: #e5ece9; selection-background-color: #285d57; font-family: Consolas; font-size: 9pt; }"
            "QProgressBar { min-height: 12px; border: 0; border-radius: 3px; background: #2a3538; }"
            "QProgressBar::chunk { border-radius: 3px; background: #26988b; }"
            "QScrollBar:vertical { width: 10px; background: #1d2629; margin: 0; }"
            "QScrollBar::handle:vertical { min-height: 24px; border-radius: 4px; background: #465653; }"
            "QScrollBar::handle:vertical:hover { background: #5c706b; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
            "QToolTip { color: #edf3f1; background: #283437; border: 1px solid #526462; padding: 4px 6px; }"
            "QWidget#fileLabel { padding: 7px 9px; background: #1d2629; "
            "border: 1px solid #3a484b; border-radius: 4px; color: #e5ece9; }"
        )

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)
        self.setCentralWidget(root)

        title = QLabel("原神乐器 MIDI 播放器")
        title.setStyleSheet("font-size: 20pt; font-weight: 650;")
        subtitle = QLabel("MIDI 音符映射与键盘演奏")
        subtitle.setStyleSheet("color: #a7b5b0;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        file_row = QHBoxLayout()
        self.file_label = QLabel("尚未选择 MIDI")
        self.file_label.setObjectName("fileLabel")
        self.file_label.setMinimumWidth(0)
        self.open_button = QPushButton("选择 MIDI")
        self.open_button.clicked.connect(self._choose_file)
        file_row.addWidget(self.file_label, 1)
        file_row.addWidget(self.open_button)
        layout.addLayout(file_row)

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(8)
        self.profile_combo = QComboBox()
        for profile in PROFILES:
            self.profile_combo.addItem(profile.name, profile.id)
        self.profile_combo.currentIndexChanged.connect(self._refresh_mapping)
        self.track_table = QTableWidget(0, 3)
        self.track_table.setHorizontalHeaderLabels(
            ["合并", "声部", "近似方式"]
        )
        self.track_table.verticalHeader().setVisible(False)
        self.track_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.track_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.track_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.track_table.setMaximumHeight(150)
        self.track_table.itemChanged.connect(self._refresh_mapping)
        self.transpose_spin = QSpinBox()
        self.transpose_spin.setRange(-24, 24)
        self.transpose_spin.setSuffix(" 半音")
        self.transpose_spin.valueChanged.connect(self._refresh_mapping)
        self.auto_transpose_button = QPushButton("自动转调")
        self.auto_transpose_button.setToolTip(
            "在 ±24 半音内优先选择映射音符最多、近似警告较少且转调幅度较小的结果。"
        )
        self.auto_transpose_button.clicked.connect(self._auto_transpose)
        transpose_row = QHBoxLayout()
        transpose_row.addWidget(self.transpose_spin, 1)
        transpose_row.addWidget(self.auto_transpose_button)
        form.addRow("乐器布局", self.profile_combo)
        form.addRow("转调", transpose_row)
        self.track_table.setToolTip(
            "勾选多个声部可合并演奏；每行可单独选择缺失音的近似方式。"
        )
        form.addRow("声部（可多选）", self.track_table)
        layout.addLayout(form)

        self.summary_label = QLabel("选择 MIDI 文件以查看音轨和映射结果。")
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet("color: #bdc9c5; padding: 2px 0;")
        layout.addWidget(self.summary_label)

        preview_title = QLabel("映射预览")
        preview_title.setStyleSheet("font-weight: 600; margin-top: 2px;")
        layout.addWidget(preview_title)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("映射音符与诊断信息将显示在这里。")
        self.preview.setMaximumBlockCount(100)
        layout.addWidget(self.preview, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

        bottom = QHBoxLayout()
        self.play_button = QPushButton("播放  F7")
        self.play_button.setObjectName("primary")
        self.pause_button = QPushButton("暂停  F8")
        self.reset_button = QPushButton("重置  F9")
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setMinimumWidth(112)
        self.play_button.clicked.connect(self._play)
        self.pause_button.clicked.connect(self._pause)
        self.reset_button.clicked.connect(self._reset)
        bottom.addWidget(self.play_button)
        bottom.addWidget(self.pause_button)
        bottom.addWidget(self.reset_button)
        bottom.addStretch(1)
        bottom.addWidget(self.time_label)
        layout.addLayout(bottom)

        self.status_label = QLabel("F7 播放/继续   F8 暂停   F9 重置")
        self.status_label.setStyleSheet("color: #a7b5b0;")
        layout.addWidget(self.status_label)
        self._set_controls_enabled(False)

    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 MIDI", str(Path.home()), "MIDI 文件 (*.mid *.midi)"
        )
        if path:
            self._load_file(path)

    def _load_file(self, path: str) -> None:
        try:
            document = load_midi(path)
        except (OSError, ValueError, EOFError) as exc:
            QMessageBox.warning(self, "无法打开 MIDI", str(exc))
            return
        self.timer.stop()
        try:
            self.engine.reset()
        except OSError as exc:
            self._input_error(exc)
            return
        self.document = document
        self.file_label.setText(Path(path).name)
        self.file_label.setToolTip(path)
        playable_tracks = [track for track in document.tracks if track.notes]
        self.track_table.blockSignals(True)
        self.track_table.setRowCount(len(playable_tracks))
        for row, track in enumerate(playable_tracks):
            pitch_range = track.pitch_range
            pitch_text = f"{pitch_range[0]}-{pitch_range[1]}" if pitch_range else "无音符"
            include_item = QTableWidgetItem()
            include_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
            )
            include_item.setCheckState(Qt.CheckState.Checked)
            self.track_table.setItem(row, 0, include_item)

            voice_item = QTableWidgetItem(
                f"{track.index}: {track.name} | {len(track.notes)} 音符 | MIDI {pitch_text}"
            )
            voice_item.setData(Qt.ItemDataRole.UserRole, track.index)
            voice_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.track_table.setItem(row, 1, voice_item)

            mode_combo = QComboBox()
            mode_combo.setObjectName("trackApproximationMode")
            mode_combo.addItem("\u5173\u95ed", "none")
            mode_combo.addItem("\u5355\u97f3\u8fd1\u4f3c", "single")
            mode_combo.addItem("\u548c\u5f26\u8fd1\u4f3c", "chord")
            mode_combo.setToolTip(
                "\u5355\u97f3\u6a21\u5f0f\u9010\u97f3\u8fd1\u4f3c\uff1b"
                "\u548c\u5f26\u6a21\u5f0f\u4f18\u5148\u8fd1\u4f3c\u4e3a\u548c\u5f26\uff0c"
                "\u5b64\u7acb\u534a\u97f3\u4e5f\u4f1a\u6269\u5c55\u4e3a\u548c\u5f26"
            )
            mode_combo.currentIndexChanged.connect(self._refresh_mapping)
            self.track_table.setCellWidget(row, 2, mode_combo)

        self.track_table.blockSignals(False)
        self._set_controls_enabled(bool(playable_tracks))
        if not playable_tracks:
            self.summary_label.setText("文件中没有包含音符的轨道。")
            self.preview.clear()
            self.progress.setValue(0)
            self._sync_playback_display()
            return
        self._refresh_mapping()

    def _auto_transpose(self) -> None:
        if not self.document:
            return
        voices = self._selected_voices()
        if not voices:
            self.status_label.setText("请至少勾选一个演奏声部。")
            return
        offset = suggest_voice_transposition(
            [
                (f"{track.index}: {track.name}", track.notes, mode)
                for track, mode in voices
            ],
            self.profile_combo.currentData(),
        )
        self.transpose_spin.setValue(offset)
        self.status_label.setText(f"自动转调已选择 {offset:+d} 半音；可在预览中检查结果。")

    def _selected_voices(self) -> list[tuple[MidiTrack, str]]:
        if not self.document:
            return []
        voices = []
        for row in range(self.track_table.rowCount()):
            include_item = self.track_table.item(row, 0)
            if not include_item or include_item.checkState() != Qt.CheckState.Checked:
                continue
            voice_item = self.track_table.item(row, 1)
            mode_combo = self.track_table.cellWidget(row, 2)
            track_index = voice_item.data(Qt.ItemDataRole.UserRole)
            voices.append((self.document.tracks[track_index], mode_combo.currentData()))
        return voices

    def _refresh_mapping(self, *_args) -> None:
        if not self.document:
            return
        voices = self._selected_voices()
        if self.engine.state is PlaybackState.PLAYING:
            self.timer.stop()
            try:
                self.engine.reset()
            except OSError as exc:
                self._input_error(exc)
                return
        self._set_controls_enabled(True)
        if not voices:
            try:
                self.engine.load([], self.document.duration)
            except OSError as exc:
                self._input_error(exc)
                return
            self.summary_label.setText("请至少勾选一个演奏声部。")
            self.preview.clear()
            self.progress.setValue(0)
            self._set_controls_enabled(True)
            self._sync_playback_display()
            return

        profile_id = self.profile_combo.currentData()
        result = map_voices(
            [
                (f"{track.index}: {track.name}", track.notes, mode)
                for track, mode in voices
            ],
            profile_id,
            self.transpose_spin.value(),
        )
        self.engine.load(result.spans, self.document.duration)
        notes = [note for track, _ in voices for note in track.notes]
        pitch_text = f"MIDI {min(note.pitch for note in notes)}-{max(note.pitch for note in notes)}"
        self.summary_label.setText(
            f"{self._format_time(self.document.duration)} | {len(voices)} 个声部 | "
            f"{len(notes)} 个音符 | "
            f"{len(result.spans)} 个已映射音符 | {pitch_text} | {len(result.warnings)} 条映射警告"
        )
        lines = [
            f"{self._format_time(span.start)}  {'+'.join(span.keys):<14} "
            f"MIDI {','.join(map(str, span.source_pitches))}  {span.label or ''}".rstrip()
            for span in result.spans[:18]
        ]
        if len(result.spans) > 18:
            lines.append(f"还有 {len(result.spans) - 18} 个映射事件")
        if result.warnings:
            lines.extend(("", "诊断信息：", *result.warnings[:6]))
            if len(result.warnings) > 6:
                lines.append(f"还有 {len(result.warnings) - 6} 条映射警告")
        if self.document.warnings:
            lines.extend(("", *self.document.warnings[:4]))
        self.preview.setPlainText("\n".join(lines) if lines else "当前音轨没有可映射的音符。")
        self.progress.setValue(0)
        self._sync_playback_display()

    def _play(self) -> None:
        if not self.document:
            return
        try:
            self.engine.play()
            if self.engine.state is PlaybackState.PLAYING:
                self.timer.start()
                self.status_label.setText("播放中。请确保游戏内已打开乐器界面。")
        except (OSError, RuntimeError) as exc:
            self._input_error(exc)

    def _pause(self) -> None:
        if self.engine.state is not PlaybackState.PLAYING:
            return
        try:
            self.engine.pause()
        except OSError as exc:
            self._input_error(exc)
            return
        self.timer.stop()
        self.status_label.setText("已暂停，所有按住的按键已释放。")
        self._sync_playback_display()

    def _reset(self) -> None:
        try:
            self.engine.reset()
        except OSError as exc:
            self._input_error(exc)
            return
        self.timer.stop()
        self.status_label.setText("已重置到开头。")
        self.progress.setValue(0)
        self._sync_playback_display()

    def _tick(self) -> None:
        try:
            self.engine.tick()
        except OSError as exc:
            self._input_error(exc)
            return
        self._sync_playback_display()
        if self.engine.state is PlaybackState.FINISHED:
            self.timer.stop()
            self.status_label.setText("播放结束，所有按键已释放。")

    def _input_error(self, error: Exception) -> None:
        self.timer.stop()
        try:
            self.engine.reset()
        except OSError:
            pass
        self.status_label.setText(f"键盘输入失败：{error}")
        QMessageBox.warning(self, "键盘输入失败", str(error))

    def _sync_playback_display(self) -> None:
        duration = self.document.duration if self.document else 0.0
        position = self.engine.position
        self.time_label.setText(f"{self._format_time(position)} / {self._format_time(duration)}")
        self.progress.setValue(int(1000 * position / duration) if duration else 0)

    @staticmethod
    def _format_time(seconds: float) -> str:
        seconds = max(0, int(seconds))
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    def _set_controls_enabled(self, enabled: bool) -> None:
        self.track_table.setEnabled(enabled)
        has_selected_voice = enabled and bool(self._selected_voices())
        self.play_button.setEnabled(has_selected_voice)
        self.pause_button.setEnabled(has_selected_voice)
        self.reset_button.setEnabled(has_selected_voice)

    def closeEvent(self, event) -> None:
        self.timer.stop()
        try:
            self.engine.reset()
        except OSError:
            pass
        finally:
            self.app.removeNativeEventFilter(self.hotkeys)
            self.hotkeys.unregister()
        super().closeEvent(event)
