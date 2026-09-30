"""Comprueba que PyTorch ve la GPU AMD vía ROCm. Ejecutar dentro de WSL2: `just gpu`."""

import sys

try:
    import torch
except ImportError:
    sys.exit("torch no está instalado: en WSL2 ejecuta `uv run just setup`.")

hip = torch.version.hip
print(f"torch        {torch.__version__}")
print(f"HIP (ROCm)   {hip}")
print(f"CUDA         {torch.version.cuda}")
print(f"GPU visible  {torch.cuda.is_available()}")

if hip is None:
    sys.exit("Este torch no es la build de ROCm (torch.version.hip es None).")
if not torch.cuda.is_available():
    sys.exit("ROCm instalado pero sin GPU visible: revisa el driver de AMD para WSL.")

props = torch.cuda.get_device_properties(0)
print(f"Dispositivo  {props.name} · {props.total_memory / 2**30:.1f} GiB")
x = torch.randn(2048, 2048, device="cuda")
print(f"matmul OK    {(x @ x).sum().item():.2f}")
