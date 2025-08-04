#!/usr/bin/env python3
"""
Git Analyzer - PyQt6 GUI Application (Redesigned UI)
A modern, professional, and minimal interface for a GitHub analysis tool.
Features a multi-page layout and asynchronous operations to prevent UI freezing.
"""

import sys
import requests
import re
import traceback
from typing import Optional, Tuple
from dataclasses import dataclass
from decouple import config

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QGridLayout, QWidget,
    QLabel, QLineEdit, QPushButton, QComboBox, QGroupBox, QMessageBox, QStatusBar,
    QFrame, QStyle, QListWidget, QTextEdit, QStackedWidget
)
from PyQt6.QtCore import Qt, QTimer, QObject, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QIcon, QPixmap, QFontDatabase, QTextCursor

# --- Import the actual logic handlers ---
try:
    from github.handler import GithubProfile, GithubRepo, GithubCommit
    from github.ai_analyzer import analyze_commit_list_with_ai, commit_best_practice, write_commit_message, write_commit_base_on_diff
except ImportError:
    print("Warning: A handler was not found. Using mock classes for GUI demonstration.")
    class GithubProfile:
        def __init__(self):
            self.avatar = None
        def test_github_connection(self, token): import time; time.sleep(1); return True
        def _set_owner_name(self, token):
            self.avatar = 'https://placehold.co/50x50/2dd4bf/1f2937?text=U'
            return "mock_user"
    class GithubRepo:
        def get_user_repositories(self, token, owner): import time; time.sleep(1); return ["modern-ui-project", "api-backend", "learning-python"]
    @dataclass
    class GithubCommit:
        def get_repo_commits(self, token:str, owner:str, repo:str) -> list:
            import time; time.sleep(1.5)
            return ["feat: Add user authentication service", "fix: Resolve alignment issue on dashboard cards", "docs: Update API endpoint documentation"]
    def analyze_commit_list_with_ai(commit_messages: list[str]) -> str:
        import time; time.sleep(2)
        return "**Overall Analysis:**\n- Good use of conventional commits."
    def commit_best_practice(commit_message: str) -> str:
        import time; time.sleep(1)
        return f"fix: Correct alignment on dashboard cards"
    def write_commit_message(message: str) -> str:
        import time; time.sleep(1.5)
        return f"feat: Implement new feature based on user description\n\n- Added logic for {message.split()[0]}\n- Updated UI components"
    def write_commit_base_on_diff(old_code: str, new_code: str) -> str:
        import time; time.sleep(2)
        return "refactor: Simplify logic in main function\n\n- Replaced complex loop with list comprehension for clarity.\n- Removed redundant variable assignments."

# --- Custom Widget for Plain Text Pasting ---
class CodeTextEdit(QTextEdit):
    """A QTextEdit that only allows plain text to be pasted."""
    def insertFromMimeData(self, source):
        if source.hasText():
            self.insertPlainText(source.text())

# --- Worker Thread for Asynchronous Operations ---
class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)

class Worker(QObject):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:
            self.signals.error.emit((type(e), e, traceback.format_exc()))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()

# --- Main Application ---
class GitAnalyzerGUI(QMainWindow):
    """The main window for the Git Analyzer application."""
    def __init__(self):
        super().__init__()
        self.token = None
        self.owner = None
        self.github_profile = GithubProfile()
        self.github_repo = GithubRepo()
        self.thread = None
        self.worker = None

        self.init_ui()
        self.setup_styles()
        QTimer.singleShot(100, self.initialize_app)

    def init_ui(self):
        self.setWindowTitle("Git Analyzer")
        self.resize(1200, 850)
        self.setMinimumSize(1000, 750)
        self.setWindowIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.loading_label = QLabel("Initializing...")
        self.loading_label.setObjectName("loadingLabel")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.loading_label)

        self.main_content_widget = QWidget()
        main_content_layout = QVBoxLayout(self.main_content_widget)
        main_content_layout.setContentsMargins(25, 20, 25, 10)
        main_content_layout.setSpacing(20)
        
        # Header
        self.header_layout = QHBoxLayout()
        self.title_label = QLabel("Git Analyzer")
        self.title_label.setObjectName("headerTitle")
        self.profile_widget = QWidget()
        profile_layout = QHBoxLayout(self.profile_widget)
        profile_layout.setContentsMargins(0, 0, 0, 0)
        profile_layout.setSpacing(12)
        self.avatar_label = QLabel()
        self.avatar_label.setObjectName("avatarLabel")
        self.avatar_label.setFixedSize(44, 44)
        self.username_label = QLabel()
        self.username_label.setObjectName("headerUsername")
        profile_layout.addWidget(self.avatar_label)
        profile_layout.addWidget(self.username_label)
        self.header_layout.addWidget(self.title_label)
        self.header_layout.addWidget(self.profile_widget)
        self.header_layout.addStretch()
        self.profile_widget.setVisible(False)
        
        self.nav_button_layout = QHBoxLayout()
        self.analyze_page_btn = QPushButton("Analyze Commits")
        self.analyze_page_btn.setObjectName("navButton")
        self.analyze_page_btn.setCheckable(True)
        self.analyze_page_btn.setChecked(True)
        self.diff_page_btn = QPushButton("Generate from Diff")
        self.diff_page_btn.setObjectName("navButton")
        self.diff_page_btn.setCheckable(True)
        self.nav_button_layout.addWidget(self.analyze_page_btn)
        self.nav_button_layout.addWidget(self.diff_page_btn)
        self.nav_button_layout.addStretch()
        self.header_layout.addLayout(self.nav_button_layout)
        main_content_layout.addLayout(self.header_layout)

        self.stacked_widget = QStackedWidget()
        main_content_layout.addWidget(self.stacked_widget)

        self.analysis_page = self.create_analysis_page()
        self.stacked_widget.addWidget(self.analysis_page)
        self.diff_page = self.create_diff_page()
        self.stacked_widget.addWidget(self.diff_page)
        
        self.analyze_page_btn.clicked.connect(lambda: self.switch_page(0))
        self.diff_page_btn.clicked.connect(lambda: self.switch_page(1))
        
        self.main_layout.addWidget(self.main_content_widget)
        self.main_content_widget.setVisible(False)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def create_analysis_page(self):
        page_widget = QWidget()
        content_layout = QHBoxLayout(page_widget)
        content_layout.setContentsMargins(0, 15, 0, 0)
        content_layout.setSpacing(25)
        
        left_column_widget = QWidget()
        workflow_layout = QVBoxLayout(left_column_widget)
        workflow_layout.setContentsMargins(0,0,0,0)
        workflow_layout.setSpacing(20)

        connection_group = QGroupBox("1. Connect to GitHub")
        connection_layout = QGridLayout(connection_group)
        connection_layout.setContentsMargins(20, 30, 20, 20)
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("GitHub Personal Access Token")
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.textChanged.connect(self.on_token_change)
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setObjectName("connectButton")
        self.connect_btn.clicked.connect(self.connect_to_github)
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setObjectName("disconnectButton")
        self.disconnect_btn.clicked.connect(self.disconnect_from_github)
        self.disconnect_btn.setVisible(False)
        self.connection_status = QLabel("Not Connected")
        self.connection_status.setObjectName("statusError")
        connection_layout.addWidget(self.token_input, 0, 0)
        connection_layout.addWidget(self.connect_btn, 0, 1)
        connection_layout.addWidget(self.disconnect_btn, 0, 1)
        connection_layout.addWidget(self.connection_status, 1, 0, 1, 2)
        workflow_layout.addWidget(connection_group)

        self.analysis_workflow_group = QGroupBox("2. Analyze Repository")
        analysis_workflow_layout = QVBoxLayout(self.analysis_workflow_group)
        analysis_workflow_layout.setContentsMargins(20, 30, 20, 20)
        analysis_workflow_layout.setSpacing(15)
        self.repo_combo = QComboBox()
        self.repo_combo.addItem("Select a Repository...")
        self.repo_combo.currentIndexChanged.connect(self.on_repo_selected)
        self.commit_list_widget = QListWidget()
        self.commit_list_widget.itemSelectionChanged.connect(self.on_commit_selection_changed)
        self.best_practice_btn = QPushButton("Show Best Practice")
        self.best_practice_btn.clicked.connect(self.run_single_commit_analysis)
        self.best_practice_btn.setEnabled(False)
        analysis_workflow_layout.addWidget(self.repo_combo)
        analysis_workflow_layout.addWidget(self.commit_list_widget)
        analysis_workflow_layout.addWidget(self.best_practice_btn)
        self.analysis_workflow_group.setEnabled(False)
        workflow_layout.addWidget(self.analysis_workflow_group)
        
        right_column_widget = QWidget()
        ai_tools_layout = QVBoxLayout(right_column_widget)
        ai_tools_layout.setContentsMargins(0,0,0,0)
        ai_tools_layout.setSpacing(20)

        self.analysis_group = QGroupBox("Overall Commit Analysis")
        analysis_layout = QVBoxLayout(self.analysis_group)
        analysis_layout.setContentsMargins(20, 30, 20, 20)
        self.analysis_results_text = QTextEdit()
        self.analysis_results_text.setReadOnly(True)
        self.analysis_results_text.setPlaceholderText("Load commits to enable analysis...")
        self.analyze_commits_btn = QPushButton("Analyze All Commits")
        self.analyze_commits_btn.clicked.connect(self.run_ai_analysis)
        analysis_layout.addWidget(self.analysis_results_text)
        analysis_layout.addWidget(self.analyze_commits_btn)
        self.analysis_group.setEnabled(False)
        ai_tools_layout.addWidget(self.analysis_group)
        
        self.write_commit_group = QGroupBox("Write My Commit")
        write_commit_layout = QVBoxLayout(self.write_commit_group)
        write_commit_layout.setContentsMargins(20, 30, 20, 20)
        self.commit_input_text = QTextEdit()
        self.commit_input_text.setPlaceholderText("Describe your changes...")
        self.commit_input_text.setFixedHeight(80)
        self.generated_commit_text = QTextEdit()
        self.generated_commit_text.setReadOnly(True)
        self.generated_commit_text.setPlaceholderText("AI-generated message...")
        self.generate_commit_btn = QPushButton("Generate Commit Message")
        self.generate_commit_btn.clicked.connect(self.run_write_commit_analysis)
        write_commit_layout.addWidget(self.commit_input_text)
        write_commit_layout.addWidget(self.generated_commit_text)
        write_commit_layout.addWidget(self.generate_commit_btn)
        self.write_commit_group.setEnabled(False)
        ai_tools_layout.addWidget(self.write_commit_group)
        
        content_layout.addWidget(left_column_widget, 1)
        content_layout.addWidget(right_column_widget, 1)
        
        return page_widget

    def create_diff_page(self):
        page_widget = QWidget()
        layout = QVBoxLayout(page_widget)
        layout.setContentsMargins(0, 15, 0, 0)
        layout.setSpacing(20)

        diff_group = QGroupBox("Generate Commit from Code Changes")
        diff_layout = QGridLayout(diff_group)
        diff_layout.setContentsMargins(20, 30, 20, 20)
        diff_layout.setSpacing(15)

        self.old_code_text = CodeTextEdit()
        self.old_code_text.setObjectName("codeInput")
        self.old_code_text.setPlaceholderText("Paste the OLD code here...")
        self.old_code_text.textChanged.connect(lambda: self.limit_text_edit_lines(self.old_code_text, 200))
        
        self.new_code_text = CodeTextEdit()
        self.new_code_text.setObjectName("codeInput")
        self.new_code_text.setPlaceholderText("Paste the NEW code here...")
        self.new_code_text.textChanged.connect(lambda: self.limit_text_edit_lines(self.new_code_text, 200))
        
        self.generated_diff_commit_text = QTextEdit()
        self.generated_diff_commit_text.setReadOnly(True)
        self.generated_diff_commit_text.setPlaceholderText("AI-generated commit message will appear here...")

        self.generate_from_diff_btn = QPushButton("Generate Commit Message from Diff")
        self.generate_from_diff_btn.setObjectName("generate_from_diff_btn")
        self.generate_from_diff_btn.clicked.connect(self.run_diff_analysis)

        diff_layout.addWidget(QLabel("Previous Code:"), 0, 0)
        diff_layout.addWidget(self.old_code_text, 1, 0)
        diff_layout.addWidget(QLabel("New Code:"), 0, 1)
        diff_layout.addWidget(self.new_code_text, 1, 1)
        diff_layout.addWidget(self.generated_diff_commit_text, 2, 0, 1, 2)
        diff_layout.addWidget(self.generate_from_diff_btn, 3, 0, 1, 2)

        layout.addWidget(diff_group)
        return page_widget

    def setup_styles(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #111827; }
            QWidget {
                color: #9CA3AF;
                font-family: 'Inter', 'Segoe UI', sans-serif;
                font-size: 14px;
            }
            QGroupBox {
                font-weight: 600; font-size: 16px; color: #E5E7EB;
                border: 1px solid #374151; border-radius: 12px;
                background-color: #1F2937;
            }
            QGroupBox::title {
                subcontrol-origin: margin; subcontrol-position: top left;
                padding: 4px 12px; left: 15px;
                background-color: #374151;
                color: #E5E7EB;
                border-radius: 6px;
            }
            QLabel#headerTitle { font-size: 28px; font-weight: 700; color: #F9FAFB; }
            QLabel#headerUsername { font-size: 24px; font-weight: 600; color: #F9FAFB; }
            QLabel#avatarLabel { border-radius: 22px; }
            QLabel#statusSuccess { color: #2DD4BF; }
            QLabel#statusError { color: #F87171; }
            QLabel#loadingLabel { font-size: 20px; color: #4B5563; font-weight: 600; }
            QLineEdit, QComboBox, QTextEdit, QListWidget {
                border: 1px solid #4B5563;
                border-radius: 8px; 
                background-color: #374151;
                color: #D1D5DB;
                padding: 10px;
            }
            QTextEdit#codeInput {
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QListWidget:focus {
                border-color: #2DD4BF;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background-color: #374151; border: 1px solid #4B5563;
                selection-background-color: #2DD4BF;
                selection-color: #111827;
                padding: 4px;
            }
            QPushButton {
                background-color: #4B5563; border: none;
                color: #F9FAFB; padding: 10px;
                border-radius: 8px; font-weight: 600;
            }
            QPushButton:hover { background-color: #6B7280; }
            QPushButton:pressed { background-color: #4B5563; }
            QPushButton:disabled { background-color: #374151; color: #6B7280; }
            QPushButton#connectButton, #generate_from_diff_btn, #generate_commit_btn {
                background-color: #2DD4BF; color: #111827;
            }
            QPushButton#connectButton:hover, #generate_from_diff_btn:hover, #generate_commit_btn:hover { background-color: #5EEAD4; }
            QPushButton#disconnectButton {
                background-color: #F87171; color: #111827;
            }
            QPushButton#disconnectButton:hover { background-color: #FCA5A5; }
            QPushButton#navButton {
                background-color: transparent;
                border: 1px solid #4B5563;
                padding: 8px 16px;
            }
            QPushButton#navButton:checked {
                background-color: #374151;
                border: 1px solid #2DD4BF;
                color: #2DD4BF;
            }
            QStatusBar {
                background-color: #1F2937; border-top: 1px solid #374151;
            }
            QMessageBox { background-color: #1F2937; }
            QListWidget::item { 
                padding: 8px; 
                border-bottom: 1px solid #374151;
            }
            QListWidget::item:selected {
                background-color: #374151; color: #2DD4BF;
                border: none;
            }
            QListWidget { 
                outline: 0px; 
                border-radius: 8px;
            }
        """)

    def switch_page(self, index):
        self.stacked_widget.setCurrentIndex(index)
        self.analyze_page_btn.setChecked(index == 0)
        self.diff_page_btn.setChecked(index == 1)

    def run_task_in_thread(self, task_function, on_result, on_error, *args):
        if self.thread is not None and self.thread.isRunning():
            QMessageBox.warning(self, "Busy", "An operation is already in progress. Please wait.")
            return

        self.thread = QThread()
        self.worker = Worker(task_function, *args)
        self.worker.moveToThread(self.thread)
        
        self.worker.signals.result.connect(on_result)
        self.worker.signals.error.connect(on_error)
        
        self.worker.signals.finished.connect(self.thread.quit)
        self.worker.signals.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self._on_thread_finished)
        
        self.thread.started.connect(self.worker.run)
        self.thread.start()

    def _on_thread_finished(self):
        self.thread = None
        self.worker = None

    def initialize_app(self):
        token = config("GITHUB_ACCESS_TOKEN", default=None)
        if token:
            self.token_input.setText(token)
            self.connect_to_github()
        else:
            self.loading_label.setVisible(False)
            self.main_content_widget.setVisible(True)

    def on_token_change(self, text):
        if not self.token:
            self.connect_btn.setEnabled(bool(text.strip()))

    def update_connection_status(self, message, is_success):
        self.connection_status.setText(message)
        self.connection_status.setObjectName("statusSuccess" if is_success else "statusError")
        self.connection_status.style().unpolish(self.connection_status)
        self.connection_status.style().polish(self.connection_status)

    def connect_to_github(self):
        token = self.token_input.text().strip()
        if not token: return
        self.connect_btn.setEnabled(False)
        self.connect_btn.setText("Connecting...")
        self.run_task_in_thread(self._task_connect, self._on_connect_result, self._on_task_error, token)

    def _task_connect(self, token):
        if self.github_profile.test_github_connection(token):
            owner = self.github_profile._set_owner_name(token)
            if owner:
                return (token, owner, self.github_profile.avatar)
            raise ValueError("Failed to retrieve owner name.")
        raise ConnectionError("Token may be invalid.")

    def _on_connect_result(self, result):
        token, owner, avatar_url = result
        self.token, self.owner = token, owner
        self.update_connection_status("✅ Connected", True)
        self.analysis_workflow_group.setEnabled(True)
        self.write_commit_group.setEnabled(True)
        self.token_input.setEnabled(False)
        self.connect_btn.setVisible(False)
        self.disconnect_btn.setVisible(True)
        self.update_header_with_profile(avatar_url, owner)
        self.load_repositories()
        self.loading_label.setVisible(False)
        self.main_content_widget.setVisible(True)

    def disconnect_from_github(self):
        self.token, self.owner = None, None
        self.token_input.clear()
        self.token_input.setEnabled(True)
        self.update_connection_status("Not Connected", False)
        self.repo_combo.clear()
        self.repo_combo.addItem("Select a Repository...")
        self.commit_list_widget.clear()
        self.analysis_results_text.clear()
        self.commit_input_text.clear()
        self.generated_commit_text.clear()
        for group in [self.analysis_workflow_group, self.analysis_group, self.write_commit_group]:
            group.setEnabled(False)
        self.disconnect_btn.setVisible(False)
        self.connect_btn.setVisible(True)
        self.connect_btn.setText("Connect")
        self.connect_btn.setEnabled(False)
        self.reset_header()

    def update_header_with_profile(self, avatar_url, owner):
        if not avatar_url:
            self.username_label.setText(owner)
            self.title_label.setVisible(False)
            self.profile_widget.setVisible(True)
            return
        self.run_task_in_thread(self._task_fetch_avatar, self._on_avatar_result, self._on_task_error, avatar_url, owner)

    def _task_fetch_avatar(self, url, owner):
        response = requests.get(url, stream=True)
        response.raise_for_status()
        return (response.content, owner)

    def _on_avatar_result(self, result):
        image_data, owner = result
        pixmap = QPixmap()
        pixmap.loadFromData(image_data)
        pixmap = pixmap.scaled(44, 44, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.avatar_label.setPixmap(pixmap)
        self.username_label.setText(owner)
        self.title_label.setVisible(False)
        self.profile_widget.setVisible(True)
    
    def reset_header(self):
        self.profile_widget.setVisible(False)
        self.title_label.setVisible(True)

    def load_repositories(self):
        self.run_task_in_thread(self.github_repo.get_user_repositories, self._on_load_repos_result, self._on_task_error, self.token, self.owner)

    def _on_load_repos_result(self, repos):
        self.repo_combo.clear()
        if repos:
            self.repo_combo.addItem("Select a Repository...")
            self.repo_combo.addItems(sorted(repos, key=str.lower))
        else:
            self.repo_combo.addItem("No repositories found.")

    def on_repo_selected(self, index):
        self.commit_list_widget.clear()
        self.analysis_results_text.clear()
        self.best_practice_btn.setEnabled(False)
        self.analysis_group.setEnabled(False)
        if index > 0:
            self.load_commits()

    def on_commit_selection_changed(self):
        self.best_practice_btn.setEnabled(len(self.commit_list_widget.selectedItems()) > 0)

    def load_commits(self):
        repo = self.repo_combo.currentText()
        if not repo or repo == "Select a Repository...": return
        self.commit_list_widget.clear()
        self.run_task_in_thread(self._task_load_commits, self._on_load_commits_result, self._on_task_error, repo)

    def _task_load_commits(self, repo):
        commit_handler = GithubCommit()
        repo_name = repo.split('/')[-1]
        return commit_handler.get_repo_commits(self.token, self.owner, repo_name)

    def _on_load_commits_result(self, commits):
        self.commit_list_widget.clear()
        if commits:
            self.commit_list_widget.addItems(commits)
            self.analysis_group.setEnabled(True)
        else:
            self.commit_list_widget.addItem("No commits found.")

    def run_ai_analysis(self):
        items = [self.commit_list_widget.item(i).text() for i in range(self.commit_list_widget.count())]
        if not items or "No commits found" in items[0]: return
        self.analyze_commits_btn.setEnabled(False)
        self.analyze_commits_btn.setText("Analyzing...")
        self.run_task_in_thread(analyze_commit_list_with_ai, self._on_ai_analysis_result, self._on_task_error, items)

    def _on_ai_analysis_result(self, result):
        self.analysis_results_text.setText(result)
        self.analyze_commits_btn.setEnabled(True)
        self.analyze_commits_btn.setText("Analyze All Commits")
    
    def run_single_commit_analysis(self):
        selected = self.commit_list_widget.selectedItems()
        if not selected: return
        message = selected[0].text().split('/')[-1].strip()
        self.best_practice_btn.setEnabled(False)
        self.best_practice_btn.setText("Improving...")
        self.run_task_in_thread(commit_best_practice, lambda result: self._on_single_analysis_result(result, message), self._on_task_error, message)

    def _on_single_analysis_result(self, result, original_message):
        formatted_original = original_message.replace('\n', '<br>')
        formatted_best = result.replace('\n', '<br>')
        QMessageBox.information(self, "Commit Best Practice", f"- <b>Original:</b><br>{formatted_original}<br><br>- <b>Best Practice Version:</b><br>{formatted_best}")
        self.best_practice_btn.setEnabled(True)
        self.best_practice_btn.setText("Show Best Practice")

    def run_write_commit_analysis(self):
        desc = self.commit_input_text.toPlainText().strip()
        if not desc: return
        self.generate_commit_btn.setEnabled(False)
        self.generate_commit_btn.setText("Generating...")
        self.run_task_in_thread(write_commit_message, self._on_write_commit_result, self._on_task_error, desc)

    def _on_write_commit_result(self, result):
        self.generated_commit_text.setText(result)
        self.generate_commit_btn.setEnabled(True)
        self.generate_commit_btn.setText("Generate Commit Message")

    def limit_text_edit_lines(self, text_edit, max_lines):
        text = text_edit.toPlainText()
        lines = text.split('\n')
        if len(lines) > max_lines:
            new_text = '\n'.join(lines[:max_lines])
            cursor = text_edit.textCursor()
            pos = cursor.position()
            text_edit.setPlainText(new_text)
            cursor.setPosition(min(pos, len(new_text)))
            text_edit.setTextCursor(cursor)

    def run_diff_analysis(self):
        old_code = self.old_code_text.toPlainText().strip()
        new_code = self.new_code_text.toPlainText().strip()
        if not old_code or not new_code:
            QMessageBox.warning(self, "Input Required", "Please provide both the old and new code.")
            return
        self.generate_from_diff_btn.setEnabled(False)
        self.generate_from_diff_btn.setText("Generating...")
        self.run_task_in_thread(write_commit_base_on_diff, self._on_diff_analysis_result, self._on_task_error, old_code, new_code)

    def _on_diff_analysis_result(self, result):
        self.generated_diff_commit_text.setText(result)
        self.generate_from_diff_btn.setEnabled(True)
        self.generate_from_diff_btn.setText("Generate Commit Message from Diff")

    def _on_task_error(self, error_tuple):
        exctype, value, tb = error_tuple
        print(tb)
        QMessageBox.critical(self, "Error", f"An error occurred:\n{value}")
        # Reset UI state
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText("Connect")
        self.best_practice_btn.setEnabled(len(self.commit_list_widget.selectedItems()) > 0)
        self.best_practice_btn.setText("Show Best Practice")
        self.analyze_commits_btn.setEnabled(self.analysis_group.isEnabled())
        self.analyze_commits_btn.setText("Analyze All Commits")
        self.generate_commit_btn.setEnabled(True)
        self.generate_commit_btn.setText("Generate Commit Message")
        self.generate_from_diff_btn.setEnabled(True)
        self.generate_from_diff_btn.setText("Generate Commit Message from Diff")

    def closeEvent(self, event):
        """Ensure background threads are stopped before closing."""
        if self.thread and self.thread.isRunning():
            print("Waiting for background thread to finish...")
            self.thread.quit()
            if not self.thread.wait(5000): # Wait for 5 seconds
                print("Thread did not finish in time. Forcing termination.")
                self.thread.terminate()
                self.thread.wait()
        event.accept()
