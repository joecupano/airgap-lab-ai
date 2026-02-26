#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

detect_gpu_vendor() {
  if command -v nvidia-smi >/dev/null 2>&1; then
    echo "nvidia"
    return
  fi

  if command -v rocminfo >/dev/null 2>&1; then
    echo "amd"
    return
  fi

  if lspci 2>/dev/null | grep -qi 'NVIDIA'; then
    echo "nvidia"
    return
  fi

  if lspci 2>/dev/null | grep -Eqi 'AMD|Advanced Micro Devices' && lspci 2>/dev/null | grep -Eqi 'VGA|3D|Display'; then
    echo "amd"
    return
  fi

  echo "none"
}

has_nvidia_toolkit() {
  command -v nvidia-ctk >/dev/null 2>&1 || return 1
  docker info --format '{{json .Runtimes}}' 2>/dev/null | grep -q '"nvidia"'
}

has_amd_toolkit() {
  command -v amdgpu-container-runtime >/dev/null 2>&1 || command -v rocm-container-runtime >/dev/null 2>&1 || return 1
  [[ -e /dev/kfd && -e /dev/dri ]]
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

install_amd_toolkit_debian() {
  if ! command -v sudo >/dev/null 2>&1; then
    echo "'sudo' is required to install AMD container runtime automatically."
    return 1
  fi

  echo "Installing AMD GPU container prerequisites (Debian/Ubuntu)..."
  sudo apt-get update
  sudo apt-get install -y rocm-hip-runtime rocm-opencl-runtime

  if apt-cache policy amdgpu-container-runtime 2>/dev/null | grep -q 'Candidate:'; then
    sudo apt-get install -y amdgpu-container-runtime
  elif apt-cache policy rocm-container-runtime 2>/dev/null | grep -q 'Candidate:'; then
    sudo apt-get install -y rocm-container-runtime
  else
    echo "AMD container runtime package not found in current apt repos."
    echo "Install AMD ROCm repository and runtime, then re-run: ./start-stack.sh --gpu --vendor amd"
    return 1
  fi
}

ensure_gpu_prereqs_nvidia() {
  if has_nvidia_toolkit; then
    return 0
  fi

  echo "NVIDIA Container Toolkit is not detected/configured for Docker."
  echo "NVIDIA GPU mode requires NVIDIA drivers + NVIDIA Container Toolkit."

  if [[ "$AUTO_INSTALL_TOOLKIT" -eq 1 ]]; then
    echo "Auto-install requested (--install-toolkit)."
    if [[ -f /etc/debian_version ]]; then
      install_nvidia_toolkit_debian || return 1
    else
      echo "Automatic install is currently supported for Debian/Ubuntu only."
      echo "Install manually, then re-run: ./start-stack.sh --gpu --vendor nvidia"
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
          echo "Install manually, then re-run: ./start-stack.sh --gpu --vendor nvidia"
          return 1
        fi
        ;;
      *)
        echo "Skipped installation. Cannot continue in NVIDIA GPU mode."
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

ensure_gpu_prereqs_amd() {
  if has_amd_toolkit; then
    return 0
  fi

  echo "AMD GPU container prerequisites are not detected."
  echo "AMD GPU mode requires ROCm userspace + AMD container runtime and /dev/kfd,/dev/dri access."

  if [[ "$AUTO_INSTALL_TOOLKIT" -eq 1 ]]; then
    echo "Auto-install requested (--install-toolkit)."
    if [[ -f /etc/debian_version ]]; then
      install_amd_toolkit_debian || return 1
    else
      echo "Automatic install is currently supported for Debian/Ubuntu only."
      echo "Install manually, then re-run: ./start-stack.sh --gpu --vendor amd"
      return 1
    fi
  else
    read -r -p "Install AMD GPU container prerequisites now? [y/N]: " reply
    case "$reply" in
      y|Y|yes|YES)
        if [[ -f /etc/debian_version ]]; then
          install_amd_toolkit_debian || return 1
        else
          echo "Automatic install is currently supported for Debian/Ubuntu only."
          echo "Install manually, then re-run: ./start-stack.sh --gpu --vendor amd"
          return 1
        fi
        ;;
      *)
        echo "Skipped installation. Cannot continue in AMD GPU mode."
        return 1
        ;;
    esac
  fi

  if ! has_amd_toolkit; then
    echo "AMD prerequisites still not detected after install step."
    echo "Re-run after resolving ROCm/container runtime setup."
    return 1
  fi

  return 0
}

verify_gpu_runtime() {
  if [[ "$USE_GPU" -ne 1 ]]; then
    return 0
  fi

  if ! docker ps --format '{{.Names}}' | grep -qx 'airgap-ollama'; then
    echo "GPU verify: ollama container not running yet (airgap-ollama)."
    return 1
  fi

  if [[ "$GPU_VENDOR" == "nvidia" ]]; then
    if docker inspect airgap-ollama --format '{{json .HostConfig.DeviceRequests}}' 2>/dev/null | grep -qi 'nvidia'; then
      echo "GPU verify: NVIDIA runtime/device request detected for ollama container."
      return 0
    fi
    echo "GPU verify: NVIDIA runtime/device request NOT detected for ollama container."
    return 1
  fi

  if [[ "$GPU_VENDOR" == "amd" ]]; then
    if docker inspect airgap-ollama --format '{{json .HostConfig.Devices}}' 2>/dev/null | grep -q '/dev/kfd'; then
      echo "GPU verify: AMD device mapping (/dev/kfd,/dev/dri) detected for ollama container."
      return 0
    fi
    echo "GPU verify: AMD device mapping NOT detected for ollama container."
    return 1
  fi

  return 1
}

USE_GPU=0
AUTO_INSTALL_TOOLKIT=0
GPU_VENDOR="auto"
STRICT_GPU_VERIFY=0

for arg in "$@"; do
  case "$arg" in
    --gpu)
      USE_GPU=1
      ;;
    --install-toolkit)
      AUTO_INSTALL_TOOLKIT=1
      ;;
    --vendor=nvidia)
      GPU_VENDOR="nvidia"
      ;;
    --vendor=amd)
      GPU_VENDOR="amd"
      ;;
    --strict-gpu-verify)
      STRICT_GPU_VERIFY=1
      ;;
    *)
      echo "Usage: ./start-stack.sh [--gpu] [--install-toolkit] [--vendor=nvidia|amd] [--strict-gpu-verify]"
      exit 1
      ;;
  esac
done

if [[ "$AUTO_INSTALL_TOOLKIT" -eq 1 && "$USE_GPU" -ne 1 ]]; then
  echo "--install-toolkit can only be used with --gpu"
  echo "Usage: ./start-stack.sh [--gpu] [--install-toolkit] [--vendor=nvidia|amd] [--strict-gpu-verify]"
  exit 1
fi

if [[ "$GPU_VENDOR" != "auto" && "$USE_GPU" -ne 1 ]]; then
  echo "--vendor can only be used with --gpu"
  echo "Usage: ./start-stack.sh [--gpu] [--install-toolkit] [--vendor=nvidia|amd] [--strict-gpu-verify]"
  exit 1
fi

if [[ "$STRICT_GPU_VERIFY" -eq 1 && "$USE_GPU" -ne 1 ]]; then
  echo "--strict-gpu-verify can only be used with --gpu"
  echo "Usage: ./start-stack.sh [--gpu] [--install-toolkit] [--vendor=nvidia|amd] [--strict-gpu-verify]"
  exit 1
fi

if [[ "$USE_GPU" -eq 1 ]]; then
  if [[ "$GPU_VENDOR" == "auto" ]]; then
    GPU_VENDOR="$(detect_gpu_vendor)"
  fi

  if [[ "$GPU_VENDOR" == "none" ]]; then
    echo "No supported GPU vendor detected (NVIDIA/AMD)."
    echo "Use CPU mode: ./start-stack.sh"
    exit 1
  fi

  if [[ "$GPU_VENDOR" == "nvidia" ]]; then
    ensure_gpu_prereqs_nvidia
  elif [[ "$GPU_VENDOR" == "amd" ]]; then
    ensure_gpu_prereqs_amd
  else
    echo "Unsupported GPU vendor selection: $GPU_VENDOR"
    exit 1
  fi

  if [[ "$GPU_VENDOR" == "nvidia" ]]; then
    if [[ ! -f docker-compose.gpu.yml ]]; then
      echo "Missing docker-compose.gpu.yml"
      exit 1
    fi
    echo "Starting stack with NVIDIA GPU override..."
    docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build -d
  else
    if [[ ! -f docker-compose.gpu-amd.yml ]]; then
      echo "Missing docker-compose.gpu-amd.yml"
      exit 1
    fi
    echo "Starting stack with AMD GPU override..."
    docker compose -f docker-compose.yml -f docker-compose.gpu-amd.yml up --build -d
  fi
else
  echo "Starting stack in standard mode..."
  docker compose up --build -d
fi

echo "UI: http://localhost:8080"
echo "API: http://localhost:8000"

if [[ "$USE_GPU" -eq 1 ]]; then
  if ! verify_gpu_runtime; then
    echo "GPU verify: check docker compose and host GPU runtime setup."
    if [[ "$STRICT_GPU_VERIFY" -eq 1 ]]; then
      exit 1
    fi
  fi
fi
