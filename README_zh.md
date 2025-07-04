# NekoConf

<div align="center">
  <img src="https://raw.githubusercontent.com/Nya-Foundation/nekoconf/main/assets/banner.png" width="800" />
  
  <h3>配置管理的完美平衡 - 强大功能与简单操作的完美结合</h3>
  
  <!-- 语言版本 -->
  <p>
    <a href="README.md">🇺🇸 English</a> |
    <a href="README_zh.md">🇨🇳 中文</a> |
    <a href="README_ja.md">🇯🇵 日本語</a>
  </p>
  
  <div>
    <a href="https://pypi.org/project/nekoconf/"><img src="https://img.shields.io/pypi/v/nekoconf.svg" alt="PyPI 版本"/></a>
    <a href="https://pypi.org/project/nekoconf/"><img src="https://img.shields.io/pypi/pyversions/nekoconf.svg" alt="Python 版本"/></a>
    <a href="https://github.com/nya-foundation/nekoconf/blob/main/LICENSE"><img src="https://img.shields.io/github/license/nya-foundation/nekoconf.svg" alt="许可证"/></a>
    <a href="https://pepy.tech/projects/nekoconf"><img src="https://static.pepy.tech/badge/nekoconf" alt="PyPI 下载量"/></a>
    <a href="https://hub.docker.com/r/k3scat/nekoconf"><img src="https://img.shields.io/docker/pulls/k3scat/nekoconf" alt="Docker 下载量"/></a>
    <a href="https://deepwiki.com/Nya-Foundation/NekoConf"><img src="https://deepwiki.com/badge.svg" alt="向 DeepWiki 提问"/></a>
  </div>
  
  <div>
    <a href="https://codecov.io/gh/nya-foundation/nekoconf"><img src="https://codecov.io/gh/nya-foundation/nekoconf/branch/main/graph/badge.svg" alt="代码覆盖率"/></a>
    <a href="https://github.com/nya-foundation/nekoconf/actions/workflows/scan.yml"><img src="https://github.com/nya-foundation/nekoconf/actions/workflows/scan.yml/badge.svg" alt="CodeQL 和依赖扫描"/></a>
    <a href="https://github.com/nya-foundation/nekoconf/actions/workflows/publish.yml"><img src="https://github.com/nya-foundation/nekoconf/actions/workflows/publish.yml/badge.svg" alt="CI/CD 构建"/></a>
  </div>
</div>

## 🐱 什么是 NekoConf？

> [!WARNING]
> 此项目目前正在积极开发中。文档可能不会反映最新的更改。如果您遇到意外行为，请考虑使用以前的稳定版本或在我们的 GitHub 仓库中报告问题。

NekoConf 是一个为 Python 应用程序设计的动态灵活配置管理系统。它简化了配置文件（YAML、JSON、TOML）的处理，并提供实时更新、环境变量覆盖和模式验证功能。

| 功能特性                     | 描述                                                                         |
| --------------------------- | --------------------------------------------------------------------------- |
| **配置即代码**               | 将配置存储在人类可读的 YAML、JSON 或 TOML 文件中                              |
| **集中管理**                | 通过 Python API、CLI 或可选的 Web UI 访问和修改配置                           |
| **动态更新**                | 使用内置事件系统即时响应配置更改                                              |
| **环境变量覆盖**             | 无缝地使用环境变量覆盖文件设置                                                |
| **模式验证**                | 使用 JSON Schema 确保配置完整性并防止错误                                     |
| **并发安全**                | 使用文件锁定防止文件访问期间的竞态条件                                        |
| **远程配置**                | 连接到远程 NekoConf 服务器进行集中配置                                       |

> [!TIP]
> NekoConf 非常适合具有复杂配置需求的应用程序、微服务架构，或任何需要在不重启服务的情况下更新配置的场景。

## 🛠️ 系统要求
- Python 3.10 或更高版本
- Docker（可选，用于容器化部署）

## 📦 安装

NekoConf 采用模块化设计，为不同功能提供可选依赖：

```bash
# 基础安装，包含核心功能（本地）
pip install nekoconf

# 包含 Web UI 服务器（基于 FastAPI）
pip install nekoconf[server]

# 包含模式验证
pip install nekoconf[schema]

# 包含远程客户端（连接到 NekoConf 服务器）
pip install nekoconf[remote]

# 用于开发和测试
pip install nekoconf[dev]

# 安装所有可选功能
pip install nekoconf[all]
```

### 可选功能

| 功能                        | 扩展包        | 依赖项                                             | 用途                                                       |
|----------------------------|--------------|---------------------------------------------------|-----------------------------------------------------------|
| **核心**                   | (无)         | pyyaml, colorlog, tomli, tomli-w                  | 基本配置操作                                               |
| **Web 服务器/API**         | `server`     | fastapi, uvicorn 等                               | 运行 Web 服务器来管理配置                                  |
| **模式验证**               | `schema`     | jsonschema, rfc3987                               | 根据 JSON Schema 验证配置                                  |
| **远程配置**               | `remote`     | requests, websocket-client                       | 连接到远程 NekoConf 服务器                                |
| **开发工具**               | `dev`        | pytest, pytest-cov 等                            | 用于开发和测试                                             |
| **所有功能**               | `all`        | 以上所有                                          | 包含所有功能的完整安装                                      |

## 🚀 快速开始

```python
from nekoconf import NekoConf

# 使用配置文件路径初始化（如果文件不存在则创建）
config = NekoConf("config.yaml", event_emission_enabled=True)

# 注册处理程序以响应配置更改
@config.on_change("database.*")
def handle_db_change(path, old_value, new_value, **kwargs):
    print(f"数据库配置已更改：{path}")
    print(f"  {old_value} -> {new_value}")
    # 重新连接数据库或应用更改...

# 获取配置值（支持点表示法的嵌套键）
db_host = config.get("database.host", default="localhost")
db_port = config.get("database.port", default=5432)

# 设置配置值
config.set("database.pool_size", 10) # 触发 `handle_db_change`
config.set("features.dark_mode", True) # 不会触发 `handle_db_change`

# 保存更改到文件
config.save()
```

## 🔧 核心功能

### 🔄 配置管理

使用点表示法表达式加载、访问和修改配置数据。

```python
sample_config = {
    "database": {
        "host": "127.0.0.1",
        "port": "8080"
    },
    "features": {
        "enabled": False
    }
}

# 用于演示的内存配置
config = NekoConf(sample_config)

# 使用类型转换访问值
host = config.get("database.host") # "127.0.0.1"
port = config.get_int("database.port", default=5432) # 8080
is_enabled = config.get_bool("features.enabled", default=False) # False

# 一次更新多个值，或使用 replace 设置整个配置
config.update({
    "logging": {
        "level": "DEBUG",
        "format": "%(asctime)s - %(levelname)s - %(message)s"
    }
})
print(config.json()) 
```

### 🌍 环境变量覆盖

使用环境变量覆盖配置。默认情况下，变量映射为：
`database.host` → `NEKOCONF_DATABASE_HOST`

```bash
# 使用环境变量覆盖配置值
export NEKOCONF_DATABASE_HOST=production-db.example.com
export NEKOCONF_DATABASE_PORT=5433
export NEKOCONF_FEATURES_ENABLED=true
```

```python
# 这些值将自动反映环境变量
config = NekoConf("config.yaml", env_override_enabled=True)
print(config.get("database.host"))  # "production-db.example.com" 
print(config.get_int("database.port"))  # 5433
print(config.get_bool("features.enabled"))  # True
```
您可以自定义环境变量前缀和分隔符：

```python
config = NekoConf(
    "config.yaml",
    env_override_enabled=True
    env_prefix="MYAPP",
    env_nested_delimiter="_"
)
```

上述配置将使用 `MYAPP_DATABASE_HOST` 覆盖 `database.host`。

### 📢 事件系统

实时响应配置更改：

```python
from nekoconf import NekoConf, EventType

config = NekoConf("config.yaml", event_emission_enabled=True)

# 响应数据库配置的任何更改
@config.on_change("database.*")
def handle_db_change(path, old_value, new_value, **kwargs):
    print(f"数据库配置 {path} 已更改：{old_value} -> {new_value}")

# 响应特定事件类型
@config.on_event([EventType.CREATE, EventType.UPDATE], "cache.*")
def handle_cache_config(event_type, path,new_value, **kwargs):
    if event_type == EventType.CREATE:
        print(f"创建了新的缓存设置：{path} = {new_value}")
    else:
        print(f"缓存设置已更新：{path} = {new_value}")

# 更改配置以触发事件
config.set("database.timeout", 30)  # 触发 handle_db_change
config.set("cache.ttl", 600)  # 触发 handle_cache_config 创建事件
config.set("cache.ttl", 300)  # 触发 handle_cache_config 更新事件
```

### 🌐 远程配置

连接到远程 NekoConf 服务器进行集中配置（需要 `nekoconf[remote]`）：

```python
from nekoconf import NekoConf, RemoteStorageBackend

remote_storage = RemoteStorageBackend(
    url="https://config-server.example.com/api/config",
    app_name="CustomApp"
    api_key="secure-key",
)

config = NekoConf(
    storage=remote_storage,  # 使用远程存储后端
    event_emission_enabled=True # 启用事件观察器
)

# 使用与本地文件完全相同的 API
db_host = config.get("database.host")

# 响应来自远程服务器的更改
@config.on_change("features.*")
def handle_feature_change(path, new_value, **kwargs):
    print(f"功能标志已更改：{path} = {new_value}")
    # 应用功能更改...

# 设置新值
config.set("features.dark_mode", True) # 这将触发 `handle_feature_change` 回调
```

### ✅ 模式验证

使用 JSON Schema 确保配置完整性（需要 `nekoconf[schema]`）：

```python
# schema.json
{
    "type": "object",
    "properties": {
        "database": {
            "type": "object",
            "required": ["host", "port"],
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer", "minimum": 1024}
            }
        }
    },
    "required": ["database"]
}
```

```python
# 使用模式初始化
config = NekoConf("config.yaml", schema_path="schema.json")

# 验证配置
errors = config.validate()
if errors:
    for error in errors:
        print(f"错误：{error}")
    
# 设置无效值并验证
config.set("database.port", "not-a-port")
errors = config.validate()
print(errors)  # 显示验证错误
```

## 🖥️ Web UI 和 REST API

NekoConf 包含一个使用 FastAPI 构建的 Web 服务器，用于远程管理配置（需要 `nekoconf[server]`）：

```python
from nekoconf import NekoConf, NekoConfOrchestrator

config = NekoConf("config.yaml")
apps = {
    "My_Config_Server": config
    # 根据需要添加更多配置应用实例
}
server = NekoConfOrchestrator(apps, api_key="secure-key", read_only=False)
server.run(host="0.0.0.0", port=8000)
```

### 与现有 FastAPI 应用程序集成

您也可以将 NekoConf 编排器挂载到现有的 FastAPI 应用程序中：

```python
from fastapi import FastAPI
from nekoconf import NekoConf, NekoConfOrchestrator

# 您现有的 FastAPI 应用
app = FastAPI(title="我的应用程序")

@app.get("/")
def read_root():
    return {"message": "来自我的主应用的问候！"}

# 创建 NekoConf 编排器
config = NekoConf("config.yaml")
apps = {"MyApp": config}
orchestrator = NekoConfOrchestrator(apps, api_key="secure-key")

# 在 /config 下挂载配置编排器
app.mount("/config", orchestrator.app)

# 现在您的应用同时提供您的端点和配置管理：
# - http://localhost:8000/ - 您的主应用
# - http://localhost:8000/config/ - 配置仪表板
# - http://localhost:8000/config/docs - 配置 API 文档
# - http://localhost:8000/config/api/apps - 配置 API 端点

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

在 http://localhost:8000 访问 Web UI 或使用 REST 端点：

> [!TIP]
> **交互式 API 文档**：FastAPI 自动生成交互式 API 文档，可在以下位置访问：
> - **Swagger UI**：http://localhost:8000/docs 
> - **ReDoc**：http://localhost:8000/redoc
> 
> 这些提供了一个完整的交互式界面，可以直接从浏览器测试所有 API 端点。

### 健康检查和系统端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/health` | GET | 健康检查和系统状态 |

### 应用管理端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/apps` | GET | 列出所有受管理的应用及其信息 |
| `/api/apps` | POST | 创建新的配置应用 |
| `/api/apps/{app_name}` | GET | 获取特定应用的信息 |
| `/api/apps/{app_name}` | PUT | 更新应用的配置和元数据 |
| `/api/apps/{app_name}` | DELETE | 删除应用并清理其资源 |
| `/api/apps/{app_name}/metadata` | PATCH | 更新应用元数据（名称和/或描述） |

### 配置管理端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/apps/{app_name}/config` | GET | 获取特定应用的完整配置 |
| `/api/apps/{app_name}/config` | PUT | 更新特定应用的完整配置 |
| `/api/apps/{app_name}/config/{path}` | GET | 通过路径获取特定配置值 |
| `/api/apps/{app_name}/config/{path}` | PUT | 通过路径设置特定配置值 |
| `/api/apps/{app_name}/config/{path}` | DELETE | 通过路径删除特定配置值 |
| `/api/apps/{app_name}/validate` | POST | 根据模式验证配置 |

### WebSocket 端点

| 端点 | 协议 | 描述 |
|------|------|------|
| `/ws/{app_name}` | WebSocket | 特定应用的实时配置更新 |

### 静态文件端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/` | GET | 提供编排器仪表板 |
| `/{app_name}` | GET | 提供特定应用的配置页面 |
| `/static/{file_path}` | GET | 提供静态资源（CSS、JS、图片） |
| `/favicon.ico` | GET | 提供网站图标 |

服务器支持 WebSocket 连接，用于按应用进行实时配置更新。

> [!WARNING]
> 在生产环境中，请使用 API 密钥保护您的 API。

### Web UI 展示

<div align="center">

**配置管理界面**
<img src="https://raw.githubusercontent.com/Nya-Foundation/nekoconf/main/assets/config_app.png" width="700" />

**仪表板和概览**
<img src="https://raw.githubusercontent.com/Nya-Foundation/nekoconf/main/assets/dashboard.png" width="700" />

</div>

## 💻 命令行界面

NekoConf 提供了一个全面的命令行界面来管理配置：

### 基本用法

```bash
# 查看帮助和版本
nekoconf --help
nekoconf --version

# 为任何命令启用调试日志
nekoconf --debug <command>
```

### 服务器管理

```bash
# 启动 Web 服务器（需要 nekoconf[server]）
nekoconf server --config config.yaml --port 8000 --api-key "secure-key"

# 使用其他选项启动服务器
nekoconf server \
  --host 0.0.0.0 \
  --port 8000 \
  --config config.yaml \
  --schema schema.json \
  --api-key "secure-key" \
  --app-name "MyApp" \
  --event true \
  --read-only false \
  --reload true
```

### 配置管理

```bash
# 使用模板初始化新配置
nekoconf init config.yaml --template default
nekoconf init api-config.yaml --template api-service
nekoconf init web-config.yaml --template web-app
nekoconf init micro-config.yaml --template microservice
nekoconf init empty-config.yaml --template empty

# 获取配置值
nekoconf get database.host --config config.yaml

# 以不同格式获取完整配置
nekoconf get --config config.yaml --format json
nekoconf get --config config.yaml --format yaml
nekoconf get --config config.yaml --format raw

# 设置配置值
nekoconf set database.port 5432 --config config.yaml

# 使用模式验证设置
nekoconf set database.port 5432 --config config.yaml --schema schema.json

# 删除配置值
nekoconf delete old.setting --config config.yaml

# 验证配置（需要 nekoconf[schema]）
nekoconf validate --config config.yaml --schema schema.json
```

### 远程配置

```bash
# 连接到远程 NekoConf 服务器（需要 nekoconf[remote]）
nekoconf connect --remote http://config-server:8000 --api-key "secure-key" --format json

# 使用特定应用名称连接
nekoconf connect --remote http://config-server:8000 --app-name "MyApp" --api-key "secure-key"

# 从远程服务器获取值
nekoconf get database.host --remote http://config-server:8000 --api-key "secure-key"

# 在远程服务器上设置值
nekoconf set cache.ttl 600 --remote http://config-server:8000 --api-key "secure-key"

# 在远程服务器上删除值
nekoconf delete old.setting --remote http://config-server:8000 --api-key "secure-key"

# 验证远程配置
nekoconf validate --remote http://config-server:8000 --api-key "secure-key" --schema schema.json
```

### 配置模板

`init` 命令支持几个内置模板：

| 模板 | 描述 | 用例 |
|------|------|------|
| `empty` | 📄 空配置 | 从空白配置开始 |
| `default` | ⚙️ 默认配置 | 基本配置模板 |
| `web-app` | 🌐 Web 应用程序 | 具有服务器和 API 设置的前端应用程序 |
| `api-service` | 🔌 API 服务 | 具有数据库和身份验证配置的后端服务 |
| `microservice` | 🐳 微服务 | 具有日志记录和指标的容器化服务 |

## ❤️ Discord 社区

[![Discord](https://img.shields.io/discord/1365929019714834493)](https://discord.gg/jXAxVPSs7K)

> [!NOTE]
> 需要支持？联系 [k3scat@gmail.com](mailto:k3scat@gmail.com) 或加入我们在 [Nya Foundation](https://discord.gg/jXAxVPSs7K) 的 Discord 社区

## 📝 许可证

本项目采用 MIT 许可证 - 详情请参阅 [LICENSE](LICENSE) 文件。