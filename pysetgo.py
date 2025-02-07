import sys
import os
import platform
import subprocess
import shutil
import time
import ctypes
import socket
import atexit
import psutil
from PyQt6 import QtWidgets, QtCore


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def is_connected():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        return False

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

        if self.install_extensions:
            self.update_signal.emit("--------------------")
            self.update_signal.emit("Installing VS Code extensions...")
            self.update_signal.emit("--------------------")
            self.install_vscode_extensions()


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
            startupinfo = None
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW 
            
            if platform.system() != "Windows":
                cmd.insert(0, "sudo")  

            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE if capture_output else subprocess.DEVNULL,
                stderr=subprocess.PIPE if capture_output else subprocess.DEVNULL,
                text=True,
                check=True,
                stdin=subprocess.PIPE if platform.system() != "Windows" else subprocess.DEVNULL,
                input=f"{self.password}\n" if platform.system() != "Windows" else None,
                startupinfo=startupinfo 
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

            total_libs = len(libraries)
            progress_per_lib = 30 // total_libs 

            self.execute_command([python_path, "-m", "pip", "install", "--upgrade", "pip"], capture_output=False)
            self.increment_progress(5)  

            for index, lib in enumerate(libraries, start=1):
                self.update_signal.emit(f"Installing {lib}...")
                self.execute_command([python_path, "-m", "pip", "install", lib], capture_output=False)

                version_output = self.execute_command([python_path, "-m", "pip", "show", lib])
                if version_output:
                    for line in version_output.split("\n"):
                        if line.startswith("Version:"):
                            installed_versions[lib] = line.split(":")[1].strip()

                self.increment_progress(progress_per_lib) 
                self.msleep(100)  

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

            total_exts = len(extensions)
            progress_per_ext = 20 // total_exts 

            installed = []
            skipped = []

            for ext in extensions:
                if ext in installed_extensions:
                    skipped.append(ext)
                else:
                    self.execute_command([code_path, "--install-extension", ext, "--force"], capture_output=False)
                    installed.append(ext)

                self.increment_progress(progress_per_ext) 
                self.msleep(100)  

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

        if platform.system() == "Windows":
            self.password_input.setVisible(False)

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
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)


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
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.log_output)
        layout.addSpacing(10)
        layout.addWidget(self.close_button)

        self.setLayout(layout)


    def elevate_admin_windows(self, password):
        try:
            result = subprocess.run(
                ["runas", "/user:Administrator", "cmd.exe", "/c", "echo Admin Test"],
                input=f"{password}\n",
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            return result.returncode == 0
        except Exception as e:
            self.log_output.append(f"[ERROR] Windows admin elevation failed: {str(e)}")
            return False

    def elevate_admin_linux(self, password):
        try:
            result = subprocess.run(
                ["sudo", "-S", "echo", "Admin Test"],
                input=f"{password}\n",
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            return result.returncode == 0
        except Exception as e:
            self.log_output.append(f"[ERROR] Linux/macOS admin elevation failed: {str(e)}")
            return False


    def toggle_install_button(self):
        self.install_button.setEnabled(self.terms_checkbox.isChecked())

    def start_installation(self):
        self.log_output.clear()

        if not is_connected():
            self.log_output.append("[ERROR] No internet connection detected.\n"
                                "Please check your connection and try again.")
            return  

        if platform.system() == "Windows" and not is_admin():
            self.log_output.append("[INFO] Restarting with admin privileges...")
            QtWidgets.QMessageBox.information(
                self, "Admin Required", "The installer needs admin rights to proceed.\n"
                                        "Click OK to restart with admin privileges.")

            subprocess.run(["powershell", "Start-Process", "pysetgo.exe", "-Verb", "RunAs"])
            QtWidgets.QApplication.quit()  
            return

        admin_password = self.password_input.text().strip()
        if platform.system() != "Windows" and not admin_password:
            self.log_output.append("[ERROR] Admin password is required to proceed.")
            return

        if platform.system() != "Windows":
            success = self.elevate_admin_linux(admin_password)
            if not success:
                self.log_output.append("[ERROR] Failed to gain admin privileges.\n"
                                    "Please check your password and try again.")
                return 

        self.cancel_button.setVisible(True)
        self.installer_thread = InstallerThread(
            self.install_extensions_checkbox.isChecked(),
            self.install_libraries_checkbox.isChecked(),
            admin_password 
        )
        self.installer_thread.update_signal.connect(self.update_progress)
        self.installer_thread.progress_signal.connect(self.update_progress_bar)
        self.installer_thread.finished_signal.connect(self.show_completion_buttons)
        self.installer_thread.start()

    

    def cancel_installation(self):
        reply = QtWidgets.QMessageBox.question(
            self, "Cancel Installation",
            "Are you sure you want to cancel? This may leave incomplete installations.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
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


    def update_progress(self, message):
        self.log_output.append(message)

    def show_completion_buttons(self):
        self.cancel_button.setVisible(False)

    def close_application(self):
        self.close()


if __name__ == "__main__":
    import tempfile
    
    LOCK_FILE = os.path.join(tempfile.gettempdir(), "pysetgo.lock")


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
