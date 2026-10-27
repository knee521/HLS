# 数码管段码修复与 COM7 复测

2026-10-27：用户确认下载的是 bringup，只有数字 4 正常。已定位旧 RTL 的段码位序与原理图相反；正确顺序是 `seg_led[7:0]={dp,g,f,e,d,c,b,a}`，低有效。数字 4 的 0x99 恰好位反转不变，与实物现象一致。XDC 引脚保持原板卡分配，修正数字、短横线和逐段自检编码。

**复验更新：用户已重新下载并确认“这次显示正常”，段码乱码故障关闭。下一步从下方 COM7 回环命令开始，无须重复下载诊断固件。** 物理最右位编号、串口回环及模型识别结果尚未明确反馈，不能一并视为通过。报告草稿中本次修复“待复验”是收到此确认前的快照，以本记录及 `evidence/board/display_feedback_20261027.json` 的最新状态为准。

先重新下载当前生成的诊断固件。仅重启 GUI 不会更新 FPGA：

```powershell
Set-Location D:\HLS\code\exp3
& 'D:\HLS\software\Xilinx\Vivado\2018.3\bin\vivado.bat' -mode batch -source scripts/program_device.tcl -tclargs release/bringup/exp3.bit
```

观察完整的 25 秒循环：先全 8，然后六个位置依次显示 0–5，再逐段点亮 a、b、c、d、e、f、g、dp，最后在默认最右位显示 0–9。逐段阶段只亮一根笔画是有意设计，不能当作错误。0–9 阶段应能辨认全部十个数字；实际最右位仍须本人确认。

显示正常后执行串口回环（关闭其他占用 COM7 的串口程序）：

```powershell
& .\.venv\Scripts\python.exe -m host.echo_test --port COM7
```

必须为 2560 字节全部一致、passed=true，然后才进入识别固件：

```powershell
& 'D:\HLS\software\Xilinx\Vivado\2018.3\bin\vivado.bat' -mode batch -source scripts/program_device.tcl -tclargs release/baseline/exp3.bit
& .\.venv\Scripts\python.exe -m host.gui
```

GUI选择COM7、115200。诊断固件只能回环，不能识别。后续状态已更新：用户完成2560字节回环及固定100图比对，全部成功。手写标签、最右位、故障注入和提速仍按硬件清单补验。AI负责修改与非硬件验证，用户负责实际下载和板测。
