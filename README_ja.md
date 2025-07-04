# NekoConf

<div align="center">
  <img src="https://raw.githubusercontent.com/Nya-Foundation/nekoconf/main/assets/banner.png" width="800" />
  
  <h3>設定管理における力強さとシンプルさの完璧なバランス</h3>
  
  <!-- 言語バージョン -->
  <p>
    <a href="README.md">🇺🇸 English</a> |
    <a href="README_zh.md">🇨🇳 中文</a> |
    <a href="README_ja.md">🇯🇵 日本語</a>
  </p>
  
  <div>
    <a href="https://pypi.org/project/nekoconf/"><img src="https://img.shields.io/pypi/v/nekoconf.svg" alt="PyPI バージョン"/></a>
    <a href="https://pypi.org/project/nekoconf/"><img src="https://img.shields.io/pypi/pyversions/nekoconf.svg" alt="Python バージョン"/></a>
    <a href="https://github.com/nya-foundation/nekoconf/blob/main/LICENSE"><img src="https://img.shields.io/github/license/nya-foundation/nekoconf.svg" alt="ライセンス"/></a>
    <a href="https://pepy.tech/projects/nekoconf"><img src="https://static.pepy.tech/badge/nekoconf" alt="PyPI ダウンロード数"/></a>
    <a href="https://hub.docker.com/r/k3scat/nekoconf"><img src="https://img.shields.io/docker/pulls/k3scat/nekoconf" alt="Docker ダウンロード数"/></a>
    <a href="https://deepwiki.com/Nya-Foundation/NekoConf"><img src="https://deepwiki.com/badge.svg" alt="DeepWiki に質問"/></a>
  </div>
  
  <div>
    <a href="https://codecov.io/gh/nya-foundation/nekoconf"><img src="https://codecov.io/gh/nya-foundation/nekoconf/branch/main/graph/badge.svg" alt="コードカバレッジ"/></a>
    <a href="https://github.com/nya-foundation/nekoconf/actions/workflows/scan.yml"><img src="https://github.com/nya-foundation/nekoconf/actions/workflows/scan.yml/badge.svg" alt="CodeQL・依存関係スキャン"/></a>
    <a href="https://github.com/nya-foundation/nekoconf/actions/workflows/publish.yml"><img src="https://github.com/nya-foundation/nekoconf/actions/workflows/publish.yml/badge.svg" alt="CI/CD ビルド"/></a>
  </div>
</div>

## 🐱 NekoConf とは？

> [!WARNING]
> このプロジェクトは現在活発に開発中です。ドキュメントは最新の変更を反映していない場合があります。予期しない動作に遭遇した場合は、以前の安定版を使用するか、GitHub リポジトリで問題を報告してください。

NekoConf は、Python アプリケーション向けの動的で柔軟な設定管理システムです。設定ファイル（YAML、JSON、TOML）の処理を簡素化し、リアルタイム更新、環境変数オーバーライド、スキーマ検証を提供します。

| 機能                        | 説明                                                                         |
| --------------------------- | --------------------------------------------------------------------------- |
| **コードとしての設定**        | 人間が読みやすい YAML、JSON、または TOML ファイルに設定を保存                  |
| **集中管理**                | Python API、CLI、または オプションの Web UI を通じて設定にアクセス・変更        |
| **動的更新**                | 内蔵イベントシステムを使用して設定変更に即座に反応                             |
| **環境変数オーバーライド**     | 環境変数でファイル設定をシームレスにオーバーライド                             |
| **スキーマ検証**             | JSON Schema を使用して設定の整合性を確保し、エラーを防止                       |
| **並行安全**                | ファイルロックを使用してファイルアクセス中の競合状態を防止                      |
| **リモート設定**             | リモート NekoConf サーバーに接続して集中設定                                  |

> [!TIP]
> NekoConf は、複雑な設定要件を持つアプリケーション、マイクロサービスアーキテクチャ、またはサービスを再起動せずに設定を更新する必要があるシナリオに最適です。

## 🛠️ 前提条件
- Python 3.10 以上
- Docker（オプション、コンテナ化デプロイメント用）

## 📦 インストール

NekoConf は、異なる機能に対してオプションの依存関係を持つモジュラー設計に従います：

```bash
# コア機能を含む基本インストール（ローカル）
pip install nekoconf

# WebUI サーバー付き（FastAPI ベース）
pip install nekoconf[server]

# スキーマ検証付き
pip install nekoconf[schema]

# リモートクライアント付き（NekoConf サーバーに接続）
pip install nekoconf[remote]

# 開発・テスト用
pip install nekoconf[dev]

# すべてのオプション機能をインストール
pip install nekoconf[all]
```

### オプション機能

| 機能                        | 拡張パッケージ | 依存関係                                           | 目的                                                       |
|----------------------------|--------------|---------------------------------------------------|-----------------------------------------------------------|
| **コア**                   | (なし)       | pyyaml, colorlog, tomli, tomli-w                  | 基本的な設定操作                                           |
| **Web サーバー/API**       | `server`     | fastapi, uvicorn など                             | 設定を管理するための Web サーバーを実行                     |
| **スキーマ検証**           | `schema`     | jsonschema, rfc3987                               | JSON Schema に対する設定検証                               |
| **リモート設定**           | `remote`     | requests, websocket-client                       | リモート NekoConf サーバーに接続                           |
| **開発ツール**             | `dev`        | pytest, pytest-cov など                          | 開発とテスト用                                             |
| **すべての機能**           | `all`        | 上記すべて                                        | すべての機能を含む完全インストール                          |

## 🚀 クイックスタート

```python
from nekoconf import NekoConf

# 設定ファイルパスで初期化（ファイルが存在しない場合は作成）
config = NekoConf("config.yaml", event_emission_enabled=True)

# 設定変更に反応するハンドラーを登録
@config.on_change("database.*")
def handle_db_change(path, old_value, new_value, **kwargs):
    print(f"データベース設定が変更されました：{path}")
    print(f"  {old_value} -> {new_value}")
    # データベースに再接続するか変更を適用...

# 設定値を取得（ドット記法でネストされたキーをサポート）
db_host = config.get("database.host", default="localhost")
db_port = config.get("database.port", default=5432)

# 設定値を設定
config.set("database.pool_size", 10) # `handle_db_change` をトリガー
config.set("features.dark_mode", True) # `handle_db_change` をトリガーしない

# 変更をファイルに保存
config.save()
```

## 🔧 コア機能

### 🔄 設定管理

ドット記法式を使用して設定データを読み込み、アクセス、変更します。

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

# デモ用のインメモリ設定
config = NekoConf(sample_config)

# 型変換でアクセス
host = config.get("database.host") # "127.0.0.1"
port = config.get_int("database.port", default=5432) # 8080
is_enabled = config.get_bool("features.enabled", default=False) # False

# 複数の値を一度に更新、または replace を使用して設定全体を設定
config.update({
    "logging": {
        "level": "DEBUG",
        "format": "%(asctime)s - %(levelname)s - %(message)s"
    }
})
print(config.json()) 
```

### 🌍 環境変数オーバーライド

環境変数で設定をオーバーライドします。デフォルトでは、変数は次のようにマップされます：
`database.host` → `NEKOCONF_DATABASE_HOST`

```bash
# 環境変数で設定値をオーバーライド
export NEKOCONF_DATABASE_HOST=production-db.example.com
export NEKOCONF_DATABASE_PORT=5433
export NEKOCONF_FEATURES_ENABLED=true
```

```python
# これらの値は環境変数を自動的に反映します
config = NekoConf("config.yaml", env_override_enabled=True)
print(config.get("database.host"))  # "production-db.example.com" 
print(config.get_int("database.port"))  # 5433
print(config.get_bool("features.enabled"))  # True
```
環境変数のプレフィックスと区切り文字をカスタマイズできます：

```python
config = NekoConf(
    "config.yaml",
    env_override_enabled=True
    env_prefix="MYAPP",
    env_nested_delimiter="_"
)
```

上記は `MYAPP_DATABASE_HOST` で `database.host` をオーバーライドします。

### 📢 イベントシステム

設定変更にリアルタイムで反応：

```python
from nekoconf import NekoConf, EventType

config = NekoConf("config.yaml", event_emission_enabled=True)

# データベース設定の任意の変更に反応
@config.on_change("database.*")
def handle_db_change(path, old_value, new_value, **kwargs):
    print(f"データベース設定 {path} が変更されました：{old_value} -> {new_value}")

# 特定のイベントタイプに反応
@config.on_event([EventType.CREATE, EventType.UPDATE], "cache.*")
def handle_cache_config(event_type, path,new_value, **kwargs):
    if event_type == EventType.CREATE:
        print(f"新しいキャッシュ設定が作成されました：{path} = {new_value}")
    else:
        print(f"キャッシュ設定が更新されました：{path} = {new_value}")

# 設定を変更してイベントをトリガー
config.set("database.timeout", 30)  # handle_db_change をトリガー
config.set("cache.ttl", 600)  # handle_cache_config 作成イベントをトリガー
config.set("cache.ttl", 300)  # handle_cache_config 更新イベントをトリガー
```

### 🌐 リモート設定

集中設定のためにリモート NekoConf サーバーに接続（`nekoconf[remote]` が必要）：

```python
from nekoconf import NekoConf, RemoteStorageBackend

remote_storage = RemoteStorageBackend(
    url="https://config-server.example.com/api/config",
    app_name="CustomApp"
    api_key="secure-key",
)

config = NekoConf(
    storage=remote_storage,  # リモートストレージバックエンドを使用
    event_emission_enabled=True # イベントオブザーバーを有効化
)

# ローカルファイルと全く同じ API を使用
db_host = config.get("database.host")

# リモートサーバーからの変更に反応
@config.on_change("features.*")
def handle_feature_change(path, new_value, **kwargs):
    print(f"機能フラグが変更されました：{path} = {new_value}")
    # 機能変更を適用...

# 新しい値を設定
config.set("features.dark_mode", True) # これは `handle_feature_change` コールバックをトリガーします
```

### ✅ スキーマ検証

JSON Schema を使用して設定の整合性を確保（`nekoconf[schema]` が必要）：

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
# スキーマで初期化
config = NekoConf("config.yaml", schema_path="schema.json")

# 設定を検証
errors = config.validate()
if errors:
    for error in errors:
        print(f"エラー：{error}")
    
# 無効な値を設定して検証
config.set("database.port", "not-a-port")
errors = config.validate()
print(errors)  # 検証エラーを表示
```

## 🖥️ Web UI と REST API

NekoConf には設定をリモート管理するための FastAPI で構築された Web サーバーが含まれています（`nekoconf[server]` が必要）：

```python
from nekoconf import NekoConf, NekoConfOrchestrator

config = NekoConf("config.yaml")
apps = {
    "My_Config_Server": config
    # 必要に応じて設定アプリインスタンスを追加
}
server = NekoConfOrchestrator(apps, api_key="secure-key", read_only=False)
server.run(host="0.0.0.0", port=8000)
```

### 既存の FastAPI アプリケーションとの統合

既存の FastAPI アプリケーションに NekoConf オーケストレーターをマウントすることもできます：

```python
from fastapi import FastAPI
from nekoconf import NekoConf, NekoConfOrchestrator

# 既存の FastAPI アプリ
app = FastAPI(title="私のアプリケーション")

@app.get("/")
def read_root():
    return {"message": "メインアプリからのご挨拶！"}

# NekoConf オーケストレーターを作成
config = NekoConf("config.yaml")
apps = {"MyApp": config}
orchestrator = NekoConfOrchestrator(apps, api_key="secure-key")

# 設定オーケストレーターを /config の下にマウント
app.mount("/config", orchestrator.app)

# これでアプリはエンドポイントと設定管理の両方を提供します：
# - http://localhost:8000/ - メインアプリ
# - http://localhost:8000/config/ - 設定ダッシュボード
# - http://localhost:8000/config/docs - 設定 API ドキュメント
# - http://localhost:8000/config/api/apps - 設定 API エンドポイント

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

Web UI は http://localhost:8000 でアクセスするか、REST エンドポイントを使用してください：

> [!TIP]
> **インタラクティブ API ドキュメント**：FastAPI は自動的にインタラクティブ API ドキュメントを生成します：
> - **Swagger UI**：http://localhost:8000/docs 
> - **ReDoc**：http://localhost:8000/redoc
> 
> これらは、ブラウザから直接すべての API エンドポイントをテストできる完全なインタラクティブインターフェースを提供します。

### ヘルスチェック・システムエンドポイント

| エンドポイント | メソッド | 説明 |
|--------------|----------|------|
| `/health` | GET | ヘルスチェック・システムステータス |

### アプリ管理エンドポイント

| エンドポイント | メソッド | 説明 |
|--------------|----------|------|
| `/api/apps` | GET | 管理されているすべてのアプリとその情報を一覧表示 |
| `/api/apps` | POST | 新しい設定アプリを作成 |
| `/api/apps/{app_name}` | GET | 特定のアプリの情報を取得 |
| `/api/apps/{app_name}` | PUT | アプリの設定とメタデータを更新 |
| `/api/apps/{app_name}` | DELETE | アプリを削除してリソースをクリーンアップ |
| `/api/apps/{app_name}/metadata` | PATCH | アプリメタデータ（名前・説明）を更新 |

### 設定管理エンドポイント

| エンドポイント | メソッド | 説明 |
|--------------|----------|------|
| `/api/apps/{app_name}/config` | GET | 特定のアプリの全設定を取得 |
| `/api/apps/{app_name}/config` | PUT | 特定のアプリの全設定を更新 |
| `/api/apps/{app_name}/config/{path}` | GET | パスで特定の設定値を取得 |
| `/api/apps/{app_name}/config/{path}` | PUT | パスで特定の設定値を設定 |
| `/api/apps/{app_name}/config/{path}` | DELETE | パスで特定の設定値を削除 |
| `/api/apps/{app_name}/validate` | POST | スキーマに対して設定を検証 |

### WebSocket エンドポイント

| エンドポイント | プロトコル | 説明 |
|--------------|-----------|------|
| `/ws/{app_name}` | WebSocket | 特定のアプリのリアルタイム設定更新 |

### 静的ファイルエンドポイント

| エンドポイント | メソッド | 説明 |
|--------------|----------|------|
| `/` | GET | オーケストレーターダッシュボードを提供 |
| `/{app_name}` | GET | 特定のアプリの設定ページを提供 |
| `/static/{file_path}` | GET | 静的アセット（CSS、JS、画像）を提供 |
| `/favicon.ico` | GET | ファビコンを提供 |

サーバーは、アプリごとのリアルタイム設定更新のための WebSocket 接続をサポートしています。

> [!WARNING]
> 本番環境では API キーで API を保護してください。

### Web UI ショーケース

<div align="center">

**設定管理インターフェース**
<img src="https://raw.githubusercontent.com/Nya-Foundation/nekoconf/main/assets/config_app.png" width="700" />

**ダッシュボード・概要**
<img src="https://raw.githubusercontent.com/Nya-Foundation/nekoconf/main/assets/dashboard.png" width="700" />

</div>

## 💻 コマンドラインインターフェース

NekoConf は設定管理のための包括的なコマンドラインインターフェースを提供します：

### 基本的な使用法

```bash
# ヘルプとバージョンを表示
nekoconf --help
nekoconf --version

# 任意のコマンドでデバッグログを有効化
nekoconf --debug <command>
```

### サーバー管理

```bash
# Web サーバーを開始（nekoconf[server] が必要）
nekoconf server --config config.yaml --port 8000 --api-key "secure-key"

# 追加オプション付きでサーバーを開始
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

### 設定管理

```bash
# テンプレートで新しい設定を初期化
nekoconf init config.yaml --template default
nekoconf init api-config.yaml --template api-service
nekoconf init web-config.yaml --template web-app
nekoconf init micro-config.yaml --template microservice
nekoconf init empty-config.yaml --template empty

# 設定値を取得
nekoconf get database.host --config config.yaml

# 異なる形式で全設定を取得
nekoconf get --config config.yaml --format json
nekoconf get --config config.yaml --format yaml
nekoconf get --config config.yaml --format raw

# 設定値を設定
nekoconf set database.port 5432 --config config.yaml

# スキーマ検証付きで設定
nekoconf set database.port 5432 --config config.yaml --schema schema.json

# 設定値を削除
nekoconf delete old.setting --config config.yaml

# 設定を検証（nekoconf[schema] が必要）
nekoconf validate --config config.yaml --schema schema.json
```

### リモート設定

```bash
# リモート NekoConf サーバーに接続（nekoconf[remote] が必要）
nekoconf connect --remote http://config-server:8000 --api-key "secure-key" --format json

# 特定のアプリ名で接続
nekoconf connect --remote http://config-server:8000 --app-name "MyApp" --api-key "secure-key"

# リモートサーバーから値を取得
nekoconf get database.host --remote http://config-server:8000 --api-key "secure-key"

# リモートサーバーで値を設定
nekoconf set cache.ttl 600 --remote http://config-server:8000 --api-key "secure-key"

# リモートサーバーで値を削除
nekoconf delete old.setting --remote http://config-server:8000 --api-key "secure-key"

# リモート設定を検証
nekoconf validate --remote http://config-server:8000 --api-key "secure-key" --schema schema.json
```

### 設定テンプレート

`init` コマンドは複数の組み込みテンプレートをサポートしています：

| テンプレート | 説明 | 用途 |
|-------------|------|------|
| `empty` | 📄 空の設定 | 空白の設定から開始 |
| `default` | ⚙️ デフォルト設定 | 基本的な設定テンプレート |
| `web-app` | 🌐 Web アプリケーション | サーバーと API 設定を持つフロントエンドアプリケーション |
| `api-service` | 🔌 API サービス | データベースと認証設定を持つバックエンドサービス |
| `microservice` | 🐳 マイクロサービス | ログとメトリクスを持つコンテナ化サービス |

## ❤️ Discord コミュニティ

[![Discord](https://img.shields.io/discord/1365929019714834493)](https://discord.gg/jXAxVPSs7K)

> [!NOTE]
> サポートが必要ですか？[k3scat@gmail.com](mailto:k3scat@gmail.com) にお問い合わせいただくか、[Nya Foundation](https://discord.gg/jXAxVPSs7K) の Discord コミュニティにご参加ください

## 📝 ライセンス

このプロジェクトは MIT ライセンスの下でライセンスされています - 詳細は [LICENSE](LICENSE) ファイルをご覧ください。