#!/bin/bash

# LAIA Model Comparison Benchmark
# Tests multiple Ollama models using big_book.txt
# Each model uses its optimal chunk size based on context length

set -e  # Exit on error

# Configuration
TEST_FILE="big_book.txt"
NUM_TESTS=3
MANUAL_PARALLEL=""    # Set via -p flag
MANUAL_CHUNK_SIZE=""  # Set via -c flag (overrides auto-calculation)

# Token Budget Configuration
# Limits context to control KV cache memory allocation
MAX_CONTEXT=8192            # Cap context at 8K tokens (limits RAM usage)
UTILIZATION_FACTOR=40       # Use 40% of context for input (safe for CPU inference)
PROMPT_TOKENS=150           # Instructions + formatting overhead
OUTPUT_TOKENS=500           # Expected response size (entity lists)
SAFETY_MARGIN=500           # Buffer for edge cases
CHARS_PER_TOKEN=3           # Approximate chars per token

# Declare associative arrays for per-model data
declare -A MODEL_CHUNK_SIZES
declare -A MODEL_CONTEXTS
declare -A MODEL_API_CONTEXTS  # Context to use in API calls
declare -A WARMUP_TIMES         # Model loading time (weights from disk)
declare -A CONTEXT_TIMES        # KV cache allocation time
declare -A results              # Test results

# Function to get model's native context length from API
get_model_context() {
    local model=$1
    local model_info=$(curl -s http://localhost:11434/api/show -d "{\"name\": \"$model\"}" 2>/dev/null)

    # Try to find context_length in model_info (format varies by model family)
    local context=$(echo "$model_info" | jq -r '.model_info | to_entries[] | select(.key | endswith("context_length")) | .value' 2>/dev/null | head -1)

    if [ -n "$context" ] && [ "$context" != "null" ]; then
        echo "$context"
    else
        echo "4096"  # Fallback to Ollama default
    fi
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--chunk-size)
            MANUAL_CHUNK_SIZE="$2"
            shift 2
            ;;
        -p|--parallel)
            MANUAL_PARALLEL="$2"
            shift 2
            ;;
        -h|--help)
            echo "LAIA Model Benchmark"
            echo ""
            echo "Usage: $0 [options] model1 model2 [model3 ...]"
            echo ""
            echo "Options:"
            echo "  -c, --chunk-size SIZE   Override auto-calculated chunk size for all models"
            echo "  -p, --parallel N        Override auto-detected parallel workers"
            echo "  -h, --help              Show this help"
            echo ""
            echo "Auto-calculation (token budget approach):"
            echo "  - Context: capped at $MAX_CONTEXT tokens (controls KV cache memory)"
            echo "  - Utilization: ${UTILIZATION_FACTOR}% of context for input (safe for CPU)"
            echo "  - Chunk size: (context × $UTILIZATION_FACTOR% - overhead) × 3 chars/token"
            echo "    Overhead: Prompt=$PROMPT_TOKENS, Output=$OUTPUT_TOKENS, Safety=$SAFETY_MARGIN"
            echo "  - With -c flag: context is calculated from chunk size (saves RAM)"
            echo "  - Without -c: uses MAX_CONTEXT cap ($MAX_CONTEXT tokens)"
            echo "  - Parallel workers: min(CPU cores-2, available RAM / model size)"
            echo ""
            echo "Examples:"
            echo "  $0 llama3.2:1b mistral:7b              # Auto (~9KB chunks, 8K context)"
            echo "  $0 -c 9000 llama3.2:1b gemma3:270m   # 9KB chunks (~5K context, saves RAM)"
            exit 0
            ;;
        *)
            break
            ;;
    esac
done

# Accept models from remaining arguments
if [ $# -lt 2 ]; then
    echo "❌ Error: At least 2 models required for comparison"
    echo ""
    echo "Usage: $0 [options] model1 model2 [model3 ...]"
    echo "  $0 -h for help"
    exit 1
fi
MODELS=("$@")

# Display header
echo "═══════════════════════════════════════════════════════════"
echo "  LAIA Model Benchmark"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "🧪 Models to test:"
for model in "${MODELS[@]}"; do
    echo "   - $model"
done
echo ""

# Check if test file exists
if [ ! -f "$TEST_FILE" ]; then
    echo "❌ Error: $TEST_FILE not found!"
    echo ""
    echo "Create it first with:"
    echo "  curl -o big_book.txt https://www.gutenberg.org/files/2600/2600-0.txt"
    echo "  # OR"
    echo "  python3 generate_realistic_text.py"
    exit 1
fi

FILE_SIZE=$(wc -c < "$TEST_FILE")
FILE_LINES=$(wc -l < "$TEST_FILE")
echo "📄 Test file: $TEST_FILE"
echo "   Size: $FILE_SIZE bytes ($(($FILE_SIZE / 1024)) KB)"
echo "   Lines: $FILE_LINES"
echo ""

# Check Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "❌ Error: Ollama is not running!"
    echo "   Start it with: ollama serve"
    exit 1
fi

echo "✅ Ollama is running"
echo ""

# Function to pull model if needed
pull_model() {
    local model=$1
    echo "📥 Checking model: $model"
    if ! ollama list | grep -q "$model"; then
        echo "   Model not found. Pulling..."
        ollama pull "$model"
    else
        echo "   Model already available"
    fi
}

# Pull both models
for model in "${MODELS[@]}"; do
    pull_model "$model"
    echo ""
done

# Calculate optimal parallel chunks and per-model chunk sizes
calculate_parallel() {
    local largest_model_size=0

    # Check each model's size and calculate optimal chunk size
    for model in "${MODELS[@]}"; do
        # Get size in GB (e.g., "1.5 GB" -> 1.5)
        local size_str=$(ollama list | grep "$model" | awk '{print $3}')
        if [[ -n "$size_str" ]]; then
            local size_gb=$(echo "$size_str" | sed 's/[^0-9.]//g')
            if (( $(echo "$size_gb > $largest_model_size" | bc -l) )); then
                largest_model_size=$size_gb
            fi
        fi

        # Get model's native context length via API
        local native_context=$(get_model_context "$model")

        # Determine effective context based on chunk size or MAX_CONTEXT
        local effective_context
        if [ -n "$MANUAL_CHUNK_SIZE" ]; then
            # When -c is provided: calculate context from chunk size
            local chunk_tokens=$((MANUAL_CHUNK_SIZE / CHARS_PER_TOKEN))
            local overhead=$((PROMPT_TOKENS + OUTPUT_TOKENS + SAFETY_MARGIN))
            local needed_context=$((chunk_tokens + overhead + 1024))

            # Cap at model's native context
            if [ $needed_context -gt $native_context ]; then
                needed_context=$native_context
            fi

            # Cap at MAX_CONTEXT
            if [ $needed_context -gt $MAX_CONTEXT ]; then
                needed_context=$MAX_CONTEXT
            fi

            effective_context=$needed_context
        else
            # No -c flag: use MAX_CONTEXT cap
            effective_context=$native_context
            if [ $native_context -gt $MAX_CONTEXT ]; then
                effective_context=$MAX_CONTEXT
            fi
        fi

        # Calculate chunk size from effective context (using utilization factor)
        local overhead=$((PROMPT_TOKENS + OUTPUT_TOKENS + SAFETY_MARGIN))
        local max_chunk_tokens=$((effective_context * UTILIZATION_FACTOR / 100 - overhead))
        local optimal_chunk=$((max_chunk_tokens * CHARS_PER_TOKEN))

        if [ $optimal_chunk -lt 500 ]; then
            optimal_chunk=500  # Minimum safe size
        fi

        # Store per-model chunk size
        if [ -n "$MANUAL_CHUNK_SIZE" ]; then
            MODEL_CHUNK_SIZES["$model"]=$MANUAL_CHUNK_SIZE
        else
            MODEL_CHUNK_SIZES["$model"]=$optimal_chunk
        fi

        # Store contexts for display and API calls
        MODEL_CONTEXTS["$model"]=$native_context       # Native (for display)
        MODEL_API_CONTEXTS["$model"]=$effective_context # Effective (for API)
    done

    # CPU limit: nproc - 2
    local cpu_parallel=$(( $(nproc) - 2 ))
    if [ $cpu_parallel -lt 1 ]; then
        cpu_parallel=1
    fi

    # RAM limit: available RAM / model size (70% safety margin)
    local available_ram_mb=$(free -m | awk '/^Mem:/{print $7}')
    local available_ram_gb=$(echo "scale=1; $available_ram_mb / 1024" | bc)
    local ram_parallel=$(echo "scale=0; ($available_ram_gb * 0.7) / $largest_model_size" | bc)

    # Ensure at least 1
    if [ -z "$ram_parallel" ] || (( $(echo "$ram_parallel < 1" | bc -l) )); then
        ram_parallel=1
    fi

    # Use the lower of CPU and RAM limits
    if (( $(echo "$cpu_parallel < $ram_parallel" | bc -l) )); then
        PARALLEL_CHUNKS=$cpu_parallel
        PARALLEL_LIMITER="CPU"
    else
        PARALLEL_CHUNKS=$ram_parallel
        PARALLEL_LIMITER="RAM"
    fi

    # Store for display
    CPU_PARALLEL=$cpu_parallel
    RAM_PARALLEL=$ram_parallel
    LARGEST_MODEL_SIZE=$largest_model_size
    AVAILABLE_RAM=$available_ram_gb
}

# Calculate or use manual override
echo "───────────────────────────────────────────────────────────"
echo "RESOURCE ANALYSIS"
echo "───────────────────────────────────────────────────────────"

# Always run calculate_parallel to get per-model chunk sizes
calculate_parallel

if [ -n "$MANUAL_PARALLEL" ]; then
    PARALLEL_CHUNKS=$MANUAL_PARALLEL
    echo "📋 Parallel workers: $PARALLEL_CHUNKS (manual override)"
else
    echo "📋 CPU cores: $(nproc) (using max $CPU_PARALLEL)"
    echo "📋 Available RAM: ${AVAILABLE_RAM} GB"
    echo "📋 Max parallel: $PARALLEL_CHUNKS (${PARALLEL_LIMITER}-limited)"
fi

echo ""
echo "📋 Per-model settings:"
for model in "${MODELS[@]}"; do
    chunk=${MODEL_CHUNK_SIZES[$model]}
    native_ctx=${MODEL_CONTEXTS[$model]}
    effective_ctx=${MODEL_API_CONTEXTS[$model]}

    if [ -n "$MANUAL_CHUNK_SIZE" ]; then
        local_chunk_tokens=$((chunk / CHARS_PER_TOKEN))
        echo "   $model: $chunk bytes (~$local_chunk_tokens tokens, ctx=${effective_ctx})"
    else
        if [ "$native_ctx" -gt "$MAX_CONTEXT" ]; then
            echo "   $model: $chunk bytes (native=${native_ctx}, capped=${effective_ctx} tokens)"
        else
            echo "   $model: $chunk bytes (ctx=${effective_ctx} tokens)"
        fi
    fi
done
echo ""

# Function to measure model loading time (weights from disk to RAM)
measure_warmup() {
    local model=$1
    local result_file=$2
    local start=$(date +%s.%N)

    # Minimal request to load model into memory with tiny context
    local payload='{"model": "'$model'", "prompt": "Hi", "stream": false, "options": {"num_ctx": 512, "temperature": 0.1, "repeat_penalty": 1.2, "repeat_last_n": 128}}'

    if ! curl -s http://localhost:11434/api/generate -d "$payload" > /dev/null 2>&1; then
        echo "0" > "$result_file"
        return 1
    fi

    local end=$(date +%s.%N)
    echo "$(echo "$end - $start" | bc)" > "$result_file"
    return 0
}

# Function to measure KV cache allocation time
measure_context_setup() {
    local model=$1
    local num_ctx=$2
    local result_file=$3
    local start=$(date +%s.%N)

    # Request with target context but tiny prompt (forces KV cache allocation)
    local payload='{"model": "'$model'", "prompt": "Ready", "stream": false, "options": {"num_ctx": '$num_ctx', "temperature": 0.1, "repeat_penalty": 1.2, "repeat_last_n": 128}}'

    if ! curl -s http://localhost:11434/api/generate -d "$payload" > /dev/null 2>&1; then
        echo "0" > "$result_file"
        return 1
    fi

    local end=$(date +%s.%N)
    echo "$(echo "$end - $start" | bc)" > "$result_file"
    return 0
}

# Function to run single test via API
run_test() {
    local model=$1
    local test_num=$2
    local chunk=$3
    local result_file=$4
    local num_ctx=$5
    local keep_alive=$6  # "0" to unload, empty for default

    # Build prompt with chunk and write to temp file (avoids ARG_MAX limit)
    local prompt_file=$(mktemp)
    cat > "$prompt_file" << 'PROMPT_EOF'
Extract all person names, dates, and places from the text below.

Output exactly 3 lines in this format:
NAMES: list names separated by semicolons, or "none"
DATES: list dates separated by semicolons, or "none"
PLACES: list places separated by semicolons, or "none"

PROMPT_EOF
    echo "<text>" >> "$prompt_file"
    echo "$chunk" >> "$prompt_file"
    echo "</text>" >> "$prompt_file"

    # Build JSON payload file using jq with --rawfile (avoids ARG_MAX and shell variable limits)
    local payload_file=$(mktemp)
    if [ -n "$keep_alive" ]; then
        jq -n \
            --arg model "$model" \
            --rawfile prompt "$prompt_file" \
            --argjson num_ctx "$num_ctx" \
            --argjson temperature 0.1 \
            --argjson repeat_penalty 1.2 \
            --argjson repeat_last_n 128 \
            --argjson keep_alive "$keep_alive" \
            '{model: $model, prompt: $prompt, stream: false, options: {num_ctx: $num_ctx, temperature: $temperature, repeat_penalty: $repeat_penalty, repeat_last_n: $repeat_last_n}, keep_alive: $keep_alive}' \
            > "$payload_file"
    else
        jq -n \
            --arg model "$model" \
            --rawfile prompt "$prompt_file" \
            --argjson num_ctx "$num_ctx" \
            --argjson temperature 0.1 \
            --argjson repeat_penalty 1.2 \
            --argjson repeat_last_n 128 \
            '{model: $model, prompt: $prompt, stream: false, options: {num_ctx: $num_ctx, temperature: $temperature, repeat_penalty: $repeat_penalty, repeat_last_n: $repeat_last_n}}' \
            > "$payload_file"
    fi

    rm -f "$prompt_file"

    # Record start time
    local start=$(date +%s.%N)

    # Run via API using payload file (avoids shell variable size limits)
    echo "      ┌─ Response ─────────────────────────────────"
    local response
    if ! response=$(curl -s http://localhost:11434/api/generate --data-binary "@$payload_file" 2>/dev/null); then
        echo "      └─────────────────────────────────────────────"
        echo "   ❌ Error running test (curl failed)"
        rm -f "$payload_file"
        echo "0" > "$result_file"
        return 1
    fi

    rm -f "$payload_file"

    # Extract and display response
    local output=$(echo "$response" | jq -r '.response // empty')
    if [ -z "$output" ]; then
        local error=$(echo "$response" | jq -r '.error // "Unknown error"')
        echo "      │ ❌ $error"
    else
        echo "$output" | while IFS= read -r line; do
            printf "      │ %s\n" "$line"
        done
    fi
    echo "      └─────────────────────────────────────────────"

    # Record end time and calculate elapsed
    local end=$(date +%s.%N)
    local elapsed=$(echo "$end - $start" | bc)

    # Write elapsed time to result file
    echo "$elapsed" > "$result_file"
}

echo "───────────────────────────────────────────────────────────"
echo "BENCHMARK PHASE"
echo "───────────────────────────────────────────────────────────"
echo "Running $NUM_TESTS tests per model (with isolated timing)..."
echo ""

# Run tests for each model
for model in "${MODELS[@]}"; do
    # Get this model's chunk size and API context
    chunk_size=${MODEL_CHUNK_SIZES[$model]}
    api_context=${MODEL_API_CONTEXTS[$model]}
    # Extract SECOND chunk (skip first chunk to avoid Gutenberg header/TOC)
    CHUNK=$(dd if="$TEST_FILE" bs=$chunk_size skip=1 count=1 2>/dev/null)

    echo "📦 $model"
    echo "   Chunk size: $chunk_size bytes (~$((chunk_size / 3)) tokens)"
    echo "   API context: $api_context tokens"
    echo ""

    # Phase 1: Measure warmup (model loading)
    echo "   Phase 1: Warmup (loading model weights)..."
    result_file=$(mktemp)
    measure_warmup "$model" "$result_file"
    warmup_time=$(cat "$result_file")
    rm -f "$result_file"
    if [ -n "$warmup_time" ] && [ "$warmup_time" != "0" ]; then
        printf "   ✅ Warmup completed in %5.2f seconds\n" "$warmup_time"
        WARMUP_TIMES["$model"]=$warmup_time
    else
        echo "   ❌ Warmup failed"
        WARMUP_TIMES["$model"]=0
    fi
    echo ""

    # Phase 2: Measure context setup (KV cache allocation)
    echo "   Phase 2: Context setup (allocating KV cache for $api_context tokens)..."
    result_file=$(mktemp)
    measure_context_setup "$model" "$api_context" "$result_file"
    context_time=$(cat "$result_file")
    rm -f "$result_file"
    if [ -n "$context_time" ] && [ "$context_time" != "0" ]; then
        printf "   ✅ Context setup completed in %5.2f seconds\n" "$context_time"
        CONTEXT_TIMES["$model"]=$context_time
    else
        echo "   ❌ Context setup failed"
        CONTEXT_TIMES["$model"]=0
    fi
    echo ""

    # Phase 3: Run inference tests
    echo "   Phase 3: Inference tests..."
    total_time=0

    for i in $(seq 1 $NUM_TESTS); do
        echo "      Test $i/$NUM_TESTS"
        echo "      Started: $(date '+%H:%M:%S')"

        # Use temp file for result (avoids capturing display output)
        result_file=$(mktemp)

        # Add keep_alive=0 only on the last test to unload after completion
        if [ $i -eq $NUM_TESTS ]; then
            run_test "$model" "$i" "$CHUNK" "$result_file" "$api_context" "0"
        else
            run_test "$model" "$i" "$CHUNK" "$result_file" "$api_context" ""
        fi

        exit_code=$?
        elapsed=$(cat "$result_file")
        rm -f "$result_file"

        if [ $exit_code -eq 0 ] && [ -n "$elapsed" ] && [ "$elapsed" != "0" ]; then
            printf "      ✅ Completed in %5.2f seconds\n\n" "$elapsed"
            total_time=$(echo "$total_time + $elapsed" | bc)
            results["$model,$i"]=$elapsed
        else
            echo "      ❌ Failed"
            results["$model,$i"]=0
        fi

        # Small delay between tests
        sleep 1
    done

    # Calculate average inference time
    avg=$(echo "scale=2; $total_time / $NUM_TESTS" | bc)
    results["$model,avg"]=$avg

    # Calculate total time (warmup + context + avg inference)
    model_warmup=${WARMUP_TIMES["$model"]:-0}
    model_context=${CONTEXT_TIMES["$model"]:-0}
    model_total=$(echo "scale=2; $model_warmup + $model_context + $avg" | bc)
    results["$model,total"]=$model_total

    echo "   📊 Timing Summary:"
    printf "      Warmup:        %6.2f s\n" "$model_warmup"
    printf "      Context setup: %6.2f s\n" "$model_context"
    printf "      Avg inference: %6.2f s\n" "$avg"
    printf "      Total:         %6.2f s\n" "$model_total"
    echo ""
    echo "   🧹 Model unloaded (keep_alive: 0)"
    echo ""
    echo "───────────────────────────────────────────────────────────"
    echo ""
done

# Summary Report
echo "═══════════════════════════════════════════════════════════"
echo "  RESULTS SUMMARY"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Build dynamic header based on number of models
header_width=12
total_width=$((22 + (${#MODELS[@]} * (header_width + 3)) + 1))

# Print header row
printf "┌──────────────────────"
for model in "${MODELS[@]}"; do
    printf "┬─────────────"
done
printf "┐\n"

# Print model names row
printf "│ Model                "
for model in "${MODELS[@]}"; do
    # Truncate/pad model name to fit
    short_name=$(echo "$model" | cut -c1-11)
    printf "│ %-11s " "$short_name"
done
printf "│\n"

# Print separator
printf "├──────────────────────"
for model in "${MODELS[@]}"; do
    printf "┼─────────────"
done
printf "┤\n"

# Print warmup times
printf "│ Warmup               "
for model in "${MODELS[@]}"; do
    time=${WARMUP_TIMES["$model"]:-0}
    printf "│ %6.2f s    " "$time"
done
printf "│\n"

# Print context setup times
printf "│ Context Setup        "
for model in "${MODELS[@]}"; do
    time=${CONTEXT_TIMES["$model"]:-0}
    printf "│ %6.2f s    " "$time"
done
printf "│\n"

# Print separator
printf "├──────────────────────"
for model in "${MODELS[@]}"; do
    printf "┼─────────────"
done
printf "┤\n"

# Print individual test results
for i in $(seq 1 $NUM_TESTS); do
    printf "│ Test %-15d " "$i"
    for model in "${MODELS[@]}"; do
        time=${results["$model,$i"]:-0}
        printf "│ %6.2f s    " "$time"
    done
    printf "│\n"
done

# Print separator
printf "├──────────────────────"
for model in "${MODELS[@]}"; do
    printf "┼─────────────"
done
printf "┤\n"

# Print inference average
printf "│ Avg Inference        "
for model in "${MODELS[@]}"; do
    avg=${results["$model,avg"]:-0}
    printf "│ %6.2f s    " "$avg"
done
printf "│\n"

# Print total (warmup + context + inference)
printf "│ TOTAL                "
for model in "${MODELS[@]}"; do
    total=${results["$model,total"]:-0}
    printf "│ %6.2f s    " "$total"
done
printf "│\n"

# Find winner (fastest total time)
fastest_model=""
fastest_total=999999
for model in "${MODELS[@]}"; do
    total=${results["$model,total"]:-999999}
    if (( $(echo "$total < $fastest_total" | bc -l) )); then
        fastest_total=$total
        fastest_model=$model
    fi
done

# Print footer
printf "└──────────────────────"
for model in "${MODELS[@]}"; do
    printf "┴─────────────"
done
printf "┘\n"

echo ""
echo "🏆 Winner: $fastest_model"
echo "   Total time: ${fastest_total}s"
echo ""

# Estimate full document time for each model using its chunk size (using actual file size)
FILE_SIZE_BYTES=$FILE_SIZE
FILE_SIZE_KB=$((FILE_SIZE_BYTES / 1024))

echo "📊 Full Document Estimate (${FILE_SIZE_KB}KB, $PARALLEL_CHUNKS parallel):"
for model in "${MODELS[@]}"; do
    avg=${results["$model,avg"]:-0}
    chunk=${MODEL_CHUNK_SIZES[$model]}
    if [ "$avg" != "0" ] && [ -n "$chunk" ]; then
        num_chunks=$(echo "scale=0; ($FILE_SIZE_BYTES + $chunk - 1) / $chunk" | bc)
        total=$(echo "scale=0; ($avg * $num_chunks) / $PARALLEL_CHUNKS" | bc)
        printf "   %-20s ~%4ds (%d min) [chunk=%d, %d chunks]\n" "$model:" "$total" "$(($total / 60))" "$chunk" "$num_chunks"
    fi
done
echo ""

echo "═══════════════════════════════════════════════════════════"
