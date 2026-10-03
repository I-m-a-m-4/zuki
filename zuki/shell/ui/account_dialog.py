"""
Account sign-in dialog — the one door into Zuki.

Every user needs an account before she'll talk to Claude: the app signs the
request with the account token, and the Zuki server (which holds the Claude
key) answers. This dialog is shown modal at startup when nobody is signed in,
and from the tray ("Account…") any time after.

Two shapes:
  * gate mode   (allow_skip=False) — startup with no local key to fall back
    on. Sign in / create an account, or quit. No quiet way past.
  * soft mode   (allow_skip=True)  — a local ANTHROPIC_API_KEY exists, so
    "continue without an account" is offered.

Firebase does ALL auth; nothing here handles passwords beyond handing them to
Firebase over TLS. The session is cached by `account.py`.
"""

from __future__ import annotations

import threading

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QVBoxLayout,
)

_QSS = """
QDialog { background: #0e1014; color: #e8eaed; }
QLabel  { color: #e8eaed; }
QLabel#title { font-size: 20px; font-weight: 700; }
QLabel#subtitle { color: #a0a3a8; font-size: 13px; }
QLabel#status { color: #c8cbd0; font-size: 13px; }
QLabel#hint { color: #6a6d73; font-size: 11px; }
QLineEdit {
    background: #1a1d22; border: 1px solid #2a2d33;
    border-radius: 6px; padding: 8px; color: #e8eaed;
}
QLineEdit:focus { border-color: #2f7fff; }
QCheckBox { color: #a0a3a8; font-size: 12px; }
QPushButton {
    background: #1f6feb; color: white; border: none;
    padding: 10px 18px; border-radius: 8px;
    font-weight: 600; font-size: 13px;
}
QPushButton:hover  { background: #2f7fff; }
QPushButton:disabled { background: #333; color: #888; }
QPushButton#secondary {
    background: transparent; color: #a0a3a8;
    border: 1px solid #2a2d33;
}
QPushButton#secondary:hover { color: #e8eaed; border-color: #444; }
QPushButton#danger {
    background: transparent; color: #e08a8a;
    border: 1px solid #5a3131;
}
QPushButton#danger:hover { color: #ffb0b0; border-color: #8a4141; }
"""


class AccountDialog(QDialog):
    """Sign in / create account / sign out. Modal in gate mode, modeless in
    soft mode. `continue_allowed` says whether Zuki may proceed without an
    account (only ever true when allow_skip was given)."""

    status_signal   = pyqtSignal(str)          # progress line from the worker
    auth_done       = pyqtSignal(bool, str)    # (ok, error message)
    account_changed = pyqtSignal()             # signed in or out — UI refresh

    def __init__(self, parent=None, allow_skip: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Zuki — Account")
        self.setStyleSheet(_QSS)
        self.setMinimumWidth(440)

        self._allow_skip = allow_skip
        self._busy = False
        self._create_mode = False
        self.continue_allowed = False

        if not allow_skip:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        self._body = QVBoxLayout(self)
        self._body.setContentsMargins(32, 26, 32, 22)
        self._body.setSpacing(12)
        self._body.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)

        # The worker thread only ever talks to the UI through these.
        self.auth_done.connect(self._on_auth_done)
        self.status_signal.connect(self._set_status)

        if cfg_signed_in():
            self.continue_allowed = True
            self._build_signed_in()
        else:
            self._build_auth()

    # ── views ────────────────────────────────────────────────────────────────

    def _clear(self):
        while self._body.count():
            item = self._body.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            elif item.layout() is not None:
                self._drain(item.layout())

    def _drain(self, lay):
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            elif item.layout() is not None:
                self._drain(item.layout())

    def _build_auth(self):
        self._clear()
        b = self._body

        title = QLabel("Welcome to Zuki")
        title.setObjectName("title")
        b.addWidget(title)

        sub = QLabel(
            "She runs on a Zuki account — it keeps your Claude access safe "
            "and free. Sign in, or create one in a few seconds."
        )
        sub.setObjectName("subtitle")
        sub.setWordWrap(True)
        b.addWidget(sub)

        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("Email")
        b.addWidget(self.email_edit)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Name (optional)")
        self.name_edit.hide()
        b.addWidget(self.name_edit)

        self.pass_edit = QLineEdit()
        self.pass_edit.setPlaceholderText("Password")
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_edit.returnPressed.connect(self._on_primary)
        b.addWidget(self.pass_edit)

        self.create_toggle = QCheckBox("Create a new account")
        self.create_toggle.toggled.connect(self._on_mode_toggled)
        b.addWidget(self.create_toggle)

        self.status = QLabel("")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        b.addWidget(self.status)

        hint = QLabel("Firebase handles sign-in; Zuki never sees your password.")
        hint.setObjectName("hint")
        b.addWidget(hint)

        row = QHBoxLayout()
        row.setSpacing(10)
        if self._allow_skip:
            skip = QPushButton("Continue without an account")
            skip.setObjectName("secondary")
            skip.clicked.connect(self._on_skip)
            row.addWidget(skip)
        else:
            quit_btn = QPushButton("Quit Zuki")
            quit_btn.setObjectName("secondary")
            quit_btn.clicked.connect(self.reject)
            row.addWidget(quit_btn)
        row.addStretch(1)

        self.primary_btn = QPushButton("Sign in")
        self.primary_btn.setDefault(True)
        self.primary_btn.clicked.connect(self._on_primary)
        row.addWidget(self.primary_btn)
        b.addLayout(row)

        self.email_edit.setFocus()

    def _build_signed_in(self):
        self._clear()
        b = self._body

        user = current_user() or {}
        title = QLabel("You're signed in")
        title.setObjectName("title")
        b.addWidget(title)

        sub = QLabel(
            f"<b>{_esc(user.get('email') or user.get('name') or 'Zuki user')}</b>"
            + (f" — {_esc(user.get('name'))}" if user.get("name") else "")
        )
        sub.setObjectName("subtitle")
        sub.setWordWrap(True)
        b.addWidget(sub)

        msg = QLabel("Claude requests go through your Zuki account. "
                     "Sign out to use a different one.")
        msg.setObjectName("status")
        msg.setWordWrap(True)
        b.addWidget(msg)

        row = QHBoxLayout()
        row.setSpacing(10)
        out_btn = QPushButton("Sign out")
        out_btn.setObjectName("danger")
        out_btn.clicked.connect(self._on_sign_out)
        row.addWidget(out_btn)
        row.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        row.addWidget(close_btn)
        b.addLayout(row)

    # ── interactions ─────────────────────────────────────────────────────────

    def _set_status(self, text: str):
        try:
            self.status.setText(text)
        except (AttributeError, RuntimeError):
            pass                       # label rebuilt mid-flight; next view is fresh

    def _on_mode_toggled(self, checked: bool):
        self._create_mode = bool(checked)
        self.name_edit.setVisible(self._create_mode)
        self.primary_btn.setText("Create account" if self._create_mode else "Sign in")
        self.status.setText("")

    def _on_primary(self):
        if self._busy:
            return
        email = self.email_edit.text().strip()
        password = self.pass_edit.text()
        name = self.name_edit.text().strip()
        if not email:
            self.status.setText("⚠️ Enter your email address.")
            self.email_edit.setFocus()
            return
        if not password:
            self.status.setText("⚠️ Enter a password.")
            self.pass_edit.setFocus()
            return
        if self._create_mode and len(password) < 6:
            self.status.setText("⚠️ Password must be at least 6 characters.")
            return

        self._busy = True
        self.primary_btn.setEnabled(False)
        self.status_signal.emit("Creating your account…" if self._create_mode
                                else "Signing in…")

        create = self._create_mode

        def _worker():
            try:
                import account
                if create:
                    account.sign_up(email, password, name)
                else:
                    account.sign_in(email, password)
            except Exception as e:
                self.auth_done.emit(False, str(e) or "Sign-in failed.")
            else:
                self.auth_done.emit(True, "")

        threading.Thread(target=_worker, daemon=True).start()

    def _on_auth_done(self, ok: bool, err: str):
        self._busy = False
        self.primary_btn.setEnabled(True)
        if not ok:
            self.status.setText(f"⚠️ {err}")
            return
        # Freed the stale credential path: everything that talks to Claude
        # must pick up the account token now.
        try:
            from ai import client_factory
            client_factory.invalidate(pool=True)
        except Exception:
            pass
        self.continue_allowed = True
        self.account_changed.emit()
        self.accept()

    def _on_sign_out(self):
        try:
            import account
            account.sign_out()
        except Exception:
            pass
        self.continue_allowed = False
        self.account_changed.emit()
        self._build_auth()

    def _on_skip(self):
        self.continue_allowed = True
        self.accept()

    def reject(self):
        # Window ✕ / Esc in soft mode = skip; in gate mode it stays blocked
        # (continue_allowed stays False and main.py quits).
        if self._allow_skip:
            self.continue_allowed = True
        super().reject()


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def cfg_signed_in() -> bool:
    try:
        import account
        return account.is_signed_in()
    except Exception:
        return False


def current_user() -> dict | None:
    try:
        import account
        return account.current_user()
    except Exception:
        return None


# ── module-level entry points ────────────────────────────────────────────────

def prompt_sign_in(parent=None, allow_skip: bool = False) -> bool:
    """Modal gate for startup. Returns True when Zuki may proceed:
    signed in — or the user chose to continue without an account (soft mode).
    In gate mode an unanswered dialog returns False → caller should quit."""
    if cfg_signed_in():
        return True
    dlg = AccountDialog(parent=parent, allow_skip=allow_skip)
    dlg.exec()
    return dlg.continue_allowed


_keepalive: list = []


def open_account_dialog(parent=None, on_changed=None) -> AccountDialog:
    """Modeless dialog for the tray — sign in, switch account, or sign out."""
    dlg = AccountDialog(parent=parent, allow_skip=True)
    if on_changed is not None:
        dlg.account_changed.connect(on_changed)
    _keepalive.append(dlg)
    dlg.finished.connect(
        lambda _r, d=dlg: _keepalive.remove(d) if d in _keepalive else None)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    return dlg
