#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
python src/01_generate_data.py          # synthetic raw extracts (+ hidden ground truth)
python src/02_build_customer360.py      # clean, match, golden record, DQ metrics, star schema
python src/03_sql_validation.py         # SQL layer + reconciliation with Pandas
python src/04_build_excel.py            # glossary + scorecard workbook
python src/05_make_preview.py           # QA preview chart
python src/06_build_flat_table.py       # single flat file for Power BI in the browser
echo "Done. Load powerbi/data/*.csv into Power BI Desktop - see docs/powerbi_build_guide.md"
