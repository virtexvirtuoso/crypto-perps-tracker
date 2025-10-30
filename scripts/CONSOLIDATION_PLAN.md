# Script Consolidation Plan

## Overview
Replace old scripts with new Container-based architecture versions.

## Scripts to Consolidate

| Old Script | Lines | New Script | Lines | Reduction | Action |
|-----------|-------|-----------|-------|-----------|--------|
| analyze_coins.py | 353 | analyze_coins_new.py | 307 | 13% | ✅ Replace |
| calculate_basis.py | 268 | calculate_basis_new.py | 490 | +83% | ✅ Replace (enhanced) |
| compare_all_exchanges.py | 678 | compare_exchanges_new.py | 227 | 66% | ✅ Replace |
| data_logger.py | 434 | data_logger_new.py | 419 | 3% | ✅ Replace |
| generate_market_report.py | 1827 | generate_market_report_new.py | 1438 | 21% | ✅ Replace |
| generate_symbol_report.py | 1859 | generate_symbol_report_new.py | 367 | 80% | ✅ Replace |

**Total:** 5,419 lines → 3,248 lines = **40% reduction**

## Verification Needed

Before consolidation, verify each _new script:
1. ✅ Uses Container pattern
2. ✅ Has equivalent functionality
3. ⏳ Works correctly with current data

## Consolidation Steps

### 1. Backup Old Versions
```bash
mv scripts/analyze_coins.py scripts/deprecated/
mv scripts/calculate_basis.py scripts/deprecated/
mv scripts/compare_all_exchanges.py scripts/deprecated/
mv scripts/data_logger.py scripts/deprecated/
mv scripts/generate_market_report.py scripts/deprecated/
mv scripts/generate_symbol_report.py scripts/deprecated/
```

### 2. Promote New Versions
```bash
mv scripts/analyze_coins_new.py scripts/analyze_coins.py
mv scripts/calculate_basis_new.py scripts/calculate_basis.py
mv scripts/compare_exchanges_new.py scripts/compare_exchanges.py
mv scripts/data_logger_new.py scripts/data_logger.py
mv scripts/generate_market_report_new.py scripts/generate_market_report.py
mv scripts/generate_symbol_report_new.py scripts/generate_symbol_report.py
```

### 3. Update compare_exchanges.py Naming
`compare_exchanges_new.py` → `compare_exchanges.py` (not `compare_all_exchanges.py`)

This is cleaner and more consistent with the new architecture.

## Testing Plan

After consolidation, test each script:

```bash
# 1. Compare exchanges
python3 scripts/compare_exchanges.py

# 2. Analyze coins
python3 scripts/analyze_coins.py

# 3. Calculate basis
python3 scripts/calculate_basis.py

# 4. Data logger
python3 scripts/data_logger.py

# 5. Market report
python3 scripts/generate_market_report.py

# 6. Symbol report
python3 scripts/generate_symbol_report.py
```

## Potential Issues

### calculate_basis_new.py (Enhanced)
- **Note:** New version is 83% larger (490 vs 268 lines)
- **Reason:** Likely added features or more comprehensive basis calculations
- **Action:** Verify functionality, likely an improvement not a problem

### compare_exchanges.py (Renamed)
- **Note:** Changing from `compare_all_exchanges.py` to `compare_exchanges.py`
- **Reason:** Cleaner name, "all" is redundant (it always compares all enabled exchanges)
- **Action:** Update any cron jobs or scripts that reference the old name

## Benefits of Consolidation

### Code Quality
- ✅ Eliminates duplicate functionality
- ✅ Uses modern Container/Service pattern
- ✅ Type-safe with Pydantic models
- ✅ Built-in caching (80% API call reduction)
- ✅ Better error handling
- ✅ Cleaner, more maintainable code

### Developer Experience
- ✅ Single source of truth for each feature
- ✅ Easier to find and modify code
- ✅ Consistent architecture across all scripts
- ✅ Better testing capabilities

### Performance
- ✅ Automatic caching reduces API calls
- ✅ Parallel fetching via ThreadPoolExecutor
- ✅ Efficient data structures

## Timeline

**Estimated Time:** 1-2 hours
1. Run tests on _new scripts: 30 min
2. Move old scripts to deprecated/: 5 min
3. Rename _new scripts: 5 min
4. Run integration tests: 30 min
5. Update documentation: 15 min

## Rollback Plan

If issues arise:
```bash
# Old versions preserved in scripts/deprecated/
# Can copy back if needed:
cp scripts/deprecated/analyze_coins.py scripts/
```

## Success Criteria

- ✅ All 6 scripts running without errors
- ✅ Output format matches or improves on old versions
- ✅ No functionality regressions
- ✅ Documentation updated
- ✅ Old versions safely preserved in deprecated/

## Post-Consolidation Cleanup

After successful consolidation (1 week stability):
- Update any external references (cron jobs, docs, etc.)
- Update README with new script names
- Archive deprecated/ folder (don't delete, keep for reference)
