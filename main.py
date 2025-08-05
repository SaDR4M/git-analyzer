from github.gui import QApplication , GitAnalyzerGUI
import sys

def main():
    """Main function to run the application."""
    app = QApplication(sys.argv)
    window = GitAnalyzerGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
    # from github.handler import GitRepo
    # git = GitRepo("git-analyzer" , 'https://github.com/SaDR4M/git-analyzer.git')
    # git.clone_repo()