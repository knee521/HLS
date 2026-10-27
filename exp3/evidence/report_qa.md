# 报告草稿排版与证据检查

2026-10-27，输出 `report/实验报告技术草稿.docx` 及同内容 Markdown。

- 模板为原始 `docs/05-考核/实验报告模板.docx`，SHA-256 为 ff0f7b79a9fd19e46208693ce00588aa3148dc33dcdd4d5396bfa9d0729cc919；先检查原模板两页。
- 从模板复制正文、标题与表格组件；仅修改 `word/document.xml`，其余 ZIP 部件逐字节相同。保留 A4、页边距、字体、页脚和八部分名称。
- 技能标准渲染器因缺少 LibreOffice soffice.exe 失败；改用本机 Microsoft Word 2024 只读打开、更新字段、导出 PDF，再由 Poppler 转 PNG。独立 validate.py 因其 validators 模块不完整无法运行；替代检查为 XML/ZIP 完整性、模板保留部件比对、python-docx 读取及 Word 实际打开与渲染。
- 最终 PDF 为 8 页。初版八页逐页视觉检查；修改后的第 2、3 页重新检查，其余六页 PNG 哈希与已检查版本完全一致。未见截断、重叠、缺字或跨页残行。
- 模型精度、HLS QoR、整机 QoR 均对应实际 evidence 文件；硬件实测、个人心得、身份和签名明确待补。
- 渲染中间件位于 `.work/report`，仅作 QA；提供用户编辑的交付物为报告草稿 DOCX/Markdown。填入硬件照片和独立心得后须重新检查总页数。

显示修复后追加：更新30项测试、三速实现指标、物理段序故障复盘，再通过 Word 导出 `display-fix-final.pdf`，8页全部重新视觉检查，无溢出。该稿生成于用户确认“显示正常”之前，实物复验的最新结论见 `docs/数码管修复与COM7复测.md` 及 `evidence/board/display_feedback_20261027.json`；不能将稿中待复验快照理解为最新硬件状态。


## 最新提交版文档更新

2026-10-27：以上为早期草稿的历史检查。当前主报告为 report/实验三实验报告.docx，共8页，附AI日志4页、声明1页、验收表2页；旧草稿入口已同步。最新逐页与数据核验见 evidence/文档提交版检查记录.md、document_submission_qa.json。
