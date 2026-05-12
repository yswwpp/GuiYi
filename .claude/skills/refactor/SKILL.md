# Refactor Skill

代码重构工作流，提升代码质量和可维护性。

## 触发时机

- 代码重复度超过 3 次
- 函数长度超过 50 行
- 类/模块职责不清晰
- 性能瓶颈需要优化

## 重构原则

### Python 后端重构

1. **提取函数**
   - 重复代码提取为独立函数
   - 函数命名清晰表达意图
   - 单一职责原则

2. **设计模式应用**
   - 适配器模式：统一数据源接口
   - 策略模式：不同的同步策略
   - 工厂模式：创建适配器实例

3. **性能优化**
   - 批量数据库操作
   - 异步 I/O
   - 缓存机制

### Swift 前端重构

1. **视图拆分**
   - 大视图拆分为小组件
   - 提取可复用组件

2. **状态管理**
   - 使用 @ObservedObject 管理复杂状态
   - 避免 @State 滥用

## 重构清单

### 重构前准备

- [ ] 确认测试覆盖（确保重构不破坏功能）
- [ ] 备份当前代码（Git commit）
- [ ] 明确重构目标（提升什么指标）

### 重构执行

- [ ] 小步重构（每次只改一点）
- [ ] 持续测试（每步都验证）
- [ ] 保持功能不变（不添加新功能）

### 重构后验证

- [ ] 所有测试通过
- [ ] 功能验证无误
- [ ] 性能指标提升
- [ ] 代码质量提升

## 常见重构场景

### 场景 1：提取适配器接口

```python
# 重构前
class FeishuAdapter:
    def fetch_all_for_index(self):
        pass

class WPSAdapter:
    def fetch_all_for_index(self):
        pass

# 重构后
from abc import ABC, abstractmethod

class BaseAdapter(ABC):
    @abstractmethod
    def fetch_all_for_index(self):
        """获取所有文档用于索引"""
        pass

class FeishuAdapter(BaseAdapter):
    def fetch_all_for_index(self):
        # 实现
        pass
```

### 场景 2：提取同步策略

```python
# 重构前
def sync_source(source_name):
    if source_name == "feishu":
        # 飞书同步逻辑
        pass
    elif source_name == "wps":
        # WPS 同步逻辑
        pass

# 重构后
class SyncStrategy(ABC):
    @abstractmethod
    def sync(self):
        pass

class FeishuSyncStrategy(SyncStrategy):
    def sync(self):
        # 飞书同步逻辑
        pass
```

## 输出格式

```markdown
## 重构报告

### 重构目标
- 目标描述

### 重构前
- 代码问题分析
- 质量指标（复杂度、重复度等）

### 重构步骤
1. 步骤 1
2. 步骤 2

### 重构后
- 代码改进说明
- 质量指标对比

### 验证结果
- [ ] 测试通过
- [ ] 功能验证通过
- [ ] 性能提升：X%
```

## 使用方法

```bash
# 重构当前文件
/refactor

# 重构指定模块
/refactor guiyi-server/adapters/
```
