from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import threading
from dataclasses import dataclass
from typing import BinaryIO, Sequence


DEFAULT_OUTPUT_LIMIT_BYTES = 1_000_000


@dataclass(frozen=True)
class ToolHealth:
    binary: str
    available: bool
    path: str | None
    version: str | None
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "binary": self.binary,
            "available": self.available,
            "path": self.path,
            "version": self.version,
            "error": self.error,
        }


@dataclass(frozen=True)
class ExecutionOutput:
    stdout: str
    stderr: str
    exit_code: int | None
    timed_out: bool
    output_truncated: bool


def inspect_tool(
    command: Sequence[str],
    *,
    version_command: Sequence[str] | None = None,
    timeout: int = 10,
) -> ToolHealth:
    if not command:
        return ToolHealth(binary="", available=False, path=None, version=None, error="empty command")

    binary = str(command[0])
    path = shutil.which(binary)
    if path is None:
        return ToolHealth(
            binary=binary,
            available=False,
            path=None,
            version=None,
            error=f"required executable is not on PATH: {binary}",
        )

    probe = list(version_command or [binary, "-version"])
    try:
        completed = subprocess.run(
            probe,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=execution_environment(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ToolHealth(binary=binary, available=True, path=path, version=None, error=str(exc))

    output = (completed.stdout or completed.stderr).strip().splitlines()
    version = extract_version(output)
    return ToolHealth(binary=binary, available=True, path=path, version=version)


def execution_environment() -> dict[str, str]:
    allowed = ("HOME", "LANG", "LC_ALL", "PATH", "SSL_CERT_FILE", "SSL_CERT_DIR", "TMPDIR")
    return {key: os.environ[key] for key in allowed if key in os.environ}


def extract_version(lines: Sequence[str]) -> str | None:
    ansi = re.compile(r"\x1b\[[0-9;]*m")
    cleaned = [ansi.sub("", line).strip() for line in lines]
    for line in cleaned:
        if re.search(r"\bversion\b", line, re.IGNORECASE) and re.search(r"v?\d+\.\d+", line):
            return line
    return next((line for line in cleaned if line), None)


def run_command(
    command: Sequence[str],
    *,
    timeout: int,
    max_output_bytes: int = DEFAULT_OUTPUT_LIMIT_BYTES,
) -> ExecutionOutput:
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if max_output_bytes <= 0:
        raise ValueError("max_output_bytes must be positive")

    process = subprocess.Popen(
        list(command),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        env=execution_environment(),
    )
    stdout_state = _StreamState(max_output_bytes)
    stderr_state = _StreamState(max_output_bytes)
    stdout_thread = threading.Thread(target=_drain_stream, args=(process.stdout, stdout_state), daemon=True)
    stderr_thread = threading.Thread(target=_drain_stream, args=(process.stderr, stderr_state), daemon=True)
    stdout_thread.start()
    stderr_thread.start()

    timed_out = False
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _terminate_process_group(process)

    stdout_thread.join(timeout=5)
    stderr_thread.join(timeout=5)
    if process.stdout is not None:
        process.stdout.close()
    if process.stderr is not None:
        process.stderr.close()

    return ExecutionOutput(
        stdout=stdout_state.text(),
        stderr=stderr_state.text(),
        exit_code=process.returncode,
        timed_out=timed_out,
        output_truncated=stdout_state.truncated or stderr_state.truncated,
    )


class _StreamState:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.content = bytearray()
        self.truncated = False

    def append(self, chunk: bytes) -> None:
        remaining = self.limit - len(self.content)
        if remaining > 0:
            self.content.extend(chunk[:remaining])
        if len(chunk) > remaining:
            self.truncated = True

    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


def _drain_stream(stream: BinaryIO | None, state: _StreamState) -> None:
    if stream is None:
        return
    while chunk := stream.read(8192):
        state.append(chunk)


def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            process.kill()
        process.wait(timeout=3)
