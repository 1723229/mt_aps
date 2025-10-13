# 茅台生产排产系统 (Maotai Production Scheduling System)

A production scheduling optimization system for Maotai packaging lines using heuristic/greedy algorithms with rule-based constraints.

## 系统概述 (System Overview)

This system implements an intelligent production scheduling solution for Maotai's packaging workshop, optimizing line-product-crew assignments while satisfying multiple constraints to maximize capacity utilization and balance crew workload.

### Key Features

- **Greedy Algorithm with Rule-Based Logic**: Chronological scheduling with locally optimal decisions
- **Multi-Constraint Satisfaction**: Implements 10 base constraints (BC-01 to BC-10) and 4 regional constraints
- **Product Priority Management**: Handles delivery dates and priority periods
- **Changeover Optimization**: 0.9 coefficient for capacity loss during product changeover
- **Crew Workload Balance**: Distributes work evenly across crews
- **Flexible Regional Rules**: Supports 4 different packaging area configurations

## Architecture

```
mt_aps/
├── src/
│   ├── models/              # Data models (Pydantic)
│   ├── constraints/         # Constraint validators
│   ├── scheduler/           # Core scheduling engine
│   ├── utils/               # Utilities (calculators, validators, sorters)
│   └── exporters/           # Output formatters (CSV, reports)
├── tests/
│   ├── unit/                # Unit tests
│   └── integration/         # Integration tests
├── docs/                    # Documentation and reference data
├── results/                 # Output directory
├── main.py                  # CLI entry point
└── requirements.txt         # Dependencies
```

## Installation

### Prerequisites

- Python 3.10+
- pip

### Install Dependencies

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

```bash
python main.py --input docs/排产入参.json --output results/schedule.csv
```

### Full Options

```bash
python main.py \
  --input docs/排产入参.json \
  --output results/schedule.csv \
  --report results/report.txt \
  --standard-csv results/schedule_standard.csv
```

### Command Line Arguments

- `--input`: Input JSON file path (required)
- `--output`: Output CSV file path (default: `results/schedule.csv`)
- `--report`: Report text file path (default: `results/report.txt`)
- `--standard-csv`: Standard format CSV output (default: `results/schedule_standard.csv`)
- `--validate-only`: Only validate constraints without full scheduling

### Example

```bash
# Run scheduling
python main.py --input docs/排产入参.json

# Validate only
python main.py --input docs/排产入参.json --validate-only
```

## Algorithm Overview

### Phase 1: Preprocessing

1. **Input Validation**: Validate JSON structure and data completeness
2. **Relationship Building**: Construct line↔product, line↔crew mappings
3. **Capacity Check**: Verify total capacity ≥ total demand
4. **Constraint Validation**: Check for conflicts (e.g., forbidden lines vs exclusive products)

### Phase 2: Product Prioritization

Sort products by:
1. Products with priority constraints (`product_priority`)
2. Products with delivery dates (earliest first)
3. Products by planned quantity (largest first)
4. Zero-quantity products (for placeholder)

### Phase 3: Main Scheduling Loop

For each date and shift:

1. **Get Available Resources**
   - Available lines (excluding forbidden)
   - Available crews (not scheduled today)

2. **Schedule by Region**
   - Old Packaging (030201, 030202, 030210): Fixed crew pairs, 1 line idle
   - New Packaging A (030203, 030204, 030207, 030211): Flexible, max 1 idle line
   - New Packaging B (030205, 030206): Strict double shifts
   - New Packaging C+D (030208, 030209, 030212, 030213): 2 double + 2 single rule

3. **Product Allocation**
   - Check ongoing product (continuity constraint)
   - Select next product by priority
   - Consider `productLineWeight` for line selection

4. **Crew Selection**
   - Priority by `lineCrewPriority` (line's preference)
   - Secondary by `crewLinePriority` (crew's preference)
   - Tertiary by current workload (balance)

5. **Capacity Calculation**
   - Use `productionCapacity` if available, else `standardCapacity`
   - Check if product nearing completion

6. **Changeover Handling**
   - If product completing: `changeover_usable = (capacity - remaining) × 0.9`
   - Select next product for second half
   - Verify total ≤ standard capacity

### Phase 4: Validation

- Validate all BC-01 to BC-10 constraints
- Check regional constraints
- Calculate utilization metrics
- Generate warnings

### Phase 5: Output Generation

- CSV export (reference format)
- Standard table format
- Analysis reports (products, crews, capacity)

## Core Constraints

### Base Constraints (BC-01 to BC-10)

| ID | Constraint | Description |
|----|-----------|-------------|
| BC-01 | Line-Product-Crew Binding | Crew can only produce specific products on specific lines |
| BC-02 | Daily Double Shifts | Each line has morning and middle shifts (with exceptions) |
| BC-03 | Crew Single Shift | Each crew works at most one shift per day |
| BC-04 | Crew Full Scheduling | All crews scheduled on all working days (soft) |
| BC-05 | Planned Quantity | No overproduction beyond 1% tolerance |
| BC-06 | Exclusive Product Guarantee | Single-line products must complete |
| BC-07 | Result Completeness | All products must be scheduled |
| BC-08 | Crew Flexibility | Release crews when products complete |
| BC-09 | Product Continuity | Same product on same line must be continuous |
| BC-10 | Changeover Rules | Product changeover with capacity limits |

### Regional Constraints

#### Old Packaging Area (030201, 030202, 030210)
- Fixed crew pairs: pack01+pack02, pack10+pack14
- 3 lines, 2 pairs → always 1 line idle per shift

#### New Packaging Area A (030203, 030204, 030207, 030211)
- Flexible crew assignment
- Max 1 idle line per shift
- 030204 doesn't use pack17

#### New Packaging Area B (030205, 030206)
- Strict double shifts on both lines
- 030205: pack05+pack11
- 030206: pack06+pack13
- Product MT0010010082 prioritized on 030205

#### New Packaging Area C+D (030208, 030209, 030212, 030213)
- Must maintain "2 double + 2 single" pattern
- Flexible crew allocation across lines

## Key Formulas

### Capacity Utilization
```
Utilization = shift_output / standard_capacity × 100%
```

### Changeover Calculation
```
first_product_output = remaining_first_product
available_capacity = standard_capacity - first_product_output
changeover_usable = available_capacity × 0.9  # 10% loss
second_product_output = min(changeover_usable, remaining_second_product)
total_output = first_product_output + second_product_output
```

### Tons to Bottles Conversion
```
bottles = tons × 500 × 2124 / spec
```

## Output Files

### 1. Schedule CSV (`results/schedule.csv`)
Reference format with lines as columns, compatible with original system.

### 2. Standard CSV (`results/schedule_standard.csv`)
One row per shift assignment with columns:
- Date, Shift, Week, Weekday
- Line Code, Line Name
- Product Code, Product Name
- Crew Code, Crew Name
- Standard Capacity, Shift Output, Cumulative Output
- Utilization, Is Changeover, Status

### 3. Report (`results/report.txt`)
Text report containing:
- Capacity utilization statistics
- Product completion status
- Crew workload distribution
- Warnings and errors

## Testing

### Run Unit Tests

```bash
pytest tests/unit/ -v
```

### Run Integration Tests

```bash
pytest tests/integration/ -v
```

### Run All Tests

```bash
pytest -v
```

## Performance Metrics

Based on test with reference data:

- **Total Assignments**: ~305 shifts
- **Average Utilization**: ~99.7%
- **Completion Rate**: ~95%
- **Changeover Rate**: ~2-3%
- **Processing Time**: < 1 second

## Known Limitations

1. **Crew Assignment Tracking**: Some scenarios may result in multiple assignments of the same crew in one shift (requires additional tracking logic)
2. **Continuity Enforcement**: Product continuity may not be strictly enforced in all edge cases
3. **Priority Constraint**: Some priority period constraints may be infeasible due to capacity limits
4. **Regional Rules**: Advanced regional rules may need refinement for edge cases

## Future Enhancements

- [ ] Improve crew availability tracking during shift scheduling
- [ ] Add backtracking for better constraint satisfaction
- [ ] Implement multi-objective optimization (e.g., minimize changeovers)
- [ ] Add support for maintenance windows
- [ ] Enhanced visualization of scheduling results
- [ ] Real-time rescheduling capability

## Development Guidelines

### Code Style

- Follow PEP 8
- Use type hints
- Document complex logic
- Write tests for new features

### Contributing

1. Create feature branch
2. Implement changes with tests
3. Ensure all tests pass
4. Update documentation
5. Submit pull request

## License

Internal use only - Maotai Production System

## Contact

For questions or issues, contact the development team.

---

**Version**: 1.0.0
**Last Updated**: 2025-10-13

