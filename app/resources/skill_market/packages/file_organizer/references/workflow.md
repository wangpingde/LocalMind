# 文件整理标准流程

1. **盘点**：`list_files` + `run_skill_script(preview.py)` 了解文件规模与扩展名分布。
2. **预览**：`batch_process_files` 设置 `dry_run=true`。
3. **执行**：用户确认后 `dry_run=false`。
4. **报告**：`write_file` 输出 `outputs/organize_report.md`，可引用 `assets/report_template.md`。
