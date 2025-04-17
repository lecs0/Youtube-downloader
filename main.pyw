import sys
import os
import yt_dlp
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTextEdit, QProgressBar, QMessageBox, QFileDialog,
    QComboBox, QGroupBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal


VIDEO_QUALITIES = {
    "Best Available": 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
    "1080p": 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]',
    "720p": 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]',
    "480p": 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best[height<=480]',
    "360p": 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]/best[height<=360]',
}

AUDIO_QUALITIES = {
    "Best Audio (MP3)": {'format': 'bestaudio/best', 'postprocessor_quality': '0'},
    "Approx 192kbps (MP3)": {'format': 'bestaudio/best', 'postprocessor_quality': '192'},
    "Approx 128kbps (MP3)": {'format': 'bestaudio/best', 'postprocessor_quality': '128'},
}

class DownloadWorker(QThread):
    progress_signal = pyqtSignal(str)
    progress_bar_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, url, output_path, selected_format_type, selected_quality_key):
        super().__init__()
        self.url = url
        self.output_path = output_path
        self.selected_format_type = selected_format_type
        self.selected_quality_key = selected_quality_key
        self.is_cancelled = False
        self._actual_filename = None

    def run(self):
        self.progress_signal.emit(f"Letöltés elkezdése: {self.url}")
        self.progress_bar_signal.emit(0)

        # --- Progress Hook ---
        def download_progress_hook(d):
            if self.is_cancelled:
                raise yt_dlp.utils.DownloadCancelled("Letöltés megszakítva.")

            if d['status'] == 'downloading':
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
                downloaded_bytes = d.get('downloaded_bytes')
                speed = d.get('_speed_str', 'N/A')
                eta = d.get('_eta_str', 'N/A')


                if 'filename' in d:
                    self._actual_filename = d['filename']
                elif 'info_dict' in d and 'filename' in d['info_dict']:
                     self._actual_filename = d['info_dict']['filename']


                if total_bytes and downloaded_bytes:
                    percent = int((downloaded_bytes / total_bytes) * 100)
                    self.progress_signal.emit(
                        f"\rLetöltés: {percent}% {speed}, ETA: {eta}"
                    )
                    self.progress_bar_signal.emit(percent)
                else:
                    percent_str = d.get('_percent_str', 'N/A').replace('%','').strip()
                    try:
                        percent = int(float(percent_str))
                        self.progress_bar_signal.emit(percent)
                    except ValueError:
                         pass
                    self.progress_signal.emit(
                        f"\rLetöltés: {percent_str}% {speed}, ETA: {eta}"
                    )

            elif d['status'] == 'finished':
                self.progress_signal.emit("\nLetöltött fálj feldolgozása...")
                self.progress_bar_signal.emit(100)
                if 'filename' in d and not self._actual_filename:
                    self._actual_filename = d['filename']
            elif d['status'] == 'error':
                 self.error_signal.emit(f"yt-dlp error: {d.get('error', 'Unknown error')}")


        ydl_opts = {
            'outtmpl': os.path.join(self.output_path, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [download_progress_hook],
            'noplaylist': True,
        }

        video_title = "Ismeretlen cím"

        try:
            if self.selected_format_type == "MP4":
                if self.selected_quality_key not in VIDEO_QUALITIES:
                     raise ValueError(f"Rossz felbontás: {self.selected_quality_key}")
                ydl_opts['format'] = VIDEO_QUALITIES[self.selected_quality_key]
                ydl_opts['merge_output_format'] = 'mp4'
                self.progress_signal.emit(f"Kiválasztott formázás: MP4 ({self.selected_quality_key})")

            elif self.selected_format_type == "MP3":
                if self.selected_quality_key not in AUDIO_QUALITIES:
                    raise ValueError(f"Rossz hangkiterjezstés: {self.selected_quality_key}")

                audio_option = AUDIO_QUALITIES[self.selected_quality_key]
                ydl_opts['format'] = audio_option['format']
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': audio_option['postprocessor_quality'],
                }]
                self.progress_signal.emit(f"Kiváaszott fáljkiterjesztés: MP3 ({self.selected_quality_key})")
            else:
                raise ValueError(f"Rossz fálj formátum: {self.selected_format_type}")

            try:
                 with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True, 'noplaylist': True}) as ydl_info:
                     info_dict = ydl_info.extract_info(self.url, download=False)
                     video_title = info_dict.get('title', video_title)
            except Exception as info_e:
                 self.progress_signal.emit(f"Nem sikerült a videó adatait megszerezni: {info_e}")


            os.makedirs(self.output_path, exist_ok=True)
            self.progress_signal.emit(f"Letöltés '{video_title}'...")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])

            if not self.is_cancelled:
                final_filepath = self._actual_filename or os.path.join(self.output_path, f"{video_title}.{self.selected_format_type.lower()}")
                if self._actual_filename and not os.path.isabs(self._actual_filename):
                    final_filepath = os.path.join(self.output_path, os.path.basename(self._actual_filename))


                self.finished_signal.emit(
                    f"Letöltés befejezve: '{video_title}' ({self.selected_format_type})\nSaved to: {final_filepath}"
                )
            else:
                 self.error_signal.emit("Letöltás leállítva.")


        except yt_dlp.utils.DownloadCancelled as e:
             self.error_signal.emit(f"Letöltás leállítva.: {e}")
        except yt_dlp.utils.DownloadError as e:
            if self.selected_format_type == 'MP3' and ('ffmpeg' in str(e).lower() or 'postprocessor' in str(e).lower()):
                 self.error_signal.emit(f"Letöltés hiba: {e}\n\n>>>>>\n>>>>> Make sure FFmpeg is installed and accessible in your system's PATH.\n>>>>> MP3 conversion requires FFmpeg.\n>>>>>")
            else:
                self.error_signal.emit(f"Letöltés hiba: {e}")
        except Exception as e:
            self.error_signal.emit(f"Nemvárt hiba: {e}")
        finally:
            if not self.is_cancelled:
                 self.progress_bar_signal.emit(0)

    def cancel(self):
        self.is_cancelled = True
        self.progress_signal.emit("Megszakítás...")


class YouTubeDownloaderApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Yt-DLP Downloader")
        self.setGeometry(200, 200, 650, 450)

        self.download_thread = None
        self.current_output_path = "downloads"

        self.main_layout = QVBoxLayout(self)
        self.url_layout = QHBoxLayout()
        self.path_layout = QHBoxLayout()
        self.options_layout = QHBoxLayout()
        self.button_layout = QHBoxLayout()


        self.url_label = QLabel("YouTube URL:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Ide írd a YouTube videó URL-jét...")   
        self.url_layout.addWidget(self.url_label)
        self.url_layout.addWidget(self.url_input)

        self.path_label = QLabel(f"Letöltés helye: {self.current_output_path}")
        self.path_button = QPushButton("Változtatás...")
        self.path_button.clicked.connect(self.select_output_path)
        self.path_layout.addWidget(self.path_label, 1)
        self.path_layout.addWidget(self.path_button)


        self.options_group = QGroupBox("Letöltési beállítások")
        self.options_group_layout = QHBoxLayout(self.options_group)


        self.format_label = QLabel("Fáljformátum:")
        self.format_combo = QComboBox()
        self.format_combo.addItems(["MP4 (Video)", "MP3 (Audio)"])
        self.format_combo.currentIndexChanged.connect(self.update_quality_options)


        self.video_quality_label = QLabel("Video minősége:")
        self.video_quality_combo = QComboBox()
        self.video_quality_combo.addItems(VIDEO_QUALITIES.keys())


        self.audio_quality_label = QLabel("Audio minősége:")
        self.audio_quality_combo = QComboBox()
        self.audio_quality_combo.addItems(AUDIO_QUALITIES.keys())
        self.audio_quality_label.setVisible(False) 
        self.audio_quality_combo.setVisible(False)

        self.options_group_layout.addWidget(self.format_label)
        self.options_group_layout.addWidget(self.format_combo)
        self.options_group_layout.addWidget(self.video_quality_label)
        self.options_group_layout.addWidget(self.video_quality_combo)
        self.options_group_layout.addWidget(self.audio_quality_label)
        self.options_group_layout.addWidget(self.audio_quality_combo)
        self.options_group_layout.addStretch() 


        self.download_button = QPushButton("Letöltés")
        self.download_button.clicked.connect(self.start_download)
        self.cancel_button = QPushButton("Megszakítás")
        self.cancel_button.clicked.connect(self.cancel_download)
        self.cancel_button.setVisible(False)

        self.button_layout.addWidget(self.download_button)
        self.button_layout.addWidget(self.cancel_button)


        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")


        self.status_label = QLabel("Kimenet:")
        self.status_output = QTextEdit()
        self.status_output.setReadOnly(True)
        self.status_output.setAcceptRichText(False)


        self.main_layout.addLayout(self.url_layout)
        self.main_layout.addLayout(self.path_layout)
        self.main_layout.addWidget(self.options_group)
        self.main_layout.addLayout(self.button_layout)
        self.main_layout.addWidget(self.progress_bar)
        self.main_layout.addWidget(self.status_label)
        self.main_layout.addWidget(self.status_output, 1)


        self.update_quality_options()

    def select_output_path(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Letöltés helye:", self.current_output_path
        )
        if directory:
            self.current_output_path = directory
            self.path_label.setText(f"Mentés helye: {self.current_output_path}")
            self.status_output.append(f"Letöltés helye megadva: {self.current_output_path}")

    def update_quality_options(self):
        selected_format = self.format_combo.currentText()

        if "MP4" in selected_format:
            self.video_quality_label.setVisible(True)
            self.video_quality_combo.setVisible(True)
            self.audio_quality_label.setVisible(False)
            self.audio_quality_combo.setVisible(False)
        elif "MP3" in selected_format:
            self.video_quality_label.setVisible(False)
            self.video_quality_combo.setVisible(False)
            self.audio_quality_label.setVisible(True)
            self.audio_quality_combo.setVisible(True)

    def start_download(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Bemeneti hiba", "Légyszives add meg a YouTube videó URL-jét.")
            return
        if not ("youtube.com/watch?v=" in url or "youtu.be/" in url):
             QMessageBox.warning(self, "Bemeneti hiba", "Légyszives egy valós linket adj meg(https://www.youtube.com/watch?v=...).")
             return

        if self.download_thread and self.download_thread.isRunning():
            QMessageBox.warning(self, "Foglalt", "Egy letöltés már folyamatban van. Kérlek várj.")
            return

        selected_format_text = self.format_combo.currentText()
        selected_format_type = "MP4" if "MP4" in selected_format_text else "MP3"

        if selected_format_type == "MP4":
            selected_quality_key = self.video_quality_combo.currentText()
        else:
            selected_quality_key = self.audio_quality_combo.currentText()

        self.download_button.setEnabled(False)
        self.cancel_button.setVisible(True)
        self.url_input.setEnabled(False)
        self.path_button.setEnabled(False)
        self.format_combo.setEnabled(False)
        self.video_quality_combo.setEnabled(False)
        self.audio_quality_combo.setEnabled(False)
        self.status_output.clear()
        self.status_output.append("Felkészülés a letöltésre...")
        self.progress_bar.setValue(0)
        self.download_thread = DownloadWorker(
            url,
            self.current_output_path,
            selected_format_type,
            selected_quality_key
        )
        self.download_thread.progress_signal.connect(self.update_status)
        self.download_thread.progress_bar_signal.connect(self.update_progress_bar)
        self.download_thread.finished_signal.connect(self.download_finished)
        self.download_thread.error_signal.connect(self.download_error)
        self.download_thread.finished.connect(self.thread_cleanup)

        self.download_thread.start()

    def cancel_download(self):
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.cancel()
        else:
             self.status_output.append("Nincs aktív letöltés a megszakításhoz.")

    def update_status(self, message):
        if message.startswith('\r'):
             current_text = self.status_output.toPlainText()
             last_newline = current_text.rfind('\n')
             base_text = current_text[:last_newline + 1] if last_newline != -1 else ""
             self.status_output.setPlainText(base_text + message.lstrip('\r'))
        else:
             self.status_output.append(message)

        self.status_output.verticalScrollBar().setValue(
            self.status_output.verticalScrollBar().maximum()
        )

    def update_progress_bar(self, value):
        self.progress_bar.setValue(value)

    def download_finished(self, message):
        QMessageBox.information(self, "Sikeres", f"Letöltés befejezve!\n{message}")

        self.reset_ui_state()

    def download_error(self, error_message):
        QMessageBox.critical(self, "Hiba", f"Hiba történt:\n{error_message}")
        self.status_output.append(f"\nHIBA: {error_message}")
        self.reset_ui_state()

    def thread_cleanup(self):
        self.download_thread = None

    def reset_ui_state(self):
        self.download_button.setEnabled(True)
        self.cancel_button.setVisible(False)
        self.url_input.setEnabled(True)
        self.path_button.setEnabled(True)
        self.format_combo.setEnabled(True)
        self.video_quality_combo.setEnabled(True)
        self.audio_quality_combo.setEnabled(True)
        self.progress_bar.setValue(0)

    def closeEvent(self, event):
        if self.download_thread and self.download_thread.isRunning():
            reply = QMessageBox.question(self, 'Letöltés megszakítása',
                                         "Egy letöltés folyamatban van. Biztosan ki szeretnél lépni? A letöltés megszakításra kerül.",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.cancel_download()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

# --- Main Execution ---
if __name__ == "__main__":
    if not os.path.exists("downloads"):
        try:
            os.makedirs("downloads")
        except OSError as e:
            print(f"Figyelmeztetés: Nem sikerült létrehozni a 'downloads' mappát: {e}")

    app = QApplication(sys.argv)
    window = YouTubeDownloaderApp()
    window.show()
    sys.exit(app.exec())