# FIA 传感器仿真 —— Modelica 物理模型

`AMMONIA_FIA_SENSOR_DESIGN.md` §3/§3.1/§3.2 描述的流路、化学反应和状态机，
目前只有文字、ASCII 图和 `src/fia_sequencer.py` 这一份按假时钟运行、驱动
`tests/synthetic_peak.py` 里**编好的**合成峰的固件实现 —— 没有一份从物理
第一原理（泵流量 → 阀路由 → NH₃ 挥发 → 膜扩散 → 氯胺化 → Beer-Lambert 吸光）
真正算出这条峰的模型。这个包补上这一块：用设计文档给的流量和化学参数搭一个
物理厂模型，可以核对文档自己的数字（1.2:0.6 mL/min 是否真能给出约 2 倍的
预浓缩、50 cm 线圈是否真能把峰落在 [20,50] s 窗口内），也可以在真实硬件出现
前用来试调 `FiaSettings`。

## 文件

| 文件 | 用途 |
|---|---|
| `package.mo` | 顶层包 |
| `Units.mo` | 内部单位约定（体积 µL、浓度 mol/µL），mM/mL·min⁻¹ 之类的换算常量 |
| `Sequencer/FiaStates.mo` | 状态枚举，对应 `fia_constants.py::State` |
| `Sequencer/FiaSequencer.mo` | 状态机，移植自 `fia_sequencer.py::_dispatch` |
| `Manifold/Pump.mo` | 受开关信号控制的恒定流量源 |
| `Manifold/SelectorValve.mo` | 样品/标液选择阀 |
| `Manifold/SixPortValve.mo` | 六通进样阀，记录进样瞬间的摩尔量 |
| `Manifold/TransportCoil.mo` | 反应线圈，用串联多釜近似轴向扩散 |
| `Reaction/Volatilization.mo` | NH₄⁺ → NH₃，供体侧一级反应 |
| `Reaction/Chloramination.mo` | NH₃ + OCl⁻ → NH₂Cl，受体侧一级反应 |
| `GasDiffusion/GdCell.mo` | 气体扩散池，双室膜传质 |
| `Optics/FlowCell.mo` | 流通池，Beer-Lambert 吸光度 |
| `Plant.mo` | 顶层厂模型，按 §3 流路图把上面所有模块接起来 |
| `Test/*.mo` | 独立验证模型，`run_tests.mos` 逐个跑并核对数值 |
| `run_tests.mos` | 自检脚本，见下方"运行" |

## 运行

需要 OpenModelica（本仓库用 1.25.4 验证过），装在
`C:\Program Files\OpenModelica1.25.4-64bit\bin\omc.exe`。从这个目录跑：

```bash
"/c/Program Files/OpenModelica1.25.4-64bit/bin/omc.exe" run_tests.mos
```

改任何模型后都应该重跑一次；退出码非零表示至少一项数值检查没通过（同
`mech/gd_cell/gd_cell.py`、`mech/cabinet/cabinet.py` 的自检退出码约定）。
单独跑某个模型（例如在 OMEdit 里，或另写一份 `.mos`）：

```modelica
loadFile("package.mo");
simulate(FiaSensor.Plant, stopTime=1000);
```

## 关键数字（照抄设计文档，不重新推导）

```
载流（NaOH）    1.2 mL/min          §3 流路图
受体流（NaOCl）  0.6 mL/min          §3 流路图，"preconcentration" 一节
进样环          100 µL              §3，BOM 第 4 项
气体扩散池体积   40.0 µL/侧          与 mech/gd_cell/gd_cell.py 的
                                    PLATE_X/Y/Z 沟槽扫掠体积一致，不重算
目标转移率       25%                §3 "why ~25% transfer is acceptable"
pKa(NH4+/NH3)   9.25                §3
供体 pH          12.5                §3，0.2 M NaOH 加碱后
受体 pH          9.2                 §3，20 mM 硼酸盐缓冲
有效摩尔吸光系数  460×0.85=391 M⁻¹cm⁻¹  245 nm λmax 的 460，255 nm LED
                                    偏峰损失约 15%，两个数字都是文档原话
流通池光程       10 mm               §3/§4，BOM 第 15 项
定时常数         prime_s=60, baseline_s=10, load_s=15, acquire_s=70,
                wash_threshold=0.002, wash_timeout_s=120,
                cycle_period_s=900, standard_every=10
                                    src/fia_settings.py::FiaSettings.DEFAULTS
```

线圈扫掠体积由 BOM 第 8/11 项给的管径和 §3 流路图给的线圈长度算出，不是猜的：

```
供体线圈  30 cm × 0.8 mm i.d.（BOM 第 8 项，一般 manifold 管）
          → π×(0.4mm)²×300mm = 150.8 µL
受体线圈  50 cm × 0.8 mm i.d.（BOM 第 11 项，"knitted reaction coil"）
          → π×(0.4mm)²×500mm = 251.3 µL
```

## 建模选择（文档没给的数字，必须和上面分开看）

- **反应动力学取一级 ODE，不取瞬时平衡。** 设计文档只说两个反应"快，几秒内"，
  没给速率常数。`Volatilization.mo`/`Chloramination.mo` 的 `k=2.0 (1/s)`
  是选来让反应在线圈停留时间内跑到 95% 以上完成度的工程取值，不是拟合或
  测量得到的常数——这是显式的建模决定，不是文档数字。
- **`TransportCoil.mo` 的 `nTanks=4`**（串联多釜近似轴向扩散的釜数）是文献
  常见范围内的工程取值。设计文档只给了目标 D≈4–6 这个扩散系数范围和线圈的
  物理尺寸，没给釜数模型，所以这个数字不是拟合出来的。
- **`GdCell.mo` 的 `kMem`（膜传质速率常数）是反解出来的，不是猜的**：解一个
  代数方程，让给定流量下的稳态转移率正好等于文档自己的 25% 这个数字（见
  `GdCell.mo` 内的推导注释）。也就是说这个模型唯一的自由参数是校准到一个
  文档给定的**结果**，不是凭空发明一个渗透系数。
- **`Plant.mo` 里 `sampleConc=8 mg/L N` 是任意取值**，没有文档来源，只是为了
  让这个模型独立跑起来有个可看的数；`standardConc=10 mg/L N` 则是文档
  §3.2 五点标定（0, 0.5, 2, 10, 40 mg/L N）里的中间点，是文档数字。

## OpenModelica 1.25.4 踩到的坑

这些是这个包能编译、能跑起来所必须绕开的编译器/后端限制，都是用最小探针
模型实测确认的，不是猜测：

1. **原生图形状态机语法（`initialState`/`transition` 语句）在这个版本里
   代码生成阶段直接崩**（`..._wrap_vars` 报未声明）。`FiaSequencer.mo` 因此
   没有用这套语法，改用一个 `discrete FiaStates` 变量。
2. **`equation` 段里对枚举状态变量写 `when...elsewhen` 链，后端排序失败**
   （`analyseStrongComponentBlock failed`）。能跑通的写法是每个状态转移
   单独一个 `algorithm` 段 `when` 块（不用 `elsewhen`），正好对应
   `fia_sequencer.py::_dispatch()` 里每个状态一个 `elif` 分支的结构。
3. **任何在 `equation` 段里用 `state_ == X` 这类比较起别名定义的
   Boolean/Integer，一旦被别处的 `when` 条件复用（或被别的组件读取），后端
   同样崩**（`analyseStrongComponentBlock failed` → `sort components failed`），
   不限于瞬态状态。修法和第 2 点同一套：所有从状态派生的输出
   （`samplePumpOn`、`injectionCount` 等）都声明成只在 `algorithm` 段
   `when` 块里赋值的量，不写 `equation` 段的别名表达式。
4. **跨组件用 `reinit()` 复现"瞬时进样"** —— `reinit()` 只能出现在
   `equation` 段 `when` 块里，不能在 `algorithm` 段（这是编译器直接报的
   错，不是坑）；父模型的 `equation` 段 `when` 对子模型状态变量
   `reinit(tank.c, ...)`，以及对数组单元素 `reinit(c[1], ...)`，都验证过
   能正常工作。
5. **`GdCell.mo` 的 `kMem` 公式含除法，若用 `if flowDonor>0 and
   flowAcceptor>0 then ... else 0` 这种条件门控零流量情形，公式本身编译
   通过，但 `Plant.mo` 在泵开关的离散事件边界上会实际算出除零断言**
   （事件迭代时求解器会去探探未选中分支的中间值）。修法是把公式改写成
   不直接除以 `flowAcceptor`，分母整体 `max(..., 1e-12)` 兜底，而不是用
   `if` 条件把整条表达式换掉。

## 还需要决定的

- **这不是硬件验证过的模型**，是从设计文档给的数字加几个明确标注的猜测速率
  常数搭出来的第一原理模型，不代表真实硬件的实测行为。
- 反应速率常数 `k=2.0` 目前对两个反应用同一个值，没有分开调 —— 如果以后要
  对着真实硬件数据拟合，这是第一个该松开的参数。
- `Plant.mo` 没有模拟泵脈动、管路老化、膜污染这些设计文档 §5.2 提到的
  健康退化因素，这些都会改变 25% 这个转移率，但目前模型里是硬编码常数。
