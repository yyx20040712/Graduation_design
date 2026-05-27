"""
dimension_formulas.py — 维度公式 + 分类库(单一数据源, v4.1)

所有维度/参数的公式和分类均在此定义.mod 调用 add_dimension() 时若未显式传入
formula=/category=,自动从此字典子串匹配.

使用方式:
  from models.dimension_formulas import (
      DIM_FORMULAS, get_formula,
      DIM_CATEGORIES, get_dimension_category,
      PARAM_CATEGORIES, get_param_category,
  )
"""

# ═══════════════════════════════════════════════════════════════════
# 维度名 → 公式 (key 为 add_dimension 的 name 参数,支持子串匹配)
# ═══════════════════════════════════════════════════════════════════

DIM_FORMULAS: dict = {
    # ── 通用 ──
    "池数": "n = 用户设定 (≥2,保证冗余)",
    "有效容积": "V = Q_max × HRT / 60",
    "总有效容积": "V_total = n × V_single",
    "单池有效容积": "V_single = V_total / n",
    "实际有效容积": "V_eff = L × B × h_eff",
    "池长": "L = √(V / h_eff)",
    "池宽": "B = V / (L × h_eff)",
    "总高度": "H = h_eff + h_super",
    "有效水深": "h_eff = 设计规范推荐值",
    "超高": "h_super ≥ 0.3m (GB50014)",
    "设计流量": "Q = 上游来水累计",
    "单池设计流量": "Q_single = Q_total / n",
    "实际停留时间": "HRT_actual = V / Q",
    "表面负荷": "q' = Q / A",
    "实际表面负荷": "q'_actual = Q / A_actual",
    "径深比": "D/h₂ = 池径 / 有效水深",
    "长宽比": "L/B = 池长 / 池宽",
    "宽高比": "B/H = 池宽 / 总高度",
    "堰负荷": "q_weir = Q / L_weir",
    "流速": "v = Q / A",
    "实际流速": "v_actual = Q / A_actual",
    "面积": "A = V / h_eff",
    "总面积": "A_total = n × A_single",
    "容积": "V = Q × HRT",
    "concrete_m3": "V_conc = 2(L+B)×t_wall×h + L×B×t_floor",
    "池底标高": "Z_bottom = Z_water - h_eff",
    "水面标高": "Z_water = Z_upstream - h_loss",
    "地面标高": "Z_ground = 用户设定",
    "上游水面标高": "Z_upstream = 上一构筑物水面标高",
    "埋深": "h_bury = Z_ground - Z_bottom",
    # ── 格栅 ──
    "过栅流速": "v = Q / (n × b × h)",
    "栅前流速": "v₁ = Q / (B₁ × h)",
    "水头损失": "h = ξ × v² / (2g)",
    "过栅水头损失": "h₁ = β(s/b)^(4/3) × v²/(2g) × sinα × k",
    "栅条形状系数": "β = 2.42(矩形) / 1.97(半圆) / 1.83(圆形)",
    "阻力系数": "ξ = β × (s/b)^(4/3)",
    "栅条间隙比指数": "(s/b)^(4/3) — s=栅条宽度, b=栅条间隙",
    # ── 管道水头损失 ──
    "沿程水头损失": "h_f = (n·v/R^(2/3))² × L",
    "局部水头损失": "h_m = ξ × v² / (2g)",
    "管道截面积": "A = πD²/4",
    "水力半径": "R = D/4 (满流)",
    "所需坡度": "i = (n×v/R^(2/3))²",
    # ── 沉淀 ──
    "沉淀面积": "A = Q / q'",
    "实际沉淀面积": "A_actual = n × πD²/4",
    # ── 过滤 ──
    "过滤面积": "A = Q / v_filter",
    "单格面积": "A_single = A_total / N",
    "滤速": "v_filter = Q / A",
    "强制滤速": "v_force = Q / ((N-1)×A_single)",
    "反冲洗水量": "V_bw = q_bw × A × t_bw",
    "冲洗水占比": "r_bw = V_bw / V_filtered",
    # ── 污泥 ──
    "固体通量": "G = DS / A",
    "污泥负荷": "Nₛ = Q×S₀ / (V×X)",
    "需氧量": "O₂ = a'×Q×Sᵣ + b'×V×X",
    "日产泥量": "Px = Y×Q×Sᵣ - Kd×V×X",
    "砂斗容积": "V_hopper = πh/3(R²+r²+Rr)",
    "贮泥容积": "V_sludge = S_dry / (ρ×(1-P))",
    "日湿污泥量": "S_wet = S_dry / (ρ×(1-P))",
    # ── 混合/絮凝 ──
    "混合区容积": "V_mix = Q × HRT_mix",
    "絮凝区容积": "V_floc = Q × HRT_floc",
    # ── 消毒 ──
    "紫外剂量": "D_UV = I × t",
    # ── 搅拌 ──
    "搅拌功率": "P = P_density × V",
    # ── 进水渠道 (chenshachi) ──
    "进水渠宽": "B渠 = 用户设定 (0.5~2.0m)",
    "进水渠水深": "h渠 = A渠/B渠 = Q₁/(v渠×B渠) (4-27)",
    "进水渠断面": "A渠 = Q₁/v渠 (4-26)",
    "进水流速": "v渠 = 设计规范推荐 1.0 m/s",
    "进水直段长度": "L直 = max(7×B渠, 4.5) (4-28)",
    "出水渠宽": "B出 = 2×B渠 (4-29)",
    # ── 砂斗 (chenshachi) ──
    "砂斗上口直径": "d_upper = 0.5×D",
    "锥体高度": "h₄ = (d_upper−dr)/(2×tanθ) (3-27)",
    "圆柱段高度": "h_cyl = ceil((V_hopper−V_cone)/A_upper, 0.1)",
    "砂斗所需容积": "V_hopper = V_sand×T_clean×1.5 (3-25)",
    "锥体实际容积": "V_cone = πh₄/3(R²+Rr+r²) (圆台)",
    "圆柱储砂容积": "V_cyl = π(d_upper/2)²×h_cyl",
    "砂斗总容积": "V_storage = V_cone + V_cyl",
    "每日沉砂量": "V_sand = (Q_avg/n)×X/10⁶ (3-24)",
    # ── 调节池 / 流量 ──
    "设计 HRT": "HRT = V_eff / Q (实际水力停留时间)",
    "单池设计流量": "Q_per_pool = Q_avg_hourly / n",
    "搅拌总功率": "P = P_density × V_total (单位容积搅拌功率×总容积)",
    "搅拌设备功率": "P = P_density × V (单位容积功率×容积)",
    # ── 格栅通用 ──
    "栅槽总长": "L_total = L1 + L2 + L3 (进水段+栅槽+出水段)",
    "栅槽宽度": "B = 按过栅流速和栅前水深确定",
    "栅条间隙数": "n = Q_max / (b × h × v) (间隙数量)",
    "栅后总高": "H = h + h_super + h_loss (水深+超高+水头损失)",
    "栅渣量": "W = Q_avg × W1 / 1000 (日栅渣量 m³/d)",
    "清渣方式": "W>0.2 → 机械清渣, W≤0.2 → 人工清渣",
    # ── UV消毒 ──
    "灯管排数": "N_rows = ceil(D_design / D_per_row)",
    "灯管总数": "N_total = N_rows × N_per_row",
    "渠道总长": "L_total = N_rows × L_per_row + L_inlet + L_outlet",
    "渠道宽度": "B = Q / (v × h_eff) (满足流速0.15~0.7m/s)",
    "渠宽": "B = Q / (v × h) (过水断面宽)",
    # ── 滤池 ──
    "滤池格数": "n = 用户设定 (≥2, 保证反洗时强制滤速不超限)",
    "滤池总高度": "H = h_eff + h_support + h_under + h_super",
    # ── 污泥通用 ──
    "池径": "D = ceil(√(4×A/π), 0.5) (圆形池最小5m)",
    "浓缩时间": "T = 设计规范推荐 12~24h",
    "污泥含水率": "P = 1 - DS/(ρ×Q_wet)",
    "泵台数": "n = n_work + n_standby (工作+备用)",
    "管径": "D = √(4Q/(πv)) (按经济流速计算)",
    "总泵送能力": "Q_total = n_work × Q_single ≥ Q_design",
    "输送扬程": "H = H_st + h_loss (静扬程+水头损失)",
    "输送功率": "P = γ·Q·H/(1000·η) (轴功率kW)",
    # ── 污泥消化 ──
    "消化温度": "T = 设计规范 33~35°C (中温消化)",
    "消化时间": "t = 设计规范 20~30d",
    "产气率": "q = 0.3~0.5 m³/kgVS (中温消化)",
    "沼气产量": "V_biogas = VS_degraded × q (m³/d)",
    "VS降解量": "VS_deg = VS_in × η_VS (kg/d)",
    "VS降解率": "η_VS = 设计规范 40~50%",
    # ── 污泥脱水 ──
    "设备类型": "equip_type: 0=带式压滤机, 1=离心脱水机",
    "单机处理量": "q_cap = 设计规范 5~60 m³/h",
    "脱水机台数": "n = ceil(Q_wet / q_cap) + 1(备用)",
    "运行时间": "T_run = Q_wet / (n × q_cap) (h/d)",
    "PAM投加量": "m_PAM = dosage × DS / 1000 (kg/d)",
    "PAM溶液量": "V_sol = m_PAM / concentration (L/d)",
    # ── 污泥干化 ──
    "干化方式": "method: 0=热干化, 1=太阳能干化",
    "蒸发水量": "Q_evap = Q_wet×(P_in-P_out)/(1-P_out)",
    "热功率": "P_thermal = Q_evap × h_vap / η (kW)",
    "综合能耗": "E = P_thermal × 24 / DS (kWh/tDS)",
    "热效率": "η = 实际蒸发量/理论蒸发量",
    "热风温度": "T_air = 设计规范 120~250°C",
    # ── 泵站 ──
    "静扬程": "H_st = Z_out - Z_in (出水标高-进水标高)",
    "总扬程": "H = H_st + h_loss_suction + h_loss_discharge + h_outlet",
    "轴功率": "P_shaft = γ·Q·H/(1000·η) (水泵轴功率kW)",
    "备泵": "n_standby = 1 (n_work≤4) / 2 (n_work>4)",
    # ── 配水井 ──
    "堰上水头": "h_weir = (Q/(C×L))^(2/3) (薄壁堰公式)",
    # ── 磁分离 / 混凝 ──
    "磁盘数量": "n = max(9, ceil(A_needed/A_per_disk))",
    "磁盘直径": "D = 设备规格 0.8~1.2m",
    "磁盘间隙": "δ = 设计取值 20~30mm",
    "设备长度": "L = n × δ + L_end (盘组+端部)",
    "设备宽度": "B = D + 2×δ_side (盘径+侧隙)",
    "设备高度": "H = D + δ_top + δ_bottom (盘径+顶底隙)",
    "总装机功率": "P_total = Σ(P_drive + P_backwash + P_aux)",
    "表面负荷": "q = Q / A_total (m³/(m²·h))",
    "实际表面负荷": "q_actual = Q / A_actual (校核值)",
    "流道流速": "v = Q / A_channel (m/s)",
    "流道停留时间": "t = L_channel / v (s)",
    "外缘线速度": "v_line = π·D·ω/60 (m/s)",
    "磁场强度": "B₀ = 磁盘表面磁场 (0.2~0.5T)",
    "PAC日耗量": "m_PAC = D_PAC × Q / 1000 (kg/d)",
    "PAM日耗量": "m_PAM = D_PAM × Q / 1000 (kg/d)",
    "磁种保有量": "M = V_cell × D_mag / 1000 (kg)",
    "磁种日补充量": "M_supply = n × M × r_loss (kg/d)",
    "磁种质量比": "γ = D_mag / (SS + D_PAC×κ) (磁种/污染物)",
    "密度修正系数": "k_ρ = ρ_mix / ρ_water (含磁种混合液密度比)",
    # ── 紫外补充 ──
    "实际剂量": "D_actual = I_avg × t (实际紫外剂量 mJ/cm²)",
    "设计剂量": "D_design = 规范推荐 40~100 mJ/cm²",
    "综合衰减系数": "k = k_aging × k_foul (老化×污染)",
    "有效透光率": "T_eff = (T254/100)^n_T (灯管老化修正)",
    "平均光强": "I_avg = I₀ × T_eff × e^(-k×d) (Beer-Lambert)",
    "接触时间": "t = L_channel / v (紫外接触时间 s)",
    # ── AAO ──
    "内回流比": "Ri = 设计规范 100~400% (缺氧→厌氧)",
    "内回流量": "Q_ri = Ri × Q_avg (m³/d)",
    "回流污泥量": "Q_r = R × Q_avg (外回流 m³/d)",
    "总HRT": "HRT_total = (Va+Vn+Vo) / Q (总水力停留时间)",
    "污泥回流比": "R = 设计规范 50~100% (二沉池→厌氧)",
    "污泥龄": "θc = V×X / Px (污泥停留时间 d)",
    "系列数": "n = 用户设定 (2~4)",
    # ── CASS 补充 ──
    "剩余污泥总量": "Px_total = Px_bio + Px_nbio (kg/d)",
    "剩余生物污泥": "Px_bio = Y·Q·(S0-Se) - Kd·V·X·f (kgVSS/d)",
    "剩余非生物污泥": "Px_nbio = Q·(SS_in/1000·(1-f_b) - SS_out/1000) (kg/d)",
    "单池滗水流量": "Q_decant = V_eff × λ / t_d (m³/h)",
    "反硝化产氧": "O₂_dn = 2.86 × (TN_load - N_synth) (kgO2/d)",
    "安全距离": "H_safe = H_max - H_decant - H_sludge (≥1.5m)",
    "实际污泥龄": "θc_actual = V·X / Px_total (实际 d)",
    "污泥层高度": "H_sludge = H_max × X × SVI / 10⁶ (m)",
    "滗水高度": "H_decant = H_max × λ (m)",
    "水温衰减系数": "KdT = Kd20 × θ^(T-20)",
    # ── 初沉池/二沉池 ──
    "刮泥机线速": "v = π·D·n/60 (外围线速 ≤ 3m/min)",
    "每日干污泥": "S_dry = Q_avg × (SS_in-SS_out)/1000 × (1-P) (kg/d)",
    "每日湿污泥": "S_wet = S_dry / ((1-P)×ρ) (m³/d)",
    "池底坡降": "h₄ = (D-d_center)/2 × tan(θ) (锥体高度 m)",
    "泥斗高度": "h₅ = (R1-R2) × tan(θ) (泥斗锥体高 m)",
    "缓冲层": "h₃ = 设计规范 0.3~0.5m",
    "MLSS浓度": "X = 设计规范 2.5~4.5 g/L",
    "回流比": "R = Qr/Q (设计规范 50~100%)",
    # ── 管道/高程 ──
    "充满度": "h/D = Q/(Q_full) → 查水力计算表",
    "管段长度": "L = 平面布置确定",
    "设计坡度": "i = (n·v/R^(2/3))²",
    "管底标高": "Z_bottom = Z_water - h_eff (管内底标高)",
    # ── 矿井水通用 ──
    "混凝土量估算": "V_conc = (L+2)(B+2)(H+tf+0.5)×n×1.2 (矩形土建)",
    "砂斗总数": "n_total = n_hoppers_per_cell × n (格数×每格个数)",
    "磁盘间距": "δ = 设计取值 20~30mm (盘间流道)",
    "变化系数": "Kz = Q_max / Q_avg (总变化系数)",
    "涌水量": "Q_avg = 矿井日均涌水量 (m³/d)",
    # ── 混凝反应池 ──
    "混合区长度": "L₁ = V₁ / (B×h_eff) = Q₁×t₁ / (B×h_eff)",
    "熟化区长度": "L₄ = V₄ / (B×h_eff)",
    "磁种混合区长度": "L₂ = V₂ / (B×h_eff)",
    "絮凝区长度": "L₃ = V₃ / (B×h_eff)",
    # ── 滤池 ──
    "单格宽度": "B = 按滤速和面积确定",
    "单格长度": "L = A_single / B",
    "滤头数量": "N = A_single / a_head (按配水均匀性布置)",
    "渠道数": "n = 按流量分配确定 (≥2)",
    # ── 污泥泵站/输送 ──
    "单泵功率": "P = γ·Q·H/(1000·η) (单台轴功率 kW)",
    "扬程": "H = H_st + h_loss (静扬程+水头损失)",
    "电机功率": "P_motor = P_shaft / η_motor (电机功率 kW)",
    "进泥干固量": "DS_in = Q_wet × (1-P) × ρ (kg/d)",
    "进泥含水率": "P_in = 上游来泥含水率 (小数)",
    "出泥干固量": "DS_out = DS_in × η (考虑回收率 kg/d)",
    "出泥含水率": "P_out = 目标含水率 (按工艺要求)",
    # ── 污泥干化/脱水/消化 ──
    "减量率": "η = 1 - DS_out/DS_in × 100%",
    "总热耗": "Q_heat = Q_evap × h_vap / η_thermal (kW)",
    "折合标煤": "m_coal = Q_heat × 24 / q_coal (t/d)",
    "PAM溶液流量": "Q_sol = m_PAM / c (L/h, c=浓度g/L)",
    "甲烷产量": "V_CH4 = VS_degraded × 0.35 (m³/kgVS)",
    "水泵总台数": "n_total = n_work + n_standby",
    # ── 通用数学项 ──
    "(s/b)^(4/3)": "栅条间隙比指数,s=栅条宽(mm), b=间隙(mm)",
    "单台流量": "q = Q_total / n (均分流量)",
    "格栅台数": "n = 设计规范 ≥2台 (1用1备)",
    # ── 巴氏计量槽 ──
    "上游水深": "h_a = 按喉道宽度和流量查标准表 (m)",
    "下游水深": "h_b = h_a × (1-S) (淹没度法计算 m)",
    # ── 最后补充 ──
    "BOD负荷": "Nₛ = Q×S₀/(V×X) (kgBOD5/(kgMLSS·d))",
    "池底坡度": "i = Δh/L (池底高差/长度,≥1%)",
    # ── 矿井水 / 补充公式 ──
    "积泥坑深度": "h_pit = 设计取值 0.5~1.0m",
    "积泥坑有效容积": "V_pit = L × B × h_pit",
    "贮泥容积需求": "V_needed = DS / (ρ×(1-P))",
    "Stokes沉降速度": "u_s = g(ρ_s-ρ_w)d²/(18μ)",
    "喉道宽度": "b = 按巴歇尔槽标准尺寸选择",
    "流量系数": "C = 按喉道宽度查标准表",
    "指数": "n = 按喉道宽度查标准表",
    "淹没度": "S = h_b / h_a",
    "弗劳德数": "Fr = v / √(g·h)",
    "浓缩面积": "A = DS / q_solid (固体通量法)",
    "固体负荷": "q_solid = DS / A (实际)",
    "分离液量": "Q_sep = Q_wet_in - Q_wet_out",
    "固体回收率": "η = 1 - SS_supernatant / SS_in",
    "回流污泥浓度": "X_r = W_s×10⁶ / Q_r",
    "过滤总水头损失": "H_loss = ΣΔh (各阶段累计)",
    "鼓风机风量": "Q_blower = max(Q_g1, Q_g2) × K (安全系数1.2)",
    "冲洗水泵流量": "Q_pump = Q_w2 + Q_w3",
    "设计充水比": "λ_design = 用户设定值 (0.2~0.4)",
    "实际充水比": "λ_actual = Q_avg × Tc / (24 × n × V_eff)",
    "滗水器堰口长度": "L_w = Q_h / (q_L × 3.6), q_L=25 L/(s·m)",
    "V型槽断面积": "A_V = 根据冲洗强度计算",
    "扫洗孔总面积": "A_孔 = Q_s / (μ × √(2gH))",
    "单孔面积": "a_孔 = πd²/4",
    "每侧孔数": "n_孔 = A_孔 / a_孔 (≥20个/侧)",
    "总吸附面积": "A_total = 2 × πD²/4 × n_disks",
    "流道断面面积": "A_ch = B_ch × h_ch",
    "流道有效长度": "L_ch = 盘片组总厚度",
    "磁场强度": "B₀ = 磁盘表面磁场强度 (0.2~0.5T)",
    "外缘线速度": "v_line = π × D_disk × n_rpm / 60",
    "总装机功率": "P_total = Σ(P_drive + P_backwash + P_aux)",
    "轴功率": "P_shaft = γ × Q × H / (1000 × η)",
    "静扬程": "H_st = Z_out - Z_in (几何高差)",
    "吸水管水力坡度": "i_s = (n × v / R^{2/3})²",
    "出水管水力坡度": "i_d = (n × v / R^{2/3})²",
    "磁种保有量": "M_mag = V_cell × ρ_mag × γ_mag × k_ρ",
    "磁种质量比": "γ_mag = m_mag / m_water",
    "密度修正系数": "k_ρ = ρ_sludge / ρ_water",
    "冲洗水占比": "η_w = W_w / V_filtered × 100%",
    "总停留时间": "t_total = t_mix + t_floc + t_settle",
    "反冲洗总历时": "t_bw = t_g1 + t_g2 + t_w2 + t_w3 + t_gs (各阶段和)",
    "日有效工作时间": "T_w = 24 - t_bw (扣除反冲洗)",
    "合并湿泥量": "Q_wet = Σ Q_wet_i (各源累加)",
    "合并干固量": "DS_merged = Σ DS_i (各源累加)",
    "合并含水率": "P_merged = 1 - ΣDS / (ρ × ΣQ_wet)",
    "合并VS比": "VS_merged = Σ(DS × VS) / ΣDS",
    "日产干泥量": "S_dry = Q_avg × (SS_in - SS_out) / (1-P)",
    "日产湿泥体积": "S_wet = S_dry / ((1-P) × ρ)",
    "日湿污泥量": "V_sludge = DS / ((1-P_moisture) × ρ)",
    "日去除干固体": "W_SS = Q_avg × (SS_in - SS_out) / 1000",
    "进泥湿泥量": "Q_wet_in = 上游污泥流湿泥量",
    "出泥湿泥量": "Q_wet_out = Q_wet_in × (1-P_in)/(1-P_out)",
    "出泥含水率": "P_out = 出口目标含水率",
    "干固体量": "DS = Q_wet × ρ × (1-P)",
    "PAC小时耗量": "m_PAC_h = D_PAC × Q / 1000",
    "PAM小时耗量": "m_PAM_h = D_PAM × Q / 1000",
    "磁种日补充量": "M_supply = M_mag × η_loss",
    "总变化系数": "Kz = 2.7 / Q_d^{0.11} (Q_d in L/s)",
    "日湿污泥量 V_sludge": "V_sludge = DS / ((1-P) × 1000)",
    "单次冲洗水量 W_w": "W_w = q_bw × A × t_bw / 60",
    "堰口负荷": "q_weir = Q / L_weir (≤ 1.7 L/(s·m))",
    "过滤水头损失": "H_loss = ΣΔh_i (清洁+堵塞+管渠水损)",
    "吸水管沿程水损": "h_f = (n × v / R^{2/3})² × L (Manning)",
    "出水管沿程水损": "h_f = (n × v / R^{2/3})² × L (Manning)",
    "设计水平流速": "v_h = 设计规范推荐 (0.15~0.3 m/s)",
    "实际水平流速": "v_actual = Q / A_cross",
    "实际出水流速": "v_out = Q / (πD²/4)",
    "实际堰负荷": "q_weir_actual = Q / L_weir_available",
    "需堰长": "L_weir = Q / q_weir_design (取整)",
    "可用堰长": "L_weir_avail = 实际布置可用的堰长",
    "有效容积 V": "V = Q × HRT (水力停留时间法)",
    "单格总容积": "V_cell = L1 + L2 + L3 + L4 各段容积之和",
    "单斗容积": "V_hopper = πh/3(R²+r²+Rr) (圆台公式)",
    "需砂斗容积": "V_needed = V_sand × T_clean × 1.5 (安全系数)",
    "最小集水池容积": "V_min = 5 × Q_pump × 60 (5min调节容积)",
    "集水池容积": "V_sump = L × B × h_eff",
    "设计总流量": "Q_d = Q_avg × Kz (含变化系数)",
    "单泵流量": "Q_single = Q_total / n (≤单泵额定流量)",
    "气冲流量": "Q_g = q_g × A_single × 3.6 (L/s)",
    "水冲流量": "Q_w = q_w × A_single × 3.6 (L/s)",
    "表扫流量": "Q_s = q_s × B_single × 3.6 (L/s)",
    "流道流速": "v_disk = Q / A_ch",
    "流道停留时间": "t_disk = L_ch / v_disk",
    "实际强制滤速": "v_force = Q / ((N-1) × A_single) — 反洗时",
    "设计滤速": "v_filter = 设计规范推荐 (5~10 m/h)",
    "V型槽始端流速": "v_V = Q_s / A_V",
    "过滤总水头损失 H_loss": "H_loss = ΣΔh (清洁滤料+堵塞+管渠)",
    "排砂管最小管径": "D ≥ 200mm (GB50014 §6.5)",
    "空气干管管径": "D_g = √(4×Q_g/(π×v_g)), v_g=10~15 m/s",
    "水冲干管管径": "D_w = √(4×Q_w/(π×v_w)), v_w=1.5~2.5 m/s",
    "上游直段长度": "L_up ≥ 10 × B_channel",
    "下游直段长度": "L_down ≥ 5 × B_channel",
}


def get_formula(dim_name: str, node_type: str = "") -> str:
    """Look up formula for a dimension name (substring match).

    Priority: mod labels.json > DIM_FORMULAS generic fallback.

    Args:
        dim_name: Dimension display name (Chinese)
        node_type: Optional node type for mod-specific lookup

    Returns:
        Formula string, or empty string if not found
    """
    # 1. Check mod-specific formulas (from labels.json, loaded by ModManager)
    if node_type:
        mod_formulas = _get_mod_formulas(node_type)
        for kw, formula in mod_formulas.items():
            if kw in dim_name:
                return formula

    # 2. Fallback to generic formulas
    for kw, formula in DIM_FORMULAS.items():
        if kw in dim_name:
            return formula
    return ""


def _get_mod_formulas(node_type: str) -> dict:
    """Get per-mod formulas from labels.json (lazy-loaded)."""
    global _mod_formulas_cache
    if node_type in _mod_formulas_cache:
        return _mod_formulas_cache[node_type]
    try:
        from mods.mod_manager import get_mod_manager

        mgr = get_mod_manager()
        mgr.load_all()
        labels = mgr.load_labels(node_type)
        if labels and "formulas" in labels:
            _mod_formulas_cache[node_type] = labels["formulas"]
            return labels["formulas"]
    except Exception:
        pass
    _mod_formulas_cache[node_type] = {}
    return {}


_mod_formulas_cache: dict = {}


# ═══════════════════════════════════════════════════════════════════
# 维度分类
#   "physical"   → 构筑物尺寸(施工建造所需的几何参数)
#   "computed"   → 计算结果(由公式导出的非几何变量)
#   "water_quality" → 水质数据(浓度/去除率,含 "进水"/"出水" 前缀)
# ═══════════════════════════════════════════════════════════════════

DIM_CATEGORIES: dict = {
    # ── physical: 数量 ──
    "池数": "physical",
    "格数": "physical",
    "系列数": "physical",
    "渠道数": "physical",
    "格栅台数": "physical",
    "滤池格数": "physical",
    "磁盘台数": "physical",
    "砂斗个数": "physical",
    "磁盘片数": "physical",
    "栅条间隙数": "physical",
    "滤头数量": "physical",
    "灯管排数": "physical",
    "灯管总数": "physical",
    "泵台数": "physical",
    "泵数量": "physical",
    "脱水机台数": "physical",
    "设备台数": "physical",
    "水泵总台数": "physical",
    "工作泵台数": "physical",
    "备用泵台数": "physical",
    "泵台数": "physical",
    "泵数量": "physical",
    "砂斗个数/格": "physical",
    "砂斗总数": "physical",
    "出水口数": "physical",
    "出水方向数": "physical",
    "磁盘数量": "physical",
    "每侧孔数": "physical",
    "每侧孔数 n_孔": "physical",
    "单孔面积": "physical",
    "滤头数量 N_nozzle": "physical",
    "滤头数量 N_nozzle(单格)": "physical",
    # ── physical: 线性尺寸 ──
    "池径": "physical",
    "池长": "physical",
    "池宽": "physical",
    "直径": "physical",
    "长度": "physical",
    "宽度": "physical",
    "总高度": "physical",
    "有效水深": "physical",
    "超高": "physical",
    "池底坡降": "physical",
    "泥斗高度": "physical",
    "锥体高度": "physical",
    "圆柱段高度": "physical",
    "砂斗深度": "physical",
    "中心管径": "physical",
    "渠宽": "physical",
    "进水渠宽": "physical",
    "出水渠宽": "physical",
    "栅后总高": "physical",
    "滤池总高度": "physical",
    "栅槽宽度": "physical",
    "单格宽度": "physical",
    "砂斗上口直径": "physical",
    "滗水高度": "physical",
    "污泥层高度": "physical",
    "安全距离": "physical",
    "浓缩区高度": "physical",
    "磁盘直径": "physical",
    "磁盘间隙": "physical",
    "灯管长度": "physical",
    "灯管间隙": "physical",
    "排沙口直径": "physical",
    "管径": "physical",
    "进水管径": "physical",
    "进水直段长度": "physical",
    "排砂管": "physical",
    "排砂管最小管径": "physical",
    "喉道宽度": "physical",
    "喉道宽度 b": "physical",
    "流道有效长度": "physical",
    "单格总长": "physical",
    "设备长度": "physical",
    "设备宽度": "physical",
    "设备高度": "physical",
    "混合区长度": "physical",
    "絮凝区长度": "physical",
    "熟化区长度": "physical",
    "磁种混合区长度": "physical",
    "上游直段长度": "physical",
    "下游直段长度": "physical",
    "出水堰总长 L_w": "physical",
    "滗水器堰口长度 L_w": "physical",
    "积泥坑深度": "physical",
    "渠长": "physical",
    "空气干管管径": "physical",
    "水冲干管管径": "physical",
    "吸水管径": "physical",
    "出水管径": "physical",
    "井径": "physical",
    "堰上水头": "physical",
    "V型槽断面积": "physical",
    "扫洗孔总面积": "physical",
    "过水面积": "physical",
    "单台占地面积": "physical",
    "总占地面积": "physical",
    "总吸附面积": "physical",
    "流道断面面积": "physical",
    "单斗容积": "physical",
    "需砂斗容积": "physical",
    "集水池容积": "physical",
    "最小集水池容积": "physical",
    "积泥坑有效容积": "physical",
    "贮泥容积需求": "physical",
    "单格总容积 V_cell": "physical",
    "总有效容积 V_total": "physical",
    "有效容积 V": "physical",
    "池底坡度 i": "physical",
    "池底坡度": "physical",
    "单格总容积": "physical",
    "浓缩面积": "physical",
    # ── physical: 面积 ──
    "沉淀面积": "physical",
    "总过滤面积": "physical",
    "单格面积": "physical",
    "调节池总面积": "physical",
    "沉砂池总面积": "physical",
    "总面积": "physical",
    "单格过滤面积": "physical",
    "出水堰长": "physical",
    "磁盘组长度": "physical",
    "渠道总长": "physical",
    "栅槽总长": "physical",
    "单格长度": "physical",
    "沉淀区面积": "physical",
    "进水渠断面": "physical",
    "进水渠断面积": "physical",
    "进水渠面积": "physical",
    # ── physical: 容积 ──
    "有效容积": "physical",
    "单池有效容积": "physical",
    "总有效容积": "physical",
    "主反应区总容积": "physical",
    "单池主反应区容积": "physical",
    "选择区容积": "physical",
    "单池总有效容积": "physical",
    "混合区容积": "physical",
    "絮凝区容积": "physical",
    "单系列总容积": "physical",
    "污泥区总容积": "physical",
    "砂斗总容积": "physical",
    "锥体实际容积": "physical",
    "圆柱储砂容积": "physical",
    "单池需贮泥容积": "physical",
    "2日贮泥容积": "physical",
    "砂斗所需容积": "physical",
    # ── physical: 比例 / 坡度 ──
    "径深比": "physical",
    "长宽比": "physical",
    "宽高比": "physical",
    "充水比": "physical",
    "池底坡度": "physical",
    # ── computed: 流量/流速 ──
    "设计流量": "computed",
    "单池设计流量": "computed",
    "进水流速": "computed",
    "进水渠水深": "computed",
    "过栅流速": "computed",
    "栅前流速": "computed",
    "流速": "computed",
    "实际流速": "computed",
    "滤速": "computed",
    "强制滤速": "computed",
    "总泵送能力": "computed",
    "液量": "computed",
    "产氧": "computed",
    "日去除": "computed",
    "日产": "computed",
    "日耗量": "computed",
    "小时耗量": "computed",
    "补充量": "computed",
    "保有量": "computed",
    "鼓风机": "computed",
    "冲洗水泵": "computed",
    "单次冲洗": "computed",
    "轴功率": "computed",
    "固体负荷": "computed",
    "回流污泥浓度": "computed",
    "外缘线速度": "computed",
    "分离液量": "computed",
    "Stokes": "computed",
    "淹没度": "computed",
    "弗劳德数": "computed",
    "流量系数": "computed",
    "指数 n": "computed",
    "排砂管": "physical",
    "上游水深": "computed",
    "下游水深": "computed",
    "总变化系数": "computed",
    "密度修正系数": "computed",
    "磁种质量比": "computed",
    "设计充水比": "computed",
    "实际充水比": "computed",
    "过滤总水头损失": "computed",
    "水力坡度": "computed",
    "沿程水损": "computed",
    "总水损": "computed",
    "总扬程": "computed",
    "静扬程": "computed",
    "干固量": "computed",
    "固体回收": "computed",
    "浓缩时间": "computed",
    "总停留时间": "computed",
    "反冲洗总历时": "computed",
    "日有效工作时间": "computed",
    "流道停留时间": "computed",
    # ── computed: 时间/负荷 ──
    "实际停留时间": "computed",
    "停留时间": "computed",
    "表面负荷": "computed",
    "实际表面负荷": "computed",
    "堰负荷": "computed",
    "固体通量": "computed",
    "污泥负荷": "computed",
    "容积负荷": "computed",
    "水力停留时间": "computed",
    "实际 HRT": "computed",
    # ── computed: 水量/泥量 ──
    "每日沉砂量": "computed",
    "日湿污泥量": "computed",
    "日产泥量": "computed",
    "日产干泥量": "computed",
    "日产污泥量": "computed",
    "反冲洗水量": "computed",
    "冲洗水占比": "computed",
    "分离液量": "computed",
    # ── computed: 设备参数 ──
    "需氧量": "computed",
    "搅拌功率": "computed",
    "紫外剂量": "computed",
    "单泵功率": "computed",
    "总装机功率": "computed",
    "扬程": "computed",
    "沼气产量": "computed",
    "甲烷产量": "computed",
    "VS降解量": "computed",
    "VS降解率": "computed",
    "固体回收率": "computed",
    # ── computed: 污泥性质 ──
    "进泥湿泥量": "computed",
    "进泥干固量": "computed",
    "进泥含水率": "computed",
    "出泥湿泥量": "computed",
    "出泥干固量": "computed",
    "出泥含水率": "computed",
    "合并湿泥量": "computed",
    "合并干固量": "computed",
    "合并含水率": "computed",
    "合并VS比": "computed",
    "干固体量": "computed",
    "浓缩时间": "computed",
    "消化温度": "computed",
    "消化时间": "computed",
    # ── computed: 水头损失 ──
    "水头损失": "computed",
    "过栅水头损失": "computed",
    "沿程水头损失": "computed",
    "局部水头损失": "computed",
    "总水头损失": "computed",
    # ── computed: 系数 ──
    "栅条形状系数": "computed",
    "阻力系数": "computed",
    "栅条间隙比指数": "computed",
    # ── computed: 高程相关 ──
    "水面标高": "computed",
    "池底标高": "computed",
    "地面标高": "computed",
    "上游水面标高": "computed",
    "埋深": "computed",
    # ── computed: 其他 ──
    "管道截面积": "computed",
    "水力半径": "computed",
    "所需坡度": "computed",
    "concrete_m3": "computed",
    "面积": "computed",
    "容积": "computed",
    "实际有效容积": "computed",
    "实际沉淀面积": "computed",
}


# ═══════════════ 事件回调 ═══════════════
def get_dimension_category(dim_name: str) -> str:
    """根据维度名查找分类(子串匹配),未命中返回 "computed"

    支持中文维度名(DIM_CATEGORIES 中文关键字匹配)
    和英文向量化字段名(内置模式匹配).
    """
    # 1. 中文关键字匹配(现有逻辑)
    for kw, cat in DIM_CATEGORIES.items():
        if kw in dim_name:
            return cat

    # 2. 英文向量化字段名模式匹配(方案浏览器路径)
    name = dim_name.strip()

    # ── physical: 纯几何尺寸 ──
    # 单字母维度符号
    if name in ("L", "B", "D", "H", "W"):
        return "physical"
    # 高度/深度
    if name in (
        "h2",
        "h4",
        "h5",
        "h_eff",
        "h_eff_out",
        "h_super",
        "h_cyl",
        "h_pit",
        "h_hopper",
        "h_channel_eff",
        "h_clear",
        "h_dist",
        "h_tube",
        "h_thicken",
        "h_check",
    ):
        return "physical"
    if (
        (name.startswith("h_") or name.startswith("H_"))
        and not name.startswith("h_f")
        and not name.startswith("h_loss")
        and not name.startswith("h_m")
    ):
        return "physical"
    # 直径/管径
    if name in ("d_center", "d_upper", "dr", "DN_mm"):
        return "physical"
    if name.startswith("D_") or name.startswith("d_"):
        return "physical"
    # 长度
    if name in (
        "L_total",
        "L_pipe",
        "L_sump",
        "L_ch",
        "L_cell",
        "L_machine",
        "L1",
        "L2",
        "L3",
        "L4",
        "L_suction",
        "L_discharge",
        "L_straight",
    ):
        return "physical"
    if name.startswith("L_") or name.startswith("L"):
        if name in (
            "L_total",
            "L_pipe",
            "L_sump",
            "L_machine",
            "L_ch",
            "L_channel",
            "L_cell",
            "L_weir",
            "L_straight",
            "L_suction",
            "L_discharge",
        ):
            return "physical"
    # 宽度
    if name in ("B1", "B_pool", "B_channel", "B_sump", "B_machine", "B_out", "B渠"):
        return "physical"
    if name.startswith("B_") or name == "B":
        return "physical"
    # 面积
    if name.startswith("A_") or name.startswith("area"):
        return "physical"
    if name in ("F_actual", "F", "S_unit", "S_total"):
        return "physical"
    # 容积
    if name.startswith("V_") and not name.startswith("val_"):
        return "physical"
    # 数量
    if name.startswith("n_") or name.startswith("N_"):
        return "physical"
    if name in (
        "n",
        "n_gap",
        "n_disks",
        "n_machines",
        "n_pumps",
        "n_standby",
        "n_work",
        "n_total",
        "n_hopper",
        "n_hopper_per",
        "n_hopper_total",
        "n_hole",
        "n_out",
        "n_dir",
        "n_rows",
        "n_lamps",
    ):
        return "physical"
    # 比率(径深比/长宽比等 —— 几何特征)
    if name.startswith("ratio_"):
        return "physical"
    # 坡度
    if name in ("i_slope", "i_suction", "i_discharge", "slope"):
        return "physical"
    # 混凝土量
    if name == "concrete_m3":
        return "physical"

    # ── computed: 计算结果 ──
    # 流量
    if name.startswith("Q_") or name.startswith("q_"):
        return "computed"
    # 流速
    if name.startswith("v_"):
        return "computed"
    # 时间/停留
    if name.startswith("t_") or name.startswith("HRT"):
        return "computed"
    # 功率
    if name.startswith("P_") or name.startswith("P"):
        return "computed"
    # 需氧量
    if name.startswith("O2"):
        return "computed"
    # 负荷
    if name in ("Ns", "solid_flux", "q_solid_actual"):
        return "computed"
    # 水头损失
    if (
        name.startswith("h_f")
        or name.startswith("h_m")
        or name.startswith("h_loss")
        or name.startswith("h1_loss")
    ):
        return "computed"
    if name in ("h_total", "h_loss", "head_loss"):
        return "computed"
    # 污泥
    if name in (
        "S_dry",
        "S_wet",
        "Px_bio",
        "Px_nbio",
        "Px_total",
        "Px",
        "W_slag",
        "W_SS_total",
        "W_chem_total",
        "W_s_total",
        "W_s_per",
        "dry_sludge",
        "wet_sludge",
        "SS_removed",
        "DS_in",
        "DS_out",
        "DS_daily",
        "DS",
    ):
        return "computed"
    if name.startswith("S_") or name.startswith("W_"):
        return "computed"
    # 系数/比率
    if name in (
        "KdT",
        "Kz",
        "k_total",
        "T_eff",
        "I_avg",
        "xi",
        "beta_val",
        "sb_factor",
        "eta_bw",
        "VS_degraded",
        "VS_degradation_rate",
        "eta_VS",
    ):
        return "computed"
    if name.startswith("k_") or name.startswith("eta_"):
        return "computed"
    # 药剂
    if (
        name.startswith("m_PAC")
        or name.startswith("m_PAM")
        or name.startswith("M_mag")
        or name.startswith("m_seed")
    ):
        return "computed"
    # 沼气
    if name in ("biogas_yield", "CH4_yield", "thermal_power", "fuel_consumption"):
        return "computed"
    # 泵
    if name in (
        "Q_single_pump",
        "H_st",
        "H_total_pump",
        "P_shaft",
        "filtrate",
        "solid_recovery",
        "Q_sep",
        "VS_degraded",
        "VS_degradation_rate",
    ):
        return "computed"

    return "computed"


# ═══════════════════════════════════════════════════════════════════
# 参数分类 (mod.json / ParamDef 的 key → 显示类别)
#   "basic"     → 基本参数(数量/台数/格数)
#   "physical"  → 构筑物参数(尺寸/水深/超高)
#   "operating" → 运行参数(流量/负荷/时间/流速)
# ═══════════════════════════════════════════════════════════════════

PARAM_CATEGORIES: dict = {
    # ── basic ──
    "n": "basic",
    "n_pumps": "basic",
    "n_machines": "basic",
    "bar_shape": "basic",
    "equip_type": "basic",
    "method": "basic",
    # ── physical ──
    "h_eff": "physical",
    "h_super": "physical",
    "h1": "physical",
    "ratio_LB": "physical",
    "h_clear": "physical",
    "h_dist": "physical",
    "h_thicken": "physical",
    "h3": "physical",
    "h5": "physical",
    "dr": "physical",
    "d_center": "physical",
    "DN_inlet": "physical",
    "B_channel": "physical",
    "i_slope": "physical",
    "R1": "physical",
    "R2": "physical",
    "s": "physical",
    "b": "physical",
    "alpha": "physical",
    "h": "physical",
    "h2": "physical",
    "L_tube": "physical",
    "alpha_tube": "physical",
    "L_pipe": "physical",
    "n_roughness": "physical",
    "h_loss_transport": "physical",
    # ── operating ──
    "Q_design": "operating",
    "Kz": "operating",
    "Q_manual": "operating",
    "q_surf": "operating",
    "q_prime": "operating",
    "t": "operating",
    "v": "operating",
    "v1": "operating",
    "v_in": "operating",
    "v_pipe": "operating",
    "v_channel": "operating",
    "v_center": "operating",
    "v_peripheral": "operating",
    "v_filter": "operating",
    "HRT": "operating",
    "T_settle": "operating",
    "T_thicken": "operating",
    "T_digest": "operating",
    "T_air": "operating",
    "T_clean": "operating",
    "q_solid": "operating",
    "q_evap": "operating",
    "q_capacity": "operating",
    "q_bw": "operating",
    "t_bw": "operating",
    "t_backwash": "operating",
    "Q_pump": "operating",
    "H_pump": "operating",
    "H_st": "operating",
    "P_density": "operating",
    "P_out": "operating",
    "theta": "operating",
    "theta_digest": "operating",
    "eta_VS": "operating",
    "eta_thermal": "operating",
    "biogas_rate": "operating",
    "dosage_PAM": "operating",
    "X": "operating",
    "D_PAC": "operating",
    "k_PAC": "operating",
    "SVI": "operating",
    "X_MLSS": "operating",
    "R_sludge": "operating",
    "RAS": "operating",
    "Z_water_inlet": "operating",
    "Z_ground": "operating",
    "P_sludge": "operating",
    "T_sludge": "operating",
    "t_d": "operating",
    "t_settle": "operating",
    "t_decant": "operating",
}


# ═══════════════ 查询/获取 ═══════════════
def get_param_category(param_key: str) -> str:
    """根据参数 key 查找分类,未命中返回 "operating" """
    return PARAM_CATEGORIES.get(param_key, "operating")
