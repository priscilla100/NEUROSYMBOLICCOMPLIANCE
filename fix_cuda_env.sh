#!/usr/bin/env bash
# fix_cuda_env.sh
# Run on a LOGIN NODE (or interactive job) to diagnose and fix the
# PyTorch/CUDA driver mismatch that causes GPU to be ignored.
#
# The symptom:
#   torch.cuda.is_available() → False
#   device_map="auto" → CPU
#   Generation takes hours instead of minutes
#
# The cause:
#   Driver reports CUDA 12.4 / 12.8, but the installed PyTorch was
#   compiled against a different CUDA toolkit (likely 11.x or 12.1).
#   PyTorch refuses to use the GPU and silently falls back to CPU.
#
# Usage:
#   chmod +x fix_cuda_env.sh
#   ./fix_cuda_env.sh          # diagnose + fix
#   ./fix_cuda_env.sh --check  # diagnose only, no changes

set -e

CHECK_ONLY=0
[[ "${1}" == "--check" ]] && CHECK_ONLY=1

source /home/pdanso/miniconda3/etc/profile.d/conda.sh
conda activate compliance_env

echo "============================================================"
echo "  CUDA / PyTorch Diagnostic"
echo "============================================================"

# ── 1. Driver CUDA version ────────────────────────────────────────────────────
echo ""
echo "--- nvidia-smi ---"
nvidia-smi --query-gpu=name,driver_version,memory.total,compute_cap \
    --format=csv,noheader 2>/dev/null || echo "  nvidia-smi not found"
DRIVER_CUDA=$(nvidia-smi 2>/dev/null | grep "CUDA Version" | awk '{print $NF}')
echo "  Driver max CUDA: ${DRIVER_CUDA:-unknown}"

# ── 2. Current PyTorch CUDA version ──────────────────────────────────────────
echo ""
echo "--- PyTorch ---"
python -c "
import torch
print(f'  torch version:        {torch.__version__}')
print(f'  torch CUDA compiled:  {torch.version.cuda}')
print(f'  cuda.is_available():  {torch.cuda.is_available()}')
if torch.cuda.is_available():
    n = torch.cuda.device_count()
    print(f'  GPU count:            {n}')
    for i in range(n):
        cc = torch.cuda.get_device_capability(i)
        name = torch.cuda.get_device_name(i)
        mem = torch.cuda.get_device_properties(i).total_memory // (1024**3)
        print(f'  GPU {i}: {name}  cc={cc[0]}.{cc[1]}  mem={mem}GB')
else:
    print('  !! GPU NOT available to PyTorch — running on CPU !!')
"

# ── 3. Decide which PyTorch to install ───────────────────────────────────────
echo ""
if [[ "${CHECK_ONLY}" == "1" ]]; then
    echo "--- Check only mode — no changes made ---"
    echo ""
    echo "To fix, run without --check:"
    echo "  ./fix_cuda_env.sh"
    exit 0
fi

CUDA_AVAIL=$(python -c "import torch; print(torch.cuda.is_available())")
if [[ "${CUDA_AVAIL}" == "True" ]]; then
    echo "--- PyTorch can already see the GPU — no reinstall needed ---"
    exit 0
fi

echo "--- PyTorch cannot see GPU — reinstalling with correct CUDA build ---"
echo ""

# Driver 12.4 / 12.8 → install PyTorch for CUDA 12.4
# (CUDA is backward compatible, so cu124 works with driver 12.4+)
# If your driver is 11.x, change cu124 → cu118
CUDA_TAG="cu124"
echo "Installing PyTorch + torchvision + torchaudio for CUDA ${CUDA_TAG}..."
echo "(This takes 3-5 minutes)"
echo ""

pip install --upgrade \
    torch \
    torchvision \
    torchaudio \
    --index-url "https://download.pytorch.org/whl/${CUDA_TAG}" \
    --quiet

echo ""
echo "--- Verifying fix ---"
python -c "
import torch
print(f'torch version:        {torch.__version__}')
print(f'torch CUDA compiled:  {torch.version.cuda}')
print(f'cuda.is_available():  {torch.cuda.is_available()}')
if torch.cuda.is_available():
    n = torch.cuda.device_count()
    for i in range(n):
        cc = torch.cuda.get_device_capability(i)
        name = torch.cuda.get_device_name(i)
        mem = torch.cuda.get_device_properties(i).total_memory // (1024**3)
        print(f'GPU {i}: {name}  compute={cc[0]}.{cc[1]}  VRAM={mem}GB')
    print('SUCCESS — GPU is now visible to PyTorch')
else:
    print('STILL FAILING — see note below')
    print('Try: pip install torch --index-url https://download.pytorch.org/whl/cu118')
"

echo ""
echo "============================================================"
echo "  Also fixing: torch_dtype deprecation warning"
echo "  (transformers expects 'dtype' not 'torch_dtype')"
echo "============================================================"
pip install --upgrade transformers accelerate --quiet
python -c "import transformers; print(f'transformers: {transformers.__version__}')"

echo ""
echo "============================================================"
echo "  Done. Now run: ./precache.sh"
echo "  Then submit your SLURM jobs."
echo "============================================================"
