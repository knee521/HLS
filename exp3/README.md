# 实验三 全连接神经网络 FPGA 手写数字识别

工程采用 MNIST 784→32→10 全连接网络，目标板为达芬奇 A7 `xc7a35tfgg484-2`，50 MHz。软件、HLS及FPGA构建完成；用户已完成部分上板验证，硬件仍全部由用户操作。

**2026-10-27 实测状态：** COM7显示修复后正常；回环2560字节一致；baseline固定100图全部成功、参考不一致0、平均端到端72.40792 ms。13次手写请求成功但无真实标签，不能计算准确率；物理最右位、错包恢复、三速优化和正式现场验收待完成。

**真实修复记录：** 反向段码及16字节回环FIFO积压均已修复并经用户复验。诊断版FIFO现为128字节，识别版不使用该FIFO；详情见docs两份故障记录。旧诊断bit已归档，禁止混用。

最新版为 `report/实验三实验报告.docx`，附 `AI交互日志.docx`、`AI使用声明.docx`、`实验三验收记录表.docx`，均保留Markdown文字源。四位成员信息及真实板测已填写；要求核对与缺口见 `report/提交说明与要求核对.md`。原模板未覆盖。

## 已验证结果

| 检查 | 结果 | 证据 |
|---|---|---|
| MNIST 官方测试集 10000 张 | 浮点 96.57%，定点 96.60% | `evidence/training/evaluation.json` |
| 实际综合 C 函数对整数参考 | 10000 张预测一致；100000 个分数完全一致 | `evidence/simulation/csim_baseline.csv` |
| C/RTL 协同仿真 | 24 个样本通过，含 0–9 与边界图像 | `evidence/simulation/cosim_baseline.csv` |
| HLS 流水线对照 | 51730→26364 周期，核延迟降低约 49.04% | `build/hls_*/solution1/syn/report` |
| 整机 baseline 布局布线 | DSP 2，LUT 552，FF 627；WNS +1.855 ns（显示修正版） | `evidence/implementation/baseline` |
| 主机与 RTL | 30项Python检查、GUI启动；原7套RTL测试及新增完整回环顶层测试 | `evidence/runs` |

上表核延迟属于综合/仿真口径；新增基线板测均值为72.40792 ms，审计见 `evidence/board/report_audit_20261027.json`。手写准确率、物理最右位与正式现场结论仍待补。GUI几何诊断准确率94.55%，不与原始MNIST或实际手写口径混用。

## 直接使用

在 PowerShell 中：

```powershell
Set-Location D:\HLS\code\exp3
& 'D:\HLS\software\Xilinx\Vivado\2018.3\bin\vivado.bat' -mode batch -source scripts/program_device.tcl -tclargs release/baseline/exp3.bit
& .\.venv\Scripts\python.exe -m host.gui
```

也可运行 `scripts/start_gui.ps1`。程序只展示 FPGA 返回结果；未连接硬件时不能识别。当前虚拟环境已经配置好。GUI 支持画板、灰度预览、加载/保存 PNG、784 字节 `.bin` 与完整 `.frame`，逐帧计时和 CSV 留证。

硬件操作见 `docs/硬件操作与验收清单.md`。比特流在 `release/bringup`、`release/baseline`、`release/medium`、`release/fast`；`release/final`暂为115200基线候选。原构建manifest保留生成时状态，分项实测另记 `evidence/board/acceptance_progress.json`，不因部分通过而把整个发布标记为验收完成。

## 重现环境和非硬件流程

本机：Python 3.12.1；PyTorch 2.5.1 CPU；Vivado/Vivado HLS 2018.3。依赖固定在 `requirements-lock.txt`，Python 3.12 是必需条件。

```powershell
# 仅新环境需要；已有 .venv 无需重复安装
& .\scripts\bootstrap.ps1 -Python D:\software\python312\python.exe
# 快速软件检查
& .\.venv\Scripts\python.exe -m scripts.build --stage checks
# 以下按依赖顺序执行；训练会重新生成模型和后续评估输入
& .\.venv\Scripts\python.exe -m scripts.build --stage train
& .\.venv\Scripts\python.exe -m scripts.build --stage hls --variant baseline
& .\.venv\Scripts\python.exe -m scripts.build --stage hls --variant serialized
& .\.venv\Scripts\python.exe -m scripts.build --stage rtl
& .\.venv\Scripts\python.exe -m scripts.build --stage implement
& .\.venv\Scripts\python.exe -m scripts.finalize_release
```

每条命令必须返回 0 才继续下一条；PowerShell 默认不会因外部程序非零退出自动停止。可单独使用 `--configuration baseline|medium|fast|bringup` 和 `--rightmost-index 0..5` 重建硬件候选。`--stage all` 包含重新训练，默认只跑 baseline HLS；串行对照另执行上面的 serialized 命令。

工具绝对路径集中在 `scripts/build.py`、相关 Tcl 与 IP 打包脚本。换机器应先按新安装位置修改，不能直接把 2018.3 生成文件跨版本当作已验证构建。HLS 日期溢出由项目内打包元数据修复处理，详见实施记录。

## 工程组织与维护

| 目录 | 职责 |
|---|---|
| `common` | 协议、图像预处理、整数模型、配置与文件校验 |
| `train` / `model` | 确定性训练、量化、评估 / 冻结权重和数值界限 |
| `host` | GUI、串口事务、故障注入、数据集测量和统计 |
| `hls` | 同一份可综合推理 C++、权重、C 测试和 HLS Tcl |
| `rtl` / `constraints` | UART、状态机、显示、顶层 / 实物引脚及 20 ns 时钟约束 |
| `tests` / `sim` | Python 自动测试 / RTL 自检测试台 |
| `scripts` | 可重建脚本；`program_device.tcl` 仅由用户上板时运行 |
| `data/vectors` | 冻结的测试图、标签、整数分数和协同仿真样本 |
| `evidence` | 原始训练、构建、仿真、时序、资源及 AI 执行记录 |
| `release` / `report` | 比特流与哈希清单 / 报告技术草稿和验收补录资料 |

工程采用分层模块、固定协议、配置校验、异常返回、单事务互斥、超时恢复、确定性种子、源文件/模型/比特流哈希和可重建脚本。原始实验资料未覆盖。`build` 是生成目录；不要删除模型、原始 CSV 或唯一的已验收发布文件。当前目录未初始化 Git，源码快照以 `evidence/source_hashes.json` 标识；运行日志是过程证据，不以“编译成功”代替仿真或上板。

先读 `docs/实施记录与偏差.md` 中的放行边界，再补齐个人报告的独立心得、真实 AI 使用确认和教师签字。不得把草稿直接作为已完成验收的个人报告提交。
