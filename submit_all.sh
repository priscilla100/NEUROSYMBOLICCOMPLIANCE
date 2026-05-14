#!/usr/bin/env bash
# submit_all.sh — submit all 9 benchmark jobs to SLURM
#
# Jobs run in parallel. Each gets its own GPU allocation.
# deepseek32b and llama70b need the most VRAM — they may queue
# until an H100 or 2x RTX8000 slot opens.
#
# Monitor:  squeue -u pdanso
# Logs:     tail -f logs/<slug>_<JOB_ID>_out.txt
# Resubmit: sbatch jobs/job_<slug>.sh  (--skip-existing skips done CSVs)
# Cancel:   scancel -u pdanso

set -e
cd /home/pdanso/COMPLIANCEGPT
mkdir -p logs

echo "============================================================"
echo "  ComplianceGPT — Submitting 9 model benchmark jobs"
echo "  $(date)"
echo "============================================================"
echo ""
sinfo --format="  %-10P %-5a %-12l %-5D %-8t %N" 2>/dev/null
echo ""

declare -A JOBS

submit() {
    local slug=$1 script=$2
    local jid
    jid=$(sbatch --parsable "jobs/${script}")
    JOBS[$slug]=$jid
    echo "  ${slug} → job ${jid}"
}

echo "--- Submitting 7B-9B models (1x GPU, ~11-13hr wall) ---"
submit mistral7b    job_mistral7b.sh
submit llama8b      job_llama8b.sh
submit gemma9b      job_gemma9b.sh
submit qwen7b       job_qwen7b.sh

echo ""
echo "--- Submitting 12B-14B models (1x GPU, ~17-20hr wall) ---"
submit mistral_nemo job_mistral_nemo.sh
submit qwen14b      job_qwen14b.sh
submit phi4         job_phi4.sh

echo ""
echo "--- Submitting large models (need H100 or 2x RTX8000) ---"
submit deepseek32b  job_deepseek32b.sh
submit llama70b     job_llama70b.sh

echo ""
echo "============================================================"
echo "  All 9 jobs submitted"
echo "============================================================"
echo ""
echo "Monitor all:  squeue -u pdanso"
echo ""
echo "Watch logs:"
for slug in "${!JOBS[@]}"; do
    echo "  tail -f logs/${slug}_${JOBS[$slug]}_out.txt"
done | sort
echo ""
echo "If a job dies before finishing, resubmit — --skip-existing"
echo "means it picks up from the last completed CSV row:"
echo "  sbatch jobs/job_<slug>.sh"
