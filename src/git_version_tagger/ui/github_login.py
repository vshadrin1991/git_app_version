"""Log in with `gh auth login --web`: show gh's one-time code, open the device page, then set up git."""
from __future__ import annotations

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QGuiApplication
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from ..github_auth import (
    DevicePrompt,
    ascii_host,
    gh_environment,
    is_device_page_of,
    login_arguments,
    parse_device_prompt,
    setup_git,
)
from .style import plain
from .worker import run_in_background


class GitHubLoginDialog(QDialog):
    """Starts gh when created; accepted once gh is logged in and git uses that login."""

    def __init__(self, gh: str, host: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Log in to {ascii_host(host)}")
        self.resize(520, 360)
        self.gh = gh
        self.host = host
        self.prompt: DevicePrompt | None = None
        self._raw = b""

        self.status = plain(QLabel("Starting gh auth login…"))
        self.status.setWordWrap(True)
        self.code = QLabel()
        font = QFont(self.code.font())
        font.setPointSize(22)
        font.setBold(True)
        self.code.setFont(font)
        self.code.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.open_button = QPushButton("Open GitHub in the browser")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(lambda _checked=False: self._open_device_page())
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.status)
        layout.addWidget(self.code, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.open_button, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.log)
        layout.addWidget(self.buttons)

        self.process = QProcess(self)
        environment = QProcessEnvironment()
        for key, value in gh_environment().items():
            environment.insert(key, value)
        self.process.setProcessEnvironment(environment)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        # No terminal and no input: gh prints the code and URL instead of asking to press Enter.
        self.process.setStandardInputFile(QProcess.nullDevice())
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.finished.connect(self._on_finished)
        self.process.errorOccurred.connect(self._on_error)
        self.process.start(gh, login_arguments(host))

    def _read_output(self) -> None:
        self._raw += self.process.readAllStandardOutput().data()
        output = self._raw.decode("utf-8", "replace")
        self.log.setPlainText(output)
        prompt = parse_device_prompt(output, self.host)
        if prompt is None or prompt == self.prompt:
            return
        if self.prompt is None:
            QGuiApplication.clipboard().setText(prompt.code)
        self.prompt = prompt
        self.code.setText(prompt.code)
        on_host = is_device_page_of(prompt.url, self.host)
        if on_host:
            self.status.setText(
                f"Open {prompt.url}, sign in and enter this code (it is already on the clipboard). "
                "This window closes by itself when GitHub confirms."
            )
        else:
            self.status.setText(
                f"gh asked to open {prompt.url}, which is not on {ascii_host(self.host)}, so this window "
                "will not open it. Enter the code only on a page you trust."
            )
        self.open_button.setEnabled(on_host)

    def _open_device_page(self) -> None:
        if self.prompt is not None and is_device_page_of(self.prompt.url, self.host):
            QDesktopServices.openUrl(QUrl(self.prompt.url))

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self._read_output()  # whatever gh printed last
        if exit_status != QProcess.ExitStatus.NormalExit or exit_code != 0:
            self._fail(f"gh auth login failed (exit code {exit_code}). Its output is below.")
            return
        self.status.setText("Logged in. Setting up git to use this login…")
        self.open_button.setEnabled(False)
        self.buttons.setEnabled(False)  # setup-git takes a moment; closing now would skip it
        run_in_background(lambda: setup_git(self.gh, self.host), lambda _result: self.accept(), self._on_setup_failed)

    def _on_setup_failed(self, exc: Exception) -> None:
        self.buttons.setEnabled(True)
        self._fail(str(exc))

    def _on_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self._fail(f"Cannot run {self.gh}: {self.process.errorString()}")

    def _fail(self, message: str) -> None:
        self.status.setText(message)
        self.open_button.setEnabled(False)
        self.buttons.setStandardButtons(QDialogButtonBox.StandardButton.Close)

    def reject(self) -> None:
        """Cancel, Close, Esc or the window's close button: stop gh so no login keeps running unseen."""
        if not self.buttons.isEnabled():
            return  # setup-git is running; the window closes by itself in a moment
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(3000)
        super().reject()
