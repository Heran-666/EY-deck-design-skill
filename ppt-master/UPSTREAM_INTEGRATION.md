# EY 内嵌 PPT Master 更新说明

- 更新日期：2026-09-14
- 全局来源：`/Users/hz/.codex/skills/ppt-master`，版本 `6.4.0`
- 内嵌版本：`6.4.0-ey.1`（原版本 `4.5.0`）
- 更新方式：按 SVG 检查、构建和原生导出入口追踪本地 Python 依赖，选择性同步；并非全量替换。

## 同步范围

| 能力 | 集成方式 |
|---|---|
| 设计和信息表达 | 更新共享规划、Executor、形状词汇、拓扑组合、图像、图表和表格参考；EY 服务合同将通用计划字段映射到已批准内容和模板 |
| 文本测量 | 引入字体字宽数据和 `text_measure.py`，同步混排字宽、换行、内联强调及溢出检查 |
| SVG 技术质量 | 更新 checker、语法契约、支持能力检查、图片和 SVG finalization；保留 EY 严格文本承载规则 |
| 原生 DrawingML | 更新 SVG 转换器及其依赖，包含渐变、形状、文字、字体、图片和图表/表格构建修复 |
| 建造参考资源 | 同步 Chart/Table 词汇、相关 SVG、schema 和 scaffold 文档；保留 EY 独立模板 |
| 上游流程文档 | 同步新流程文档以保持共享参考链接完整；仅供依赖参考，不激活全局生成流程 |

## 必须保留的 EY 边界

- 根 `SKILL.md`、控制器、Storyline/content 审批、候选分配/确认和请求 schema 保持原有职责。
- `ppt-master/` 不含可发现的 `SKILL.md` 或 `agents/openai.yaml`，仍仅从 EY 服务调用。
- 完整保留 `INTERNAL.md` 身份、归属文件、两层完整性检查和旧入口 guard 检查；不使用全局 guard 直接覆盖内嵌 guard。
- 保留 `page_svg_service.py` 的请求 v4、上下文 v6 和旧 v2 恢复能力。
- 保留单一 A → Rn → 用户确认 → 发布的流程，不新增三方向选择或 Default/Quick 审批。
- 保留 `ey-executive-editorial-v3`、页面逻辑、满画布、EY fit completion 和直接源 SVG QA 规则。
- 保留延后结构页、固定 Ending、页序和输出文件名。
- 导出仍为平面原生 PPTX、无 notes、reflow；文字承载数量、字符、空格、段落、哈希回执和 postflight 审计继续生效。

## 兼容补丁

1. 上游没有 EY 的 `editable_text_contract_errors` / `text_carrier_integrity_errors`：在新 tspan transform 上保留这些检查及可证明安全的绝对 y → 相对 dy 归一化。
2. 保留 `ImageValidationDependencyError`：缺失 Pillow 必须作为环境缺失，不能误判为坏图片；同时保留新版 MPO/JPEG 支持。
3. 新版结构推断会读取 `data-pptx-editable`；EY 导出桥剥离该非视觉标记及 `data-pptx-layout-kind`，原始 SVG 不改写，视觉指纹仍校验一致。
4. 共享 `plan-core.md` 的包外 ownership 链接改为包内 `artifact-ownership.md`，保证内嵌运行不依赖仓库级规则。

5. 保留 `ShapeResult.trace_metadata`、逐字 `text_sequence` 和 converter 传播：全局新版没有这套 EY 审计扩展；不能以去掉文本审计来解决导出不兼容。

## 未启用或未整体迁移

- 全局 `SKILL.md`、agent 注册、路由/确认执行入口，不替换 EY 工作流。
- 已被上游移除的旧 Template Fill / Native Enhance 入口保留，以满足内嵌归属检查；不是 EY 当前业务入口，本次不承诺其独立运行兼容性。
- 上游新增原生 Office Math 编译器作为依赖存在，但 EY 服务拒绝原生数学标记：现有文字审计尚未支持 OMML。
- EY 导出不启用原生 Chart/Table replacement，继续使用可见、可编辑的 SVG 图形和文字表示。
- 未同步上游用户项目、exports、分析数据、密钥配置、无关品牌/样式目录及完整图片/音频/预览服务升级。

## 验证与限制

验证记录和备份地址见根目录 `reports/ppt-master-update-20260914.md`。
通过自动验证说明受测流程未发现回归；不等同于对任意历史用户项目或 PowerPoint/WPS/Keynote 渲染的绝对保证。
