# EvoCurr: self-evolving curriculum with behavior code generation for complex decision-making

## 📝overview

While large language models (LLMs) demonstrate remarkable capabilities across diverse domains, they fail catastrophically on high-complexity tasks requiring long-horizon reasoning and multi-step coordination. To address this problem, we present EvoCurr, a self-evolving curriculum learning framework that enables LLMs to solve complex decision-making problems through cooperative multiagent learning.

## 🚀 Usage

Here are step-by-step instructions to run the training-free GRPO process for agent practice and evaluation. Please follow each step carefully to ensure proper setup and execution.

## Step 0. Environment Setup

### Prerequisites

- Python 3.8+
- StarCraft II client installed
- Windows system (required for StormLib.dll compatibility)
- 20+ GB free disk space for maps and replays

### Install Dependencies

```bash
# Clone the repository
git clone <https://github.com/anchicken/EvoCurr.git>

# Install required packages
pip install -r requirements.txt
```

### Key Dependencies

- `python-sc2`: StarCraft II API for agent control
- `openai`: LLM integration for curriculum generation
- `numpy`, `pillow`: Image processing for terrain analysis
- `ctypes`: For StormLib DLL interaction (Windows only)

***

## Step 1. Curriculum Configuration

The curriculum system automatically generates training tasks of increasing difficulty using LLM-driven curriculum learning.

### Configuration Files

Update `configs/rollout_config.py`:

```python
# Map selection
map_name = 'bush_elsecaro'

# Training parameters
scenario_type = 'pvt'  # Protoss vs Terran
winning_rate = 0.7    # Target win rate threshold
```

### Understanding the Curriculum System

The curriculum generator works through three phases:

1. **Initialization Phase**: Creates a basic, easy scenario
2. **Adaptive Phase**: Adjusts difficulty based on win rate
3. **Final Phase**: Converges to the ultimate task configuration

### Win Rate Adaptation Logic

```
Win Rate >= 70% → Difficulty ⬆️  (More enemies, new units)
Win Rate < 70%  → Difficulty ⬇️  (Fewer enemies, simpler units)
```

------

## Step 2. Map Preparation and Unit Setup

### Prepare Base Map

Ensure your base template map is available:

```bash
# Copy template map
cp Maps/template.SC2Map ./Maps/current_map.SC2Map
```

### Understanding the Unit Editor

The `StormLibUnitEditor` class in `creat_units.py` handles:

- **Terrain Analysis**: Extracts height maps and walkable regions
  - Uses `TerrainAnalyzer` to parse height maps and pathing data
  - Identifies safe unit placement positions
  - Generates visualization of terrain
- **Unit Placement**: Intelligently places units based on terrain
  - Avoids impassable terrain and cliff edges
  - Maintains minimum distances between units
  - Respects map boundaries (0-31 coordinate range)
- **Map Modification**: Uses StormLib to modify MPQ archives
  - Reads/writes Objects.xml for unit placement
  - Preserves other map data and structure

------

## Step 3. Run Curriculum Generation

### Automatic Curriculum Generation

Start the main pipeline which automatically generates curricula:

```bash
python pipeline.py
```

This will execute the following sequence:

1. **Generate Curriculum** (via `curriculum.py`)
   - LLM creates a task based on win/loss results
   - Adjusts difficulty dynamically
   - Returns JSON configuration with unit compositions
2. **Create Battle Scenario** (via `creat_units.py`)
   - Uses `StormLibUnitEditor` to parse map terrain
   - Intelligently places units using terrain analysis
   - Generates LLM-based strategic positioning hints
3. **Configure Technologies** (via `tech_modify.py`)
   - Enables/disables abilities and upgrades
   - Modifies MapScript.galaxy to inject tech initialization
   - Sets per-player ability availability
4. **Train Agent** (via `training.py`)
   - Python-SC2 agent learns on the generated task
   - Multiple restart attempts with iterative improvement
   - Uses LLM for code generation and summarization

### Pipeline Flow Diagram

```
┌─────────────────────┐
│ Curriculum Generator │
│   (LLM-based)       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Map Unit Editor    │
│  (Terrain Analysis) │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Tech Modifier      │
│  (Galaxy Script)    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Agent Training     │
│  (LLM Coder)        │
└──────────┬──────────┘
           │
           ▼
      ┌────────┐
      │ Results │
      └────────┘
```

### Monitor Curriculum Progress

The curriculum generator creates a directory structure:

```
log/
├── 2024-01-15_10-30-45/
│   ├── task_0/
│   │   ├── test.SC2Map
│   │   ├── test1.SC2Map
│   │   ├── training.log
│   │   └── combat_results.json
│   ├── task_1/
│   │   └── ...
│   └── task_9/
│       └── ...
```

Each task directory includes:

- **test.SC2Map**: Generated map with unit placements (before tech modifications)
- **test1.SC2Map**: Final map with technology configurations
- **training.log**: Complete training execution log
- **combat_results.json**: Battle statistics and metrics

### Understanding Curriculum Stages

The system tracks three metrics:

| Metric        | Definition                             |
| ------------- | -------------------------------------- |
| **Win Rate**  | Percentage of battles won by agent     |
| **Tie Rate**  | Percentage of balanced/timeout battles |
| **Loss Rate** | Percentage of battles lost by agent    |

**Adaptation Rules:**

When `win_rate >= winning_rate_threshold` (default 0.7):

- ✅ **Difficulty increases**
- Enemy unit count increases by 10-20%
- Stronger enemy unit types introduced
- New ability combinations unlocked

When `win_rate < winning_rate_threshold`:

- ⬇️ **Difficulty decreases**
- Enemy unit count decreases by 10-20%
- Weaker enemy unit types used
- Simplified unit compositions

------

## Step 4. Agent Training

### Understanding the Training Pipeline

The `training.py` module orchestrates LLM-based code generation through multiple phases:

```
┌──────────────┐
│   Restart    │
│   Attempt    │
└──────┬───────┘
       │
       ▼
┌──────────────┐      ┌──────────────┐
│  Code Gen    │ ───▶ │  Test Code   │
│  (LLMCoder)  │      │  (Validate)  │
└──────────────┘      └──────┬───────┘
       ▲                      │
       │                      ▼
       │                 ┌─────────┐
       │    Bug?    No   │ Success?│
       │    ◀─────────▶  │         │
       │                 └────┬────┘
       │                      │
       │              Yes     ▼
       └──────────────────────┘
                       │
                       ▼
              ┌──────────────────┐
              │ Summarization    │
              │ (LLMSummarizer)  │
              └──────────────────┘
```

### Training Configuration

Key parameters in `training.py`:

```python
tactics_times = 1        # Number of tactic redesigns
restart_times = 3        # Restart attempts per curriculum
generate_times = 15      # Code generation iterations per restart
bug_threshold = 4        # Max consecutive bugs before restart
winning_rate = 0.7       # Target win rate for success
```

***

## Step 5. Configurations

### Map Configuration

Edit `configs/map_config.py`:

```python
class MapConfig:
    maps = {
        'test1': {
            'map_info': 'A 32x32 square map with mixed terrain. Suitable for micro-intensive battles.',
            'units_info': [
                'Marine', 'Marauder', 'Medivac', 'SiegeTank',
                'Zealot', 'Stalker', 'HighTemplar', 'Carrier'
            ],
            'player1_start': (5, 25),
            'player2_start': (25, 5),
            'terrain_type': 'mixed'
        },
        'test2': {
            'map_info': 'A 64x64 large map with strategic positions.',
            'units_info': [...],
            'player1_start': (10, 50),
            'player2_start': (50, 10)
        }
    }
```

### LLM API Configuration

Update `configs/llm_api_config.py`:

```python
class LLMAPIConfig:
    @staticmethod
    def get_model_dict():
        return {
            'planner': 'deepseek-reasoner',
            'coder': 'deepseek-reasoner',
            'checker': 'deepseek-reasoner',
            'summarizer': 'deepseek-reasoner'
        }

    # API Configuration
    LLM_CONFIG = {
        'provider': 'deepseek',
        'api_key': 'sk-your-key',
        'base_url': 'https://api.deepseek.com',
        'temperature': 0.7,
        'max_tokens': 4096,
        'timeout': 60
    }
```

------

## Step 6. Quick Start

```bash
# 1. Setup environment
pip install -r requirements.txt

# 2. Configure parameters (edit configs)
# - configs/rollout_config.py: Set map_name, winning_rate
# - configs/map_config.py: Add your maps

# 3. Prepare base map
cp Maps/template.SC2Map Maps/current_map.SC2Map

# 4. Start pipeline
python pipeline.py
```

### Step-by-Step Execution

**Phase 1: Initialization**

```bash
# Check configuration
cat configs/rollout_config.py

# Verify map file exists
ls -la Maps/test1.SC2Map
```

**Phase 2: Curriculum Generation**

```bash
# Run one curriculum iteration manually
python -c "from curriculum import Curriculum; c = Curriculum(); curr, json = c.generate_curriculum(); print(json)"
```

**Phase 3: Map Creation**

```bash
# Create test map with units
python creat_units.py
```

**Phase 4: Training**

```bash
# Train agent on generated task
python training.py
```
