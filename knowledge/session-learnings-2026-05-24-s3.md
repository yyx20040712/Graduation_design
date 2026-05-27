# 2026-05-24 (会话3) 学习记录 — 矿井水模组全量审计 + v4.3 标签自包含

> **日期**: 2026-05-24 | **测试**: 327 passed | **修改文件**: 40+

---

## 一、成本估算修复 (3项)

### Bug 1: 高程/集配水节点无法提取尺寸
| 项目 | 内容 |
|------|------|
| 文件 | `cost_estimator.py` |
| 根因 | `jcws_smbg`/`gdys_stss` 是 elevation 节点，`is_io_node()` 对 elevation stage 返回 False |
| 修复 | `_NO_CIVIL` 新增 `jcws_smbg`, `gdys_stss` |

### Bug 2: 维度别名缺失
| 项目 | 内容 |
|------|------|
| 根因 | `_val()` CN_ALIASES 缺少 `井径→池径`, `渠长→池长`, `渠宽→池宽` |
| 修复 | CN_ALIASES + ENG_FALLBACK 均补充映射 |

### Bug 3: gaomidu 方案浏览器 NameError
| 项目 | 内容 |
|------|------|
| 根因 | `_vectorized_compute` dtype 字段名为 `S_dry_SS`，赋值写 `S_dry_SS_total` → ValueError |
| 修复 | 统一为 `S_dry_SS_total` / `S_dry_chem_total`，同步 `dimension_labels.py` VEC_FIELD_TABLE |
| 连带 | D_PAC 20→40 mg/L, R_sludge 0.05→0.03, X_r 约束 → ≥0 (永真, 低SS时仅警告) |

---

## 二、消除 _DEFAULT_HEAD_LOSS 硬编码 (v4.2)

| 前 | 后 |
|----|-----|
| `elevation_calculator.py` 43行硬编码字典 | 1行回退值 `0.2m` |
| 仅 2 个 mod.json 有 `elevation_loss` | **全部 31 个** mod.json 均有 |
| 新增模组需修改 Python 代码 | 只需编辑 `mod.json` |

**格式**: `"elevation_loss": {"value": 0.30, "formula": "经验值: 0.30m"}`
**批量**: 62 files (31 mods × 2 目录)

---

## 三、矿井水模组全量审计重写 (4 模组)

### 3.1 矿井水调节池 (kw_tiaojiechi) v2.0
| 修改项 | 修正前 | 修正后 | 规范 |
|--------|--------|--------|------|
| L/B 约束 | 1.5~3.0 | **2.0~4.0** | 2:1~4:1 |
| HRT 约束 | ≥HRT-0.5 | **6~12h 范围检查** | |
| H_total | h_eff+h_super | **h_eff+h_super+h_pit** | (4-5) |
| 积泥坑 | ❌ | ✅ V_pit = B×h_pit²/(2i), 校核 | (4-8) |
| 污泥参数 | 硬编码 P=85% ρ=1.4 | **参数化 P_sludge 90~95%, ρ=1.0~1.2** | |
| k 系数 | ❌ | ✅ 0.8~1.5 | |
| Stokes 沉降 | ❌ | ✅ u_s = g(ρ_s-ρ)d²/(18μ) | (4-1) |
| 出水管径 | ❌ | ✅ D_out = √(4Q/(π·v_out)) | (4-10) |
| 堰口负荷 | ❌ | ✅ ≤2.9 L/(s·m) | |
| n 范围 | min=2 max=6 | **min=4 max=8 step=2** | 用户要求 4/6/8 |

### 3.2 平流沉砂池 (kw_chenshachi) v2.0
| 修改项 | 修正前 | 修正后 | 规范 |
|--------|--------|--------|------|
| **有效水深** | 2.0~3.5m | **0.25~1.0m, ≤1.2m** | H≤1.2 强制 |
| **堰口负荷** | ≤200 L/(s·m) | **≤2.9 L/(s·m)** | 差 69 倍 |
| mod.json 键名 | `"t"`, `"B"` | `"t_stay"`, B 改为派生 | 对齐代码 |
| 沉砂量系数 | 0.02 m³/1000m³ | **κ=0.03~0.05 L/m³ (参数化)** | |
| 流速校核 | ❌ | ✅ 0.15~0.30 m/s | (4-13) |
| B≥0.6m | ❌ | ✅ | |
| B/H 宽深比 | ❌ | ✅ 1.0~2.0 | |
| 排砂管径 | ❌ | ✅ D≥200mm | |
| 堰长计算 | ❌ | ✅ L_weir_req = Q×1000/q | (4-22) |

### 3.3 磁种混凝反应池 (kw_ningjiao) v2.0
| 修改项 | 修正前 | 修正后 |
|--------|--------|--------|
| **功能分区** | 2区 (混合+絮凝) | **4区** (混合+磁种混合+絮凝+熟化) |
| **磁种系统** | ❌ | ✅ 投加/保有/补充/γ_mag ≥ 0.5 |
| **GT校核** | 单一组合 | 4区独立 GT₁~GT₄ |
| **功率计算** | 无修正 | k_ρ密度修正 + 絮凝区×1.2 |
| **出水管** | ❌ | ✅ D_out |
| **形状校核** | 整体 L/B | 4区独立 L_i/B 0.8~1.5 |
| PAC 范围 | 10~60 | **50~100 mg/L** |
| 絮凝时间 | 15~30min | **3~6min** |
| 参数数 | 10 | **22** |

### 3.4 磁盘分离机 (kw_cifenli) v2.0
| 修改项 | 修正前 | 修正后 |
|--------|--------|--------|
| **设计模型** | 简化过滤面积 | **全磁盘分离机物理模型** |
| 约束数 | 1 (过滤速度) | **4** (t_disk/v_disk/q/v_line) |
| D_disk | 1.5~3.0m | **0.6~1.5m** |
| δ | 30~80mm | **20~30mm** |
| 新增计算 | — | A_total/L_channel/v_line/设备外形/功率 |
| mod.json 键名 | `"v_filter"` | `"v_filt"` → 替换为规范参数 |

---

## 四、v4.3: 向量化字段标签模组自包含

### 问题
`dimension_labels.py` VEC_FIELD_TABLE (138 行) 集中管理所有模组的 numpy 字段→中文标签映射。新增模组必须修改此文件。

### 方案
| | 迁移前 | 迁移后 |
|---|--------|--------|
| VEC_FIELD_TABLE | 138 行 | **48 行**共享回退 (L/B/H/D/val_*) |
| 模组标签 | ❌ | **labels.json** (vec_fields) |
| 新模组 | 需编辑 dimension_labels.py | 只需创建 labels.json |

### labels.json 格式
```json
{
  "vec_fields": {
    "V_mix": ["V_mix", "混合区容积", "m³"],
    "v_axial": ["v_axial", "斜管轴向流速", "m/s"]
  }
}
```

### 加载机制 (已有)
`_build_dynamic_labels()` → `mgr.load_labels(mod_id)` → `labels["vec_fields"]` → 合并

### 已迁移: 11 模组 (22 files)

---

## 五、改动文件汇总

| 文件 | 改动 | 类型 |
|------|------|------|
| `cost_estimator.py` | +8 | _NO_CIVIL + CN_ALIASES + ENG_FALLBACK |
| `elevation_calculator.py` | -42/+3 | 删除 _DEFAULT_HEAD_LOSS → 单值回退 |
| `dimension_labels.py` | -90/+30 | VEC_FIELD_TABLE 138→48 行 (v4.3) |
| `mod_schema.json` | +12 | process_stage + elevation_loss schema |
| `MOD_SPEC.md` | +25 | labels.json 规范 + 注册清单更新 |
| 31× `mod.json` | +2 each | 添加 elevation_loss |
| `gaomidu/__init__.py` | ~10 | 3 轮修复: X_r/S_dry_SS/D_PAC/R_sludge |
| `gaomidu/discretization.json` | ~5 | 同步约束名 |
| `kw_tiaojiechi/*` (3 files) | 重写 | v2.0 矿井水调节池 |
| `kw_chenshachi/*` (3 files) | 重写 | v2.0 平流沉砂池 |
| `kw_ningjiao/*` (3 files) | 重写 | v2.0 磁种混凝反应池 |
| `kw_cifenli/*` (3 files) | 重写 | v2.0 磁盘分离机 |
| 11× `labels.json` (22 files) | 新建 | v4.3 向量化标签自包含 |

---

> **记录者**: Sisyphus | **版本**: v4.3 | **测试**: 327 passed | **修改文件**: 70+
