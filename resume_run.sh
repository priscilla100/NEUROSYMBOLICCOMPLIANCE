#!/usr/bin/env bash                                                                                                         
  set -euo pipefail
  cd "$(dirname "$0")"                                                                                                        
  export OLLAMA_KEEP_ALIVE=24h                              
                                                                                                                              
  # ── Resume from gpt-oss rag_cot onwards ──────────────────────────────────────                                             
  # Copy completed CSVs from old run into results/ first, then run this.                                                      
  # --skip-existing will skip the good files; failed/missing files will rerun.                                                
                                                                                                                              
  RESULTS_DIR="results/$(date +%Y%m%d_%H%M%S)"                                                                                
  mkdir -p "$RESULTS_DIR"                                                                                                     
                                                                                                                              
  echo "Resuming from gpt-oss rag_cot..."                   

  # gpt-oss: only the remaining strategies                                                                                    
  python3 run_benchmark.py --models  gpt-oss:latest --strategies formal agentic --datasets goldcoin hipaa_qa  --skip-existing                                                                                                         
                                                            
  echo "Running qwen3:14b (all strategies)..."                                                                                
                                                            
  python3 run_benchmark.py  --models  qwen3:14b --strategies baseline baseline_fs baseline_cot baseline_fscot rag rag_fs rag_cot rag_fscot formal agentic  --datasets goldcoin hipaa_qa   --skip-existing

  echo "Running component evals..."
  COMPONENT_MODEL="ollama/qwen3:14b"
                                                                                                                              
  python3 eval_component1_souffle.py --model "$COMPONENT_MODEL" --skip-existing                                               
  python3 eval_component2_llm2.py --component1 data/eval_component1.csv --model "$COMPONENT_MODEL" --rubric data/explanation_rubric.csv --skip-existing                                                                                 
  python3 eval_e2e.py --llm1 "$COMPONENT_MODEL" --llm2 "$COMPONENT_MODEL" --skip-existing
  python3 evaluate_llm1.py --goldcoin data/goldcoin.csv --model "$COMPONENT_MODEL" --out evaluate_llm1_goldcoin_results.csv   
  python3 evaluate_llm2.py --results results/ --rubric data/explanation_rubric.csv --out evaluate_llm2_results.csv            
                                                                                                                              
  echo "Running model-swap ablation..."                                                                                       
  for ENTRY in \                                                                                                              
      "llama32-llama32    ollama/llama3.2:latest   ollama/llama3.2:latest" \                                                  
      "qwen3-qwen3        ollama/qwen3:14b         ollama/qwen3:14b" \                                                        
      "gptoss-gptoss      ollama/gpt-oss:latest    ollama/gpt-oss:latest" \                                                   
      "qwen3-llama32      ollama/qwen3:14b         ollama/llama3.2:latest" \                                                  
      "llama32-qwen3      ollama/llama3.2:latest   ollama/qwen3:14b"                                                          
  do                                                                                                                          
      TAG=$(echo "$ENTRY" | awk '{print $1}')                                                                                 
      LLM1=$(echo "$ENTRY" | awk '{print $2}')                                                                                
      LLM2=$(echo "$ENTRY" | awk '{print $3}')
      python3 eval_e2e.py --llm1 "$LLM1" --llm2 "$LLM2" \                                                                     
          --out "data/eval_e2e_${TAG}.csv" --skip-existing \
          || echo "[WARN] $TAG failed — continuing"                                                                           
  done                                                                                                                        
                                                                                                                              
  echo "ALL DONE: $(date)"  