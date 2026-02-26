#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

has_nvidia_toolkit() {
  command -v nvidia-ctk >/dev/null 2>&1 || return 1
  docker info --format '{{json .Runtimes}}' 2>/dev/null | grep -q '"nvidia"'
}

install_nvidia_toolkit_debian() {
  if ! command -v sudo >/dev/null 2>&1; then
    echo "'sudo' is required to install NVIDIA Container Toolkit automatically."
    return 1
  fi

  echo "Installing NVIDIA Container Toolkit (Debian/Ubuntu)..."
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

  curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null

  sudo apt-get update
  sudo apt-get install -y nvidia-container-toolkit
  sudo nvidia-ctk runtime configure --runtime=docker
  sudo systemctl restart docker
}

ensure_gpu_prereqs() {
  if has_nvidia_toolkit; then
    return 0
  fi

  echo "NVIDIA Container Toolkit is not detected/configured for Docker."
  echo "GPU mode requires NVIDIA drivers + NVIDIA Container Toolkit."

  if [[ "$AUTO_INSTALL_TOOLKIT" -eq 1 ]]; then
    echo "Auto-install requested (--install-toolkit)."
    if [[ -f /etc/debian_version ]]; then
      install_nvidia_toolkit_debian || return 1
    else
      echo "Automatic install is currently supported for Debian/Ubuntu only."
      echo "Install manually, then re-run: ./start-stack.sh --gpu"
      return 1
    fi
  else
    read -r -p "Install NVIDIA Container Toolkit now? [y/N]: " reply
    case "$reply" in
      y|Y|yes|YES)
        if [[ -f /etc/debian_version ]]; then
          install_nvidia_toolkit_debian || return 1
        else
          echo "Automatic install is currently supported for Debian/Ubuntu only."
          echo "Install manually, then re-run: ./start-stack.sh --gpu"
          return 1
        fi
        ;;
      *)
        echo "Skipped installation. Cannot continue in GPU mode."
        return 1
        ;;
    esac
  fi

  if ! has_nvidia_toolkit; then
    echo "NVIDIA Container Toolkit still not detected after install step."
    echo "Re-run after resolving host GPU runtime setup."
    return 1
  fi

  return 0
}

USE_GPU=0
AUTO_INSTALL_TOOLKIT=0

for arg in "$@"; do
  case "$arg" in
    --gpu)
      USE_GPU=1
      ;;
    --install-toolkit)
      AUTO_INSTALL_TOOLKIT=1
      ;;
    *)
      echo "Usage: ./start-stack.sh [--gpu] [--install-toolkit]"
      exit 1
      ;;
  esac
done

if [[ "$AUTO_INSTALL_TOOLKIT" -eq 1 && "$USE_GPU" -ne 1 ]]; then
  echo "--install-toolkit can only be used with --gpu"
  echo "Usage: ./start-stack.sh [--gpu] [--install-toolkit]"
  exit 1
fi

if [[ "$USE_GPU" -eq 1 ]]; then
  ensure_gpu_prereqs

  if [[ ! -f docker-compose.gpu.yml ]]; then
    echo "Missing docker-compose.gpu.yml"
    exit 1
  fi
  echo "Starting stack with GPU override..."
  docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build -d
else
  echo "Starting stack in standard mode..."
  docker compose up --build -d
fi

echo "UI: http://localhost:8080"
echo "API: http://localhost:8000"
