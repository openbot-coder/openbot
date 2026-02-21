# OpenBot 代码修改建议

## 1. 立即修复的问题

### 1.1 移除API密钥（安全问题）

**文件**: `examples/config.json`
**问题**: 包含真实的API密钥

**修改前**:
```json
{
  "model_configs": {
    "mimo-v2-flash": {
      "api_key": "sk-cormmuv2d5il2biktno0mcltxjis5iuybh4m81b90g0cdxk8",
      "base_url": "https://api.xiaomimimo.com/v1"
    },
    "doubao-seed-2-0-pro-260215": {
      "api_key": "38b45a58-e42c-428d-8b58-71dc80d1fa02",
      "base_url": "https://ark.cn-beijing.volces.com/api/v3"
    }
  }
}
```

**修改后**:
```json
{
  "model_configs": {
    "mimo-v2-flash": {
      "api_key": "${MIMO_API_KEY}",
      "base_url": "https://api.xiaomimimo.com/v1"
    },
    "doubao-seed-2-0-pro-260215": {
      "api_key": "${DOUBAO_API_KEY}",
      "base_url": "https://ark.cn-beijing.volces.com/api/v3"
    }
  }
}
```

### 1.2 修复AgentCore类型注解

**文件**: `src/openbot/agents/core.py`

**问题**: `__init__`方法参数类型与实际调用不匹配

**修改前**:
```python
def __init__(
    self, model_configs: Dict[str, ModelConfig], agent_config: AgentConfig
):
```

**修改后**:
```python
from typing import Dict, Any

def __init__(
    self, model_configs: Dict[str, Any], agent_config: AgentConfig
):
```

### 1.3 实现ConsoleChannel.on_receive方法

**文件**: `src/openbot/channels/console.py`

**修改前**:
```python
class ConsoleChannel(ChatChannel):
    def __init__(self, prompt: str = "openbot> "):
        self.prompt = prompt
        self.running = False
    
    # ... 其他方法
    
    # 缺少 on_receive 方法
```

**修改后**:
```python
class ConsoleChannel(ChatChannel):
    def __init__(self, prompt: str = "openbot> "):
        self.prompt = prompt
        self.running = False
    
    # ... 其他方法
    
    async def on_receive(self, message: AnyMessage) -> None:
        """处理接收消息"""
        # 控制台通道不需要特殊处理接收消息
        pass
```

### 1.4 修复send_stream类型注解

**文件**: `src/openbot/channels/console.py`

**问题**: 类型注解不匹配

**修改前**:
```python
async def send_stream(self, stream: AsyncIterator[str]) -> None:
```

**修改后**:
```python
async def send_stream(self, stream: AsyncIterator[AnyMessage]) -> None:
    """发送流式响应"""
    content = ""
    async for chunk in stream:
        if hasattr(chunk, 'content'):
            content += chunk.content
            print(chunk.content, end="", flush=True)
    print()
```

## 2. 中优先级修改

### 2.1 添加错误处理到main.py

**文件**: `src/openbot/main.py`

**修改前**:
```python
# 调用 AI 处理
ai_response = await agent_core.process(
    processed_message.content, session
)
```

**修改后**:
```python
# 调用 AI 处理
try:
    ai_response = await agent_core.process(
        processed_message.content, session
    )
except Exception as e:
    logging.error(f"AI processing failed: {e}")
    ai_response = "抱歉，处理您的请求时出现了错误。请稍后再试。"
```

### 2.2 修复配置文件路径硬编码

**文件**: `src/openbot/agents/core.py`

**修改前**:
```python
config_manager = ConfigManager(
    "C:\\Users\\shale\\Documents\\trae_projects\\openbot\\examples\\config.json"
)
```

**修改后**:
```python
import os

# 从环境变量获取配置路径
config_path = os.environ.get("OPENBOT_CONFIG_PATH", "examples/config.json")
config_manager = ConfigManager(config_path)
```

### 2.3 添加配置验证

**文件**: `src/openbot/config.py`

**修改后**:
```python
class ConfigManager:
    def __init__(self, config_path: str | None = None):
        self.config_path = config_path
        self.config = self._load_config()
        self._validate_config()

    def _validate_config(self) -> None:
        """验证配置完整性"""
        if not self.config.model_configs:
            raise ValueError("No model configurations provided")
        
        for name, config in self.config.model_configs.items():
            if not config.api_key:
                logging.warning(f"API key not configured for model {name}")
            
            if not config.model:
                raise ValueError(f"Model name not specified for {name}")
```

### 2.4 添加输入验证

**文件**: `src/openbot/channels/console.py`

**修改后**:
```python
import re

class ConsoleChannel(ChatChannel):
    # ... 其他代码 ...
    
    async def receive(self) -> AsyncIterator[AnyMessage]:
        while self.running:
            try:
                user_input = await asyncio.to_thread(input, self.prompt)
                if user_input.lower() == "exit":
                    self.running = False
                    break
                
                # 输入验证
                if not user_input or user_input.isspace():
                    continue
                
                # 长度限制
                if len(user_input) > 10000:
                    print("输入过长，请限制在10000字符以内")
                    continue
                
                # 移除控制字符
                user_input = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', user_input)
                
                yield HumanMessage(
                    content=user_input, role="user", metadata={"channel": "console"}
                )
            except EOFError:
                self.running = False
                break
```

## 3. 低优先级改进

### 3.1 添加常量定义

**文件**: `src/openbot/main.py`

**修改后**:
```python
# 常量定义
CONSOLE_CHANNEL_NAME = "console"
DEFAULT_USER_ID = "default-user"

# 使用常量
if config.channels.get(CONSOLE_CHANNEL_NAME, {}).enabled:
    console_channel = ConsoleChannel(
        prompt=config.channels.get(CONSOLE_CHANNEL_NAME, {}).prompt
    )
    router.register(CONSOLE_CHANNEL_NAME, console_channel)
```

### 3.2 修复版本依赖

**文件**: `pyproject.toml`

**修改前**:
```toml
"vxutils>=20260127",
```

**修改后**:
```toml
"vxutils>=20240127",
```

### 3.3 添加测试

**文件**: `tests/test_config.py`

**新增文件**:
```python
import pytest
from openbot.config import ConfigManager, Config

def test_config_loading():
    """测试配置加载"""
    config_manager = ConfigManager()
    config = config_manager.get()
    assert isinstance(config, Config)

def test_config_validation():
    """测试配置验证"""
    config_manager = ConfigManager()
    assert config_manager.config is not None
```

### 3.4 完善evolution模块

**文件**: `src/openbot/botflow/evolution.py`

**修改后**:
```python
import subprocess
import os
from typing import List, Optional

class GitManager:
    """Git 管理"""

    def __init__(self, repo_path: str = "."):
        self.repo_path = repo_path

    def commit(self, changes: List[CodeChange], message: str) -> str:
        """提交更改"""
        try:
            # 检查是否是git仓库
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                raise RuntimeError("Not a git repository")
            
            # 添加更改
            for change in changes:
                subprocess.run(
                    ["git", "add", change.file_path],
                    cwd=self.repo_path,
                    check=True
                )
            
            # 提交
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            
            # 获取提交哈希
            hash_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            
            return hash_result.stdout.strip()
            
        except Exception as e:
            raise RuntimeError(f"Git commit failed: {e}")

    def rollback(self, commit_hash: str) -> bool:
        """回滚到指定提交"""
        try:
            subprocess.run(
                ["git", "revert", "--no-edit", commit_hash],
                cwd=self.repo_path,
                check=True
            )
            return True
        except Exception as e:
            print(f"Git rollback failed: {e}")
            return False
```

## 4. 代码质量改进

### 4.1 添加类型检查

**文件**: `pyproject.toml`

**修改后**:
```toml
[dependency-groups]
dev = [
    "black>=26.1.0",
    "mypy>=1.19.1",
    "pytest>=9.0.2",
    "pytest-cov>=7.0.0",
    "ruff>=0.15.1",
    "pyright>=1.1.300",  # 添加pyright用于类型检查
]
```

### 4.2 添加pre-commit配置

**文件**: `.pre-commit-config.yaml`

**新增文件**:
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-merge-conflict

  - repo: https://github.com/psf/black
    rev: 24.3.0
    hooks:
      - id: black
        language_version: python3.13

  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
        args: [--max-line-length=88]
```

### 4.3 添加文档字符串

**文件**: `src/openbot/main.py`

**修改后**:
```python
async def main() -> None:
    """
    OpenBot 主函数
    
    1. 解析命令行参数
    2. 加载配置
    3. 初始化组件
    4. 启动Channel
    5. 处理用户输入
    6. 清理资源
    
    Raises:
        KeyboardInterrupt: 当用户中断程序时
    """
    # ... 实现代码 ...
```

## 5. 安全改进

### 5.1 添加日志级别配置

**文件**: `src/openbot/main.py`

**修改后**:
```python
import logging
import os

# 配置日志级别
log_level = os.environ.get("OPENBOT_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### 5.2 敏感信息处理

**文件**: `src/openbot/config.py`

**修改后**:
```python
class ConfigManager:
    def __str__(self) -> str:
        """隐藏敏感信息的字符串表示"""
        config_dict = self.config.model_dump()
        # 隐藏API密钥
        if 'model_configs' in config_dict:
            for name, config in config_dict['model_configs'].items():
                if 'api_key' in config:
                    config['api_key'] = '***'
        return str(config_dict)
```

## 实施计划

### 第1周（立即执行）
1. 移除所有真实API密钥
2. 修复类型注解不一致问题
3. 实现缺失的接口方法

### 第2周
4. 添加错误处理和输入验证
5. 修复配置文件路径硬编码
6. 添加配置验证

### 第3-4周
7. 完善evolution模块
8. 添加单元测试和集成测试
9. 添加代码质量工具（pre-commit、类型检查）

### 第5-6周
10. 性能优化（缓存机制）
11. 完善文档
12. 添加更多功能测试

## 验证清单

### 修复验证
- [ ] 所有API密钥已移除或替换为环境变量
- [ ] 类型注解一致且正确
- [ ] 所有接口方法已实现
- [ ] 错误处理已添加
- [ ] 输入验证已实现

### 功能验证
- [ ] 项目可以正常启动
- [ ] 控制台交互正常
- [ ] 配置加载正常
- [ ] 错误处理正常工作

### 质量验证
- [ ] 代码通过类型检查
- [ ] 代码通过格式化工具检查
- [ ] 单元测试通过
- [ ] 集成测试通过

## 总结

通过实施这些修改，OpenBot项目的代码质量将显著提高，安全性得到加强，可维护性增强。建议按照优先级逐步实施这些修改，并在每次修改后进行充分测试。