# EY 内嵌 PPT Master 更新与兼容验证

已将内嵌运行时从 `4.5.0` 选择性升级到 `6.4.0-ey.1`。全局来源为本机 `ppt-master 6.4.0`；没有整体覆盖 EY 工作流。

## 更新判断

| 部分 | 结果 |
|---|---|
| 共享设计/信息表达、形状词汇、拓扑、图像、图表和表格参考 | 已更新；通过 EY 服务合同映射到批准内容和模板 |
| 文本测量、字宽数据、内联强调、换行和溢出检查 | 已更新 |
| SVG 质量检查、finalization、原生 DrawingML 转换及本地依赖 | 已更新 |
| Chart/Table 词汇、相关 SVG、schema 和 scaffold 参考 | 已更新 |
| 全局入口、三方向确认、Default/Quick 执行流程 | 不进入 EY；保持 EY 控制器和审批 |
| 全局原生数学标记 | 暂不启用；EY 服务提前拒绝现有文字审计不能验证的 OMML 对象 |
| 上游用户项目、图片/音频/预览服务整体升级、无关品牌和样式库 | 未同步 |

本次修改原有文件 167 个，新增文件 66 个（含来自上游的 5 组回归测试和 8 个测试 SVG）。本报告是额外新增的记录文件。

## 兼容性处理

- 保留 EY 文本承载闭合检查、安全绝对 y 归一化、1→N 检查。
- 保留缺失 Pillow 的环境错误类型，合并新版图片支持。
- 保留 `ShapeResult.trace_metadata`、`text_sequence` 和转换器传播，确保逐字审计仍有可信证据。
- 导出平面副本剥离新版识别的非视觉 editable/layout-kind 结构提示，原始 SVG 保留，视觉指纹继续验证。
- 新版共享规划规则仅作为设计参考；绑定字段取 EY 请求，禁止新增全局流程和用户 gate。
- 修复唯一包外 ownership 链接，补齐共享参考中的本地文档链接。

## 已验证

| 检查 | 结果 |
|---|---|
| 更新前 EY 测试 | 45 / 45 通过 |
| 隔离副本 EY 测试（新增数学边界回归） | 46 / 46 通过，无跳过 |
| 隔离副本上游相关测试 | 103 / 103 通过，无跳过 |
| 全部 Python 文件语法 | 通过 |
| EY 控制器、根 SKILL、审批参考、独立模板、两层 guard 不变校验 | 通过 |
| 共享 references/workflows 本地 Markdown 链接 | 无缺失 |
| 实际安装目录完整性检查 | 通过 |
| Git diff 空白检查 | 通过 |
| 实际安装目录 EY 测试 | 46 / 46 通过，无跳过 |

实际导出测试覆盖中文段落 reflow、源 SVG → 转换事件 → PPTX 文字框数量一致、字符连续性、无合成硬换行、混合模板页序、封面填充、固定 Ending 和完整导出审计。

## 生效与恢复

全局 EY 技能 `/Users/hz/.codex/skills/ey-deck-design` 是当前工作目录的符号链接，本次更新直接生效。

- 备份目录：`/Users/hz/.codex/backups/ey-deck-design/20260914-163929-ppt-master-update`
- 原文件及逐文件前后哈希：`manifest.json`、`originals/`
- 上游源文件哈希：`upstream_hashes.json`
- 更新前/隔离验证日志保存在备份目录。
- 回滚：`python3 "/Users/hz/.codex/backups/ey-deck-design/20260914-163929-ppt-master-update/restore.py"`

回滚脚本会先核对安装后的哈希，发现后续编辑则拒绝覆盖，避免丢失之后的修改。

## 验证范围

这是一套受测流程未发现回归的选择性集成，不声称完整兼容全部全局 6.4.0 路线。未逐一验证工作目录外历史用户项目，也未逐页验证 Microsoft PowerPoint / WPS / Keynote 的实际渲染。后续上游更新仍应以 EY 请求、模板和导出审计为兼容边界。

详细包内说明：`ppt-master/UPSTREAM_INTEGRATION.md`。
