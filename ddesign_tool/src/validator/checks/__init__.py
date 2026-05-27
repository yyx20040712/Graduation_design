"""
validator/checks/ — 内置检查器

每个检查器是一个独立类,实现 run(cls, cfg, flow, quality, mode) → CheckResult.
新模组自动继承所有检查器,无需额外配置.
"""
