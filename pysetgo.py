import sys
import os
import platform
import subprocess
import shutil
import time
from PyQt6 import QtWidgets, QtCore


class InstallerThread(QtCore.QThread):
    update_signal = QtCore.pyqtSignal(str)
    progress_signal = QtCore.pyqtSignal(int)
    finished_signal = QtCore.pyqtSignal()

    def __init__(self, install_extensions, install_libraries, password):
        super().__init__()
        self.install_extensions = install_extensions
        self.install_libraries = install_libraries
        self.password = password
        self.progress = 0
        self.total_steps = 100
        self.current_step = 0
        self.canceled = False

    def run(self):
        self.update_signal.emit("--------------------")
        self.update_signal.emit("Starting installation...")
        self.update_signal.emit("--------------------")
        self.increment_progress(5)

        self.update_signal.emit("Checking Python installation...")
        time.sleep(0.5)
        if not self.is_python_installed():
            self.update_signal.emit("Installing Python...")
            self.install_python()
        else:
            python_version = self.execute_command(["python3", "--version"])
            self.update_signal.emit(f"Python is already installed.\nInstalled version: {python_version}")

        self.increment_progress(20)

        self.update_signal.emit("Checking VS Code installation...")
        time.sleep(0.5)
        if not self.is_vscode_installed():
            self.update_signal.emit("Installing VS Code...")
            self.install_vscode()
        else:
            self.update_signal.emit("VS Code is already installed.")

        self.increment_progress(25)

        if self.install_libraries:
            self.update_signal.emit("--------------------")
            self.update_signal.emit("Installing Python libraries...")
            self.update_signal.emit("--------------------")
            self.install_python_libraries()
            self.increment_progress(30)

        if self.install_extensions:
            self.update_signal.emit("--------------------")
            self.update_signal.emit("Installing VS Code extensions...")
            self.update_signal.emit("--------------------")
            self.install_vscode_extensions()
            self.increment_progress(20)


        self.update_signal.emit("--------------------")
        self.update_signal.emit("Installation completed! You can now safely close this program.")
        self.update_signal.emit("--------------------")
        self.progress_signal.emit(100)
        self.finished_signal.emit()

    def abort_installation(self):
        """Handle installation cancellation"""
        self.update_signal.emit("Installation Canceled!")
        self.progress_signal.emit(0)
        self.finished_signal.emit()

    def execute_command(self, cmd, capture_output=True):
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE if capture_output else None,
                stderr=subprocess.PIPE if capture_output else None,
                text=True,
                check=True,
                stdin=subprocess.DEVNULL
            )
            return result.stdout.strip() if capture_output and result.stdout else None
        except subprocess.CalledProcessError as e:
            return f"Error: {e.stderr.strip()}" if capture_output else None

    def get_command_path(self, command):
        result = shutil.which(command)
        if result:
            return result
        if command == "brew":
            for path in ["/opt/homebrew/bin/brew", "/usr/local/bin/brew"]:
                if os.path.exists(path):
                    return path
        return None

    def increment_progress(self, steps=1):
        for _ in range(steps):
            self.current_step += 1
            progress = min(int((self.current_step / self.total_steps) * 100), 100)
            self.progress_signal.emit(progress)
            time.sleep(0.05)  

    def is_python_installed(self):
        return shutil.which("python3") is not None

    def is_vscode_installed(self):
        return self.get_command_path("code") is not None

    def install_python(self):
        brew_path = self.get_command_path("brew")
        if brew_path:
            self.execute_command([brew_path, "install", "python"], capture_output=False)
            self.update_signal.emit("Python installed successfully.")
        self.increment_progress(5)

    def install_vscode(self):
        brew_path = self.get_command_path("brew")
        if platform.system() == "Darwin" and brew_path:
            self.execute_command([brew_path, "install", "--cask", "visual-studio-code"], capture_output=False)
        elif platform.system() == "Linux":
            self.execute_command(["sudo", "apt", "install", "code", "-y"], capture_output=False)
        elif platform.system() == "Windows":
            self.execute_command(["choco", "install", "vscode"], capture_output=False)
        else:
            self.update_signal.emit("Error: Unsupported OS for automated VS Code installation.")
        self.increment_progress(5)

    def install_python_libraries(self):
        python_path = self.get_command_path("python3")
        if python_path:
            libraries = ["numpy", "pandas", "matplotlib", "requests", "flask", "pytest"]
            installed_versions = {}

            self.execute_command([python_path, "-m", "pip", "install", "--upgrade", "pip"], capture_output=False)
            for lib in libraries:
                self.execute_command([python_path, "-m", "pip", "install", lib], capture_output=False)
                version_output = self.execute_command([python_path, "-m", "pip", "show", lib])
                if version_output:
                    for line in version_output.split("\n"):
                        if line.startswith("Version:"):
                            installed_versions[lib] = line.split(":")[1].strip()

            summary = "\n".join([f"{pkg}: {ver}" for pkg, ver in installed_versions.items()])
            self.update_signal.emit(f"Python libraries installation completed.\nInstalled versions:\n{summary}")

    def install_vscode_extensions(self):
        code_path = self.get_command_path("code")
        if code_path:
            extensions = [
                "ms-python.python", "ms-python.vscode-pylance", "ms-toolsai.jupyter",
                "formulahendry.code-runner", "esbenp.prettier-vscode"
            ]
            result = self.execute_command([code_path, "--list-extensions"])
            installed_extensions = result.split("\n") if result else []

            installed = []
            skipped = []

            for ext in extensions:
                if ext in installed_extensions:
                    skipped.append(ext)
                else:
                    self.execute_command([code_path, "--install-extension", ext, "--force"], capture_output=False)
                    installed.append(ext)

            summary = (
                f"VS Code extensions installation completed.\n"
                f"Installed: {', '.join(installed) if installed else 'None'}\n"
                f"Already installed: {', '.join(skipped)}"
            )
            self.update_signal.emit(summary)


class InstallerApp(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PySetGo Installer")
        self.setGeometry(100, 100, 500, 550)
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout()

        # Header
        self.header = QtWidgets.QLabel("<h1>PySetGo</h1>")
        self.header.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        # Description
        self.description = QtWidgets.QLabel(
            "PySetGo installs the latest version of Python and VS Code, the most popular IDE. "
            "It also includes optional packages for Python and recommended VS Code extensions, "
            "commonly used in Python development."
        )
        self.description.setWordWrap(True)
        self.description.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        # Checkboxes
        self.install_extensions_checkbox = QtWidgets.QCheckBox("Install VS Code Extensions (Recommended)")
        self.install_extensions_checkbox.setChecked(True)
        self.install_libraries_checkbox = QtWidgets.QCheckBox("Install Python Libraries (Recommended)")
        self.install_libraries_checkbox.setChecked(True)

        # Password Input
        self.password_input = QtWidgets.QLineEdit()
        self.password_input.setPlaceholderText("System password required to install Python and VS Code")
        self.password_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)

        # Terms and Conditions
        self.terms_checkbox = QtWidgets.QCheckBox("I agree to the Terms and Conditions")
        self.terms_checkbox.stateChanged.connect(self.toggle_install_button)

        # Install/Cancel Buttons Layout
        button_layout = QtWidgets.QHBoxLayout()
        self.install_button = QtWidgets.QPushButton("Install")
        self.install_button.setEnabled(False)
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.setStyleSheet("background-color: #ffcccc; color: black; border-radius: 3px;")
        self.cancel_button.setVisible(False)
        self.install_button.clicked.connect(self.start_installation)
        self.cancel_button.clicked.connect(self.cancel_installation)
        button_layout.addWidget(self.install_button)
        button_layout.addWidget(self.cancel_button)

        # Progress Bar Layout
        progress_layout = QtWidgets.QHBoxLayout()
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_label = QtWidgets.QLabel("0%")
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)

        # Log Output
        self.log_output = QtWidgets.QTextEdit()
        self.log_output.setReadOnly(True)

        # Close Button
        self.close_button = QtWidgets.QPushButton("Close")
        self.close_button.setStyleSheet("background-color: #636363; border-radius: 3px;")
        self.close_button.clicked.connect(self.close_application)

        # Layout Arrangement
        layout.addWidget(self.header)
        layout.addSpacing(20) 
        layout.addWidget(self.description)
        layout.addSpacing(20)
        layout.addWidget(self.install_extensions_checkbox)
        layout.addWidget(self.install_libraries_checkbox)
        layout.addSpacing(10)
        layout.addWidget(self.password_input)
        layout.addSpacing(10)
        layout.addWidget(self.terms_checkbox)
        layout.addLayout(button_layout)
        layout.addLayout(progress_layout)
        layout.addWidget(self.log_output)
        layout.addSpacing(10)
        layout.addWidget(self.close_button)

        self.setLayout(layout)


    def toggle_install_button(self):
        self.install_button.setEnabled(self.terms_checkbox.isChecked())

    def start_installation(self):
        self.cancel_button.setVisible(True)
        self.installer_thread = InstallerThread(
            self.install_extensions_checkbox.isChecked(),
            self.install_libraries_checkbox.isChecked(),
            self.password_input.text()
        )
        self.installer_thread.update_signal.connect(self.update_progress)
        self.installer_thread.progress_signal.connect(self.update_progress_bar)
        self.installer_thread.finished_signal.connect(self.show_completion_buttons)
        self.installer_thread.start()
    
    def cancel_installation(self):
        if hasattr(self, "installer_thread") and self.installer_thread.isRunning():
            self.installer_thread.update_signal.emit("--------------------")
            self.installer_thread.update_signal.emit("Installation Canceled!")
            self.installer_thread.update_signal.emit("--------------------")
            self.installer_thread.progress_signal.emit(0)
            
            self.installer_thread.terminate()  
            self.installer_thread.wait()  

            self.install_button.setEnabled(True) 
            self.cancel_button.setVisible(False)  


    def update_progress_bar(self, value):
        self.progress_bar.setValue(value)
        self.progress_label.setText(f"{value}%")

    def update_progress(self, message):
        self.log_output.append(message)

    def show_completion_buttons(self):
        self.cancel_button.setVisible(False)

    def close_application(self):
        self.close()


if __name__ == "__main__":
    import atexit
    import psutil 

    LOCK_FILE = "/tmp/pysetgo.lock"

    def is_pysetgo_running(pid):
        try:
            for proc in psutil.process_iter(attrs=['pid', 'name', 'cmdline']):
                if proc.info['pid'] == pid:
                    if proc.info['cmdline'] and 'pysetgo.py' in ' '.join(proc.info['cmdline']):
                        return True 
            return False
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False

    if os.path.exists(LOCK_FILE):
        with open(LOCK_FILE, "r") as lock:
            try:
                existing_pid = int(lock.read().strip())
                if is_pysetgo_running(existing_pid):
                    print(
                        f"Another instance of PySetGo (PID {existing_pid}) is already running. Exiting...")
                    sys.exit(1)
                else:
                    print("Stale lock file found. Removing it...")
                    os.remove(LOCK_FILE)
            except (ValueError, FileNotFoundError):
                os.remove(LOCK_FILE) 

    with open(LOCK_FILE, "w") as lock:
        lock.write(str(os.getpid()))

    def release_lock():
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)

    atexit.register(release_lock)

    app = QtWidgets.QApplication(sys.argv)
    installer = InstallerApp()
    installer.show()
    sys.exit(app.exec())
