# GuiYi 运维手册

本目录是 GuiYi 的部署与运维文档索引。

---

## 文档导航

| 文档 | 适用场景 |
|------|---------|
| [本机部署指南](./deployment-local.md) | 当前开发机上 GuiYi 的实际部署布局——代码、虚拟环境、数据、模型、配置、日志各自在哪，启动脚本如何调用 |
| [本机开发调试指南](./development-local.md) | 开发实例与部署实例完全隔离：`8766`、`data-dev/`、`models-dev/`、`guiyi_dev`、开发启动脚本和数据快照流程 |
| [通用部署指南](./deployment-general.md) | 把 GuiYi 部署到其它 macOS 机器：从零搭建、配置 launchd、构建前端、备份恢复、故障排查 |

---

## 怎么选

- **想了解本机环境怎么跑起来 / 在哪改东西** → [本机部署指南](./deployment-local.md)
- **要在本机开发调试且不影响部署实例** → [本机开发调试指南](./development-local.md)
- **要在新机器上从头部署** → [通用部署指南](./deployment-general.md)
- **日常运维操作（启停、看日志、重建索引）** → [本机部署指南 - 日常运维操作](./deployment-local.md#日常运维操作)
- **故障排查** → [通用部署指南 - 故障排查](./deployment-general.md#故障排查)

---

## 相关文档

- [架构决策记录](../decisions/)
- [项目需求与技术方案](../归一GuiYi-需求与技术方案.md)
