"""在 Docker 容器中执行 Godot CLI（ADR-13 §3.8）。"""

from __future__ import annotations

from pathlib import Path

CONTAINER_WORKSPACE = "/workspace"
GODOT_ENTRYPOINT = "godot"


def build_docker_godot_cmd(
    workspace: Path,
    *,
    image: str,
    godot_args: list[str],
) -> list[str]:
    """构造 ``docker run --rm -v … godot …`` 命令行。"""
    host_path = workspace.resolve()
    container_path = CONTAINER_WORKSPACE
    translated: list[str] = []
    for arg in godot_args:
        text = str(arg)
        if text == str(workspace):
            translated.append(container_path)
        elif text.startswith(str(host_path)):
            translated.append(container_path + text[len(str(host_path)) :])
        else:
            translated.append(text)
    return [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{host_path}:{container_path}",
        "-w",
        container_path,
        image.strip(),
        GODOT_ENTRYPOINT,
        *translated,
    ]
