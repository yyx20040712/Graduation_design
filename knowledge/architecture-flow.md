# 排水工程设计工具 v3.2 — 架构与数据流

> 生成日期: 2026-05-19

---

## 一、系统分层架构

```mermaid
graph TB
    subgraph UI["🖥️ 视图层 (tkinter)"]
        CANVAS["节点画布<br/>拖拽/连线/缩放"]
        PARAMS["参数面板<br/>Slider + Entry"]
        BROWSER["方案浏览器<br/>枚举/排序/应用"]
        TREE["结果查看<br/>Treeview + Checks"]
    end

    subgraph CTRL["🔀 控制层"]
        EXEC["GraphExecutor<br/>DAG 拓扑执行"]
        PM["ProjectManager<br/>JSON 序列化"]
        FM["FileManager<br/>文件操作"]
    end

    subgraph MODEL["🧮 模型层"]
        BASE["NodeBase<br/>WaterFlow / WaterQuality<br/>ParamDef / Port"]
        NODES["24 处理单元<br/>调节池·格栅·CASS·V滤···"]
        DISCRETE["discretization.py<br/>参数离散化配置"]
        COST["cost/<br/>工程概算 5 模块"]
        PIPE["pipe_hydraulic.py<br/>管网水力计算"]
        OUTPUT["output_writer.py<br/>分类 Excel 输出"]
    end

    subgraph MOD["🧩 模组系统"]
        MM["ModManager<br/>发现·加载·注册"]
        CORE["mods/core/<br/>16 核心模组"]
        COMMUNITY["mods/community/<br/>社区模组"]
    end

    UI --> CTRL
    CTRL --> MODEL
    MM --> MODEL
    CORE --> MM
    COMMUNITY --> MM
```

---

## 二、核心数据流（水量→计算→输出）

```mermaid
flowchart LR
    subgraph INPUT["📥 输入"]
        Q["Q_design 滑块<br/>m³/s (已含Kz)"]
        KZ["Kz 滑块<br/>总变化系数"]
    end

    subgraph FLOW["💧 水量模型"]
        WF["WaterFlow<br/>Q_design = Q<br/>Q_avg = Q/Kz×86400<br/>Kz = Kz"]
    end

    subgraph DAG["🔀 DAG 执行"]
        COMB["Combiner<br/>WATER+QUALITY→MIXED"]
        N1["粗格栅"] --> N2["细格栅"]
        N2 --> N3["沉砂池"]
        N3 --> N4["初沉池"]
        N4 --> N5["CASS"]
        N5 --> N6["高密池"]
        N6 --> N7["V滤池"]
        N7 --> N8["紫外消毒"]
        S1["污泥线"] -.-> S2["浓缩→脱水→干化"]
    end

    subgraph OUT["📤 输出"]
        EXCEL["分类Excel<br/>按构筑物分Sheet"]
        COST_R["概算报告<br/>BOQ 工程量清单"]
        PIPE_R["管网报告<br/>管径·跌水井"]
    end

    INPUT --> WF
    WF --> COMB
    COMB --> DAG
    DAG --> OUT
```

---

## 三、参数输入与同步机制

```mermaid
sequenceDiagram
    participant E as Entry (StringVar)
    participant S as Scale (DoubleVar)
    participant C as _on_param_changed
    participant N as Node._params

    Note over E,S: 用户打字 — StringVar 不触发提交
    E->>E: 退格·方向键·选中替换<br/>(原生 Excel 体验)

    Note over E,S: Enter / 点击外部 → 提交
    E-->>C: parse float → 提交
    C->>N: set_param(key, value)
    N->>N: _params[key]=value<br/>state=DIRTY

    Note over E,S: 滑块拖动松手 → 提交 + 同步显示
    S-->>E: var.get() → str_var.set()
    S-->>C: _on_param_changed
    C->>N: set_param(key, value)
```

---

## 四、模组加载时序

```mermaid
sequenceDiagram
    participant APP as 应用启动
    participant MM as ModManager
    participant FS as 文件系统
    participant REG as NodeRegistry
    participant UI as 画布菜单

    APP->>MM: get_mod_manager()
    MM->>FS: scan mods/core/
    MM->>FS: scan mods/community/
    FS-->>MM: mod.json × N

    loop 每个模组
        MM->>MM: 验证 mod.json
        MM->>MM: import module_path
        MM-->>MM: getattr(module, node_class)
        MM->>REG: register(node_type, NodeClass)
        MM->>UI: get_category_menu()
    end

    UI-->>APP: 分类菜单就绪
```

---

## 五、格栅计算流程（示例：细格栅）

```mermaid
flowchart TD
    A["读取参数<br/>n, b, α, h, v, v₁, s"] --> B["单台流量<br/>q = Q_design / n"]
    B --> C["间隙数<br/>n_gap = ceil(q·√sinα / b·h·v)"]
    C --> D["栅槽宽 B<br/>B = s·(n_gap-1) + b·n_gap + 0.2"]
    D --> E["校核流速<br/>v_checked = q·√sinα / b·h·n_gap"]
    E --> F["水头损失<br/>ξ = β·(s/b)^(4/3)<br/>h₁ = 3·ξ·v²/(2g)·sinα"]
    F --> G{"约束校核"}
    G -->|v∈[0.6,1.0]| H1["✅ 流速"]
    G -->|v₁∈[0.4,0.9]| H2["✅ 渠速"]
    G -->|B₁<B| H3["✅ 宽度"]
    G -->|h₁≤0.3m| H4["✅ 水头损失"]
    H1 & H2 & H3 & H4 --> I["组装 NodeResult → 下游"]
```

---

## 六、污泥干化面积分支

```mermaid
flowchart TD
    A["method = get_param('method')"] --> B{"method == 0 ?"}
    B -->|是: 热干化| C["A = m_evap / (q_evap × 24)<br/>q_evap ∈ [4,15] kg/(m²·h)"]
    B -->|否: 太阳能| D["A = m_evap / q_evap<br/>q_evap ∈ [5,15] kg/(m²·d)"]
    C --> E["组装结果"]
    D --> E
```

---

## 七、输出文件命名

```mermaid
flowchart LR
    subgraph FILES["输出文件"]
        A["shuichang_sheji_{ts}.xlsx<br/>构筑物设计"]
        B["gaisuan_baogao_{ts}.xlsx<br/>构筑物概算"]
        C["{pipe}_{ts}_计算结果.xlsx<br/>管网水力"]
        D["{pipe}_guanwang_gaisuan_{ts}.xlsx<br/>管网概算"]
    end
```

各输出文件均包含 `YYYYMMDD_HHMMSS` 时间戳；管网相关文件还包含输入 Excel 名称前缀。
