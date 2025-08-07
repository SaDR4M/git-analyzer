#!/usr/bin/env python3
"""
Git Analyzer - PyQt6 GUI Application (Redesigned UI)
A modern, professional, and minimal interface for a GitHub analysis tool.
Features a multi-page layout and asynchronous operations to prevent UI freezing.
"""

import sys
import os
import requests
import re
import traceback
from typing import Optional, Tuple, Dict, List
from dataclasses import dataclass
from decouple import config

# --- GitPython Import ---
# This is now a hard dependency for the local features.
try:
    from git import Repo, InvalidGitRepositoryError
except ImportError:
    print("FATAL ERROR: GitPython is not installed. Please run 'pip install GitPython'")
    sys.exit(1)


from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QGridLayout, QWidget,
    QLabel, QLineEdit, QPushButton, QComboBox, QGroupBox, QMessageBox, QStatusBar,
    QFrame, QStyle, QListWidget, QTextEdit, QStackedWidget, QFileDialog
)
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal, pyqtSlot, QRunnable, QThreadPool
from PyQt6.QtGui import QIcon, QPixmap, QFontDatabase, QTextCursor

# --- Import the actual logic handlers ---
try:
    from github.handler import GithubProfile, GithubRepo, GithubCommit
    from github.ai_analyzer import analyze_commit_list_with_ai, commit_best_practice, write_commit_message, write_commit_base_on_diff, write_commits_for_staged_changes
except ImportError:
    print("Warning: A remote handler was not found. Using mock classes for GUI demonstration.")
    class GithubProfile:
        def __init__(self):
            self.avatar = None
        def test_github_connection(self, token): import time; time.sleep(1); return True
        def _set_owner_name(self, token):
            self.avatar = 'https://placehold.co/50x50/2dd4bf/1f2937?text=U'
            return "mock_user"
    class GithubRepo:
        def get_user_repositories(self, token, owner): 
            import time; time.sleep(1)
            return [
                {"mock_user/modern-ui-project": "https://..."},
                {"mock_user/api-backend": "https://..."},
                {"mock_user/learning-python": "https://..."}
            ]
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
    def write_commits_for_staged_changes(staged_changes:dict) -> str:
        import time; time.sleep(2)
        num_files = len(staged_changes)
        return f"feat: Update {num_files} files\n\n- Refactored core logic for performance.\n- Updated documentation and tests."


# --- Real GitRepo Class ---
class GitRepo:
    """Handles all local Git repository interactions."""
    def __init__(self):
        self.staged_diffs = []

    def _decode_blob(self, diff):
        """Safely decodes blob content to string."""
        try:
            old_content = diff.a_blob.data_stream.read().decode('utf-8')
        except (AttributeError, UnicodeDecodeError):
            old_content = "" # File is new or is binary
        try:
            new_content = diff.b_blob.data_stream.read().decode('utf-8')
        except (AttributeError, UnicodeDecodeError):
            new_content = "" # File was deleted or is binary
        return old_content, new_content

    def get_status(self, path: str) -> Dict[str, List[Dict[str, str]]]:
        """
        Gets the status of the local repository, separating staged and unstaged files.
        Also caches the staged diff objects for later use.
        """
        if not os.path.isdir(path):
            raise ValueError("Invalid directory path provided.")
        
        try:
            repo = Repo(path, search_parent_directories=True)
        except InvalidGitRepositoryError:
            raise InvalidGitRepositoryError("The selected folder is not a valid Git repository.")

        self.staged_diffs = list(repo.index.diff(repo.head.commit))
        
        staged_files = []
        for diff in self.staged_diffs:
            staged_files.append({"file_name": diff.a_path, "change_type": diff.change_type})

        unstaged_files = []
        for diff in repo.index.diff(None):
            unstaged_files.append({"file_name": diff.a_path, "change_type": diff.change_type})
        
        untracked = repo.untracked_files
        for file_path in untracked:
            if not any(f['file_name'] == file_path for f in unstaged_files):
                unstaged_files.append({"file_name": file_path, "change_type": "A"})

        return {"staged": staged_files, "unstaged": unstaged_files}

    def combine_all_blobs(self) -> dict:
        """Combine all diffs to analyze the staged changes commits"""
        combined_diffs = {}
        for diff in self.staged_diffs:
            file_path = diff.b_path or diff.a_path
            if not file_path:
                continue # Should not happen, but good practice
            
            old_content, new_content = self._decode_blob(diff)
            combined_diffs[file_path] = {"old": old_content, "new": new_content}
    
        return combined_diffs

    def stage_files(self, path: str, files_to_stage: List[str]):
        """Stages a list of files in the given repository."""
        repo = Repo(path, search_parent_directories=True)
        repo.index.add(files_to_stage)
        return True

    def unstage_files(self, path: str, files_to_unstage: List[str]):
        """Unstages a list of files in the given repository."""
        repo = Repo(path, search_parent_directories=True)
        repo.index.reset(paths=files_to_unstage)
        return True
        
    def unstage_all_files(self, path: str):
        """Unstages all files in the repository."""
        repo = Repo(path, search_parent_directories=True)
        repo.index.reset()
        return True

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

class Worker(QRunnable):
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
            self.signals.result.emit(result)
        except Exception as e:
            self.signals.error.emit((type(e), e, traceback.format_exc()))
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
        self.local_git_repo = GitRepo()
        
        self.current_project_path = None
        self.stage_selected_btn = None
        self.stage_all_btn = None
        self.unstage_selected_btn = None
        self.unstage_all_btn = None
        self.unstaged_files_list = None
        self.staged_files_list = None
        self.refresh_local_btn = None
        self.generate_from_staged_btn = None
        self.generated_staged_commit_text = None

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
        self.local_page_btn = QPushButton("Generate from Local Changes")
        self.local_page_btn.setObjectName("navButton")
        self.local_page_btn.setCheckable(True)
        self.nav_button_layout.addWidget(self.analyze_page_btn)
        self.nav_button_layout.addWidget(self.diff_page_btn)
        self.nav_button_layout.addWidget(self.local_page_btn)
        self.nav_button_layout.addStretch()
        self.header_layout.addLayout(self.nav_button_layout)
        main_content_layout.addLayout(self.header_layout)

        self.stacked_widget = QStackedWidget()
        main_content_layout.addWidget(self.stacked_widget)

        self.analysis_page = self.create_analysis_page()
        self.stacked_widget.addWidget(self.analysis_page)
        self.diff_page = self.create_diff_page()
        self.stacked_widget.addWidget(self.diff_page)
        self.local_page = self.create_local_page()
        self.stacked_widget.addWidget(self.local_page)
        
        self.analyze_page_btn.clicked.connect(lambda: self.switch_page(0))
        self.diff_page_btn.clicked.connect(lambda: self.switch_page(1))
        self.local_page_btn.clicked.connect(lambda: self.switch_page(2))
        
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

    def create_local_page(self):
        page_widget = QWidget()
        layout = QVBoxLayout(page_widget)
        layout.setContentsMargins(0, 15, 0, 0)
        layout.setSpacing(20)

        local_group = QGroupBox("Manage & Generate from Local Repository")
        local_group_layout = QVBoxLayout(local_group)
        local_group_layout.setContentsMargins(20, 30, 20, 20)
        local_group_layout.setSpacing(15)

        folder_select_layout = QHBoxLayout()
        self.select_folder_btn = QPushButton("Select Project Folder")
        self.select_folder_btn.clicked.connect(self.select_project_folder)
        
        self.refresh_local_btn = QPushButton()
        self.refresh_local_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.refresh_local_btn.setToolTip("Refresh file status")
        self.refresh_local_btn.setObjectName("iconButton")
        self.refresh_local_btn.clicked.connect(self.refresh_local_repo_view)
        self.refresh_local_btn.setEnabled(False)

        self.selected_folder_label = QLabel("No folder selected.")
        self.selected_folder_label.setObjectName("folderLabel")
        folder_select_layout.addWidget(self.select_folder_btn)
        folder_select_layout.addWidget(self.refresh_local_btn)
        folder_select_layout.addWidget(self.selected_folder_label, 1)
        local_group_layout.addLayout(folder_select_layout)

        file_management_layout = QGridLayout()
        file_management_layout.setSpacing(15)

        self.unstaged_files_list = QListWidget()
        self.unstaged_files_list.setObjectName("filesList")
        
        self.staged_files_list = QListWidget()
        self.staged_files_list.setObjectName("filesList")

        staging_buttons_layout = QVBoxLayout()
        staging_buttons_layout.setSpacing(10)
        staging_buttons_layout.addStretch()
        
        self.stage_selected_btn = QPushButton("Stage →")
        self.stage_selected_btn.setObjectName("stageButton")
        self.stage_selected_btn.setToolTip("Stage the selected file")
        self.stage_selected_btn.clicked.connect(self.handle_stage_selected)
        
        self.stage_all_btn = QPushButton("Stage All →")
        self.stage_all_btn.setObjectName("stageAllButton")
        self.stage_all_btn.setToolTip("Stage all unstaged changes")
        self.stage_all_btn.clicked.connect(self.handle_stage_all)
        
        self.unstage_selected_btn = QPushButton("← Unstage")
        self.unstage_selected_btn.setObjectName("unstageButton")
        self.unstage_selected_btn.setToolTip("Unstage the selected file")
        self.unstage_selected_btn.clicked.connect(self.handle_unstage_selected)

        self.unstage_all_btn = QPushButton("← Unstage All")
        self.unstage_all_btn.setObjectName("unstageAllButton")
        self.unstage_all_btn.setToolTip("Unstage all staged changes")
        self.unstage_all_btn.clicked.connect(self.handle_unstage_all)

        staging_buttons_layout.addWidget(self.stage_selected_btn)
        staging_buttons_layout.addWidget(self.stage_all_btn)
        staging_buttons_layout.addSpacing(40)
        staging_buttons_layout.addWidget(self.unstage_selected_btn)
        staging_buttons_layout.addWidget(self.unstage_all_btn)
        staging_buttons_layout.addStretch()

        file_management_layout.addWidget(QLabel("Unstaged Changes:"), 0, 0)
        file_management_layout.addWidget(self.unstaged_files_list, 1, 0)
        file_management_layout.addLayout(staging_buttons_layout, 1, 1)
        file_management_layout.addWidget(QLabel("Staged Changes:"), 0, 2)
        file_management_layout.addWidget(self.staged_files_list, 1, 2)
        
        file_management_layout.setColumnStretch(0, 5)
        file_management_layout.setColumnStretch(1, 1)
        file_management_layout.setColumnStretch(2, 5)

        local_group_layout.addLayout(file_management_layout)
        
        # --- AI Commit Generation for Staged Files ---
        staged_commit_group = QGroupBox("AI Commit Generation for Staged Changes")
        staged_commit_layout = QVBoxLayout(staged_commit_group)
        staged_commit_layout.setContentsMargins(20, 30, 20, 20)
        staged_commit_layout.setSpacing(15)

        self.generated_staged_commit_text = QTextEdit()
        self.generated_staged_commit_text.setReadOnly(True)
        self.generated_staged_commit_text.setPlaceholderText("AI-generated commit message for all staged changes will appear here...")
        
        self.generate_from_staged_btn = QPushButton("Generate Commit from Staged")
        self.generate_from_staged_btn.setObjectName("generate_from_diff_btn") # Re-use style
        self.generate_from_staged_btn.clicked.connect(self.run_staged_changes_analysis)

        staged_commit_layout.addWidget(self.generated_staged_commit_text)
        staged_commit_layout.addWidget(self.generate_from_staged_btn)
        
        local_group_layout.addWidget(staged_commit_group)

        layout.addWidget(local_group)
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
            QLabel#folderLabel { color: #9CA3AF; font-style: italic; padding-left: 10px; }
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
            QPushButton#iconButton {
                background-color: transparent;
                border: 1px solid #4B5563;
                padding: 8px;
            }
            QPushButton#iconButton:hover {
                background-color: #374151;
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
            QListWidget, QListWidget#filesList { 
                outline: 0px; 
                border-radius: 8px;
            }
            QPushButton#stageButton {
                background-color: #3B82F6;
                color: #F9FAFB;
            }
            QPushButton#stageButton:hover {
                background-color: #60A5FA;
            }
            QPushButton#stageAllButton {
                background-color: transparent;
                border: 1px solid #3B82F6;
                color: #3B82F6;
            }
            QPushButton#stageAllButton:hover {
                background-color: #374151;
            }
            QPushButton#unstageButton {
                background-color: #F43F5E; /* Rose color */
                color: #F9FAFB;
            }
            QPushButton#unstageButton:hover {
                background-color: #FB7185;
            }
            QPushButton#unstageAllButton {
                background-color: transparent;
                border: 1px solid #F43F5E;
                color: #F43F5E;
            }
            QPushButton#unstageAllButton:hover {
                background-color: #374151;
            }
        """)

    def switch_page(self, index):
        self.stacked_widget.setCurrentIndex(index)
        self.analyze_page_btn.setChecked(index == 0)
        self.diff_page_btn.setChecked(index == 1)
        self.local_page_btn.setChecked(index == 2)

    def run_task_in_thread(self, task_function, on_result, on_error, *args, **kwargs):
        worker = Worker(task_function, *args, **kwargs)
        worker.signals.result.connect(on_result)
        worker.signals.error.connect(on_error)
        QThreadPool.globalInstance().start(worker)

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
        self.run_task_in_thread(self._task_connect_and_load_all, self._on_connect_and_load_all_result, self._on_task_error, token=token)

    def _task_connect_and_load_all(self, token):
        profile = GithubProfile()
        repo_handler = GithubRepo()
        connection_ok = profile.test_github_connection(token)
        if not connection_ok:
            raise ConnectionError("Token may be invalid or network issue.")
        owner = profile._set_owner_name(token)
        if not owner:
            raise ValueError("Failed to retrieve owner name.")
        repos = repo_handler.get_user_repositories(token, owner)
        avatar_data = None
        if profile.avatar:
            response = requests.get(profile.avatar, stream=True)
            response.raise_for_status()
            avatar_data = response.content
        return (token, owner, avatar_data, repos)

    def _on_connect_and_load_all_result(self, result):
        token, owner, avatar_data, repos = result
        self.token = token
        self.owner = owner
        if avatar_data:
            pixmap = QPixmap()
            pixmap.loadFromData(avatar_data)
            pixmap = pixmap.scaled(44, 44, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.avatar_label.setPixmap(pixmap)
        self.username_label.setText(owner)
        self.title_label.setVisible(False)
        self.profile_widget.setVisible(True)
        self.repo_combo.clear()
        if repos:
            self.repo_combo.addItem("Select a Repository...")
            for repo_dict in repos:
                for name, url in repo_dict.items():
                    self.repo_combo.addItem(name, userData=url)
        else:
            self.repo_combo.addItem("No repositories found.")
        self.update_connection_status("✅ Connected", True)
        self.analysis_workflow_group.setEnabled(True)
        self.write_commit_group.setEnabled(True)
        self.token_input.setEnabled(False)
        self.connect_btn.setVisible(False)
        self.disconnect_btn.setVisible(True)
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

    def reset_header(self):
        self.profile_widget.setVisible(False)
        self.title_label.setVisible(True)

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
        self.run_task_in_thread(self._task_load_commits, self._on_load_commits_result, self._on_task_error, repo=repo)

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
        self.run_task_in_thread(analyze_commit_list_with_ai, self._on_ai_analysis_result, self._on_task_error, commit_messages=items)

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
        self.run_task_in_thread(commit_best_practice, lambda result: self._on_single_analysis_result(result, message), self._on_task_error, commit_message=message)

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
        self.run_task_in_thread(write_commit_message, self._on_write_commit_result, self._on_task_error, message=desc)

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
        self.run_task_in_thread(write_commit_base_on_diff, self._on_diff_analysis_result, self._on_task_error, old_code=old_code, new_code=new_code)

    def _on_diff_analysis_result(self, result):
        self.generated_diff_commit_text.setText(result)
        self.generate_from_diff_btn.setEnabled(True)
        self.generate_from_diff_btn.setText("Generate Commit Message from Diff")

    def select_project_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Project Folder")
        if folder_path:
            self.current_project_path = folder_path
            self.selected_folder_label.setText(folder_path)
            self.refresh_local_btn.setEnabled(True)
            self.refresh_local_repo_view()

    def refresh_local_repo_view(self):
        if not self.current_project_path:
            return
        self.status_bar.showMessage("Refreshing local changes...", 2000)
        self.refresh_local_btn.setEnabled(False)
        self.run_task_in_thread(self.local_git_repo.get_status, self._on_get_local_changes_result, self._on_task_error, path=self.current_project_path)

    def handle_stage_selected(self):
        selected_items = self.unstaged_files_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select a file to stage.")
            return
        file_to_stage = selected_items[0].text().split('\t')[-1]
        self.run_stage_task([file_to_stage])

    def handle_stage_all(self):
        all_files = []
        for i in range(self.unstaged_files_list.count()):
            item_text = self.unstaged_files_list.item(i).text()
            if "No unstaged changes" not in item_text:
                 all_files.append(item_text.split('\t')[-1])
        if not all_files:
            QMessageBox.information(self, "No Changes", "There are no unstaged files to stage.")
            return
        self.run_stage_task(all_files)

    def run_stage_task(self, files: List[str]):
        self.status_bar.showMessage(f"Staging {len(files)} file(s)...", 3000)
        self.run_task_in_thread(
            self.local_git_repo.stage_files,
            self._on_stage_complete,
            self._on_task_error,
            path=self.current_project_path,
            files_to_stage=files
        )

    def _on_stage_complete(self, result):
        self.status_bar.showMessage("Staging successful!", 2000)
        self.refresh_local_repo_view()

    def handle_unstage_selected(self):
        selected_items = self.staged_files_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select a file to unstage.")
            return
        file_to_unstage = selected_items[0].text().split('\t')[-1]
        self.run_unstage_task([file_to_unstage])

    def handle_unstage_all(self):
        if self.staged_files_list.count() == 0 or "No staged changes" in self.staged_files_list.item(0).text():
            QMessageBox.information(self, "No Changes", "There are no staged files to unstage.")
            return
        
        self.status_bar.showMessage("Unstaging all files...", 3000)
        self.run_task_in_thread(
            self.local_git_repo.unstage_all_files,
            self._on_unstage_complete,
            self._on_task_error,
            path=self.current_project_path
        )

    def run_unstage_task(self, files: List[str]):
        self.status_bar.showMessage(f"Unstaging {len(files)} file(s)...", 3000)
        self.run_task_in_thread(
            self.local_git_repo.unstage_files,
            self._on_unstage_complete,
            self._on_task_error,
            path=self.current_project_path,
            files_to_unstage=files
        )

    def _on_unstage_complete(self, result):
        self.status_bar.showMessage("Unstaging successful!", 2000)
        self.refresh_local_repo_view()

    def run_staged_changes_analysis(self):
        """Handles the full workflow for generating a commit from staged files."""
        if not self.local_git_repo.staged_diffs:
            QMessageBox.information(self, "No Staged Changes", "There are no changes in the staging area to analyze.")
            return
        
        self.generate_from_staged_btn.setEnabled(False)
        self.generate_from_staged_btn.setText("Analyzing...")
        self.run_task_in_thread(self._task_generate_from_staged, self._on_staged_analysis_result, self._on_task_error)

    def _task_generate_from_staged(self):
        """Background task to combine blobs and call the AI."""
        combined_blobs = self.local_git_repo.combine_all_blobs()
        if not combined_blobs:
            raise ValueError("Could not extract changes from staged files.")
        
        commit_message = write_commits_for_staged_changes(combined_blobs)
        return commit_message

    def _on_staged_analysis_result(self, result):
        self.generated_staged_commit_text.setText(result)
        self.generate_from_staged_btn.setEnabled(True)
        self.generate_from_staged_btn.setText("Generate Commit from Staged")

    def _on_get_local_changes_result(self, result: Dict[str, list]):
        self.refresh_local_btn.setEnabled(True)
        self.staged_files_list.clear()
        self.unstaged_files_list.clear()

        staged_files = result.get("staged", [])
        if staged_files:
            for file_info in staged_files:
                display_text = f"{file_info['change_type']}\t{file_info['file_name']}"
                self.staged_files_list.addItem(display_text)
        else:
            self.staged_files_list.addItem("No staged changes.")

        unstaged_files = result.get("unstaged", [])
        if unstaged_files:
            for file_info in unstaged_files:
                display_text = f"{file_info['change_type']}\t{file_info['file_name']}"
                self.unstaged_files_list.addItem(display_text)
        else:
            self.unstaged_files_list.addItem("No unstaged changes.")

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
        if self.refresh_local_btn:
            self.refresh_local_btn.setEnabled(True)
        if self.generate_from_staged_btn:
            self.generate_from_staged_btn.setEnabled(True)
            self.generate_from_staged_btn.setText("Generate Commit from Staged")

    def closeEvent(self, event):
        QThreadPool.globalInstance().waitForDone()
        event.accept()

if __name__ == '__main__':
    if not config("GITHUB_ACCESS_TOKEN", default=None):
        print("INFO: .env file with GITHUB_ACCESS_TOKEN not found. Starting with manual input.")

    app = QApplication(sys.argv)
    window = GitAnalyzerGUI()
    window.show()
    sys.exit(app.exec())
