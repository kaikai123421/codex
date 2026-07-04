# 私有上线部署说明：Render + 管理员登录

本项目是带后端和本地 SQLite 数据的 Web 应用，不适合直接放到 GitHub Pages、Vercel 静态站这类纯前端托管。当前推荐使用 Render 的 Docker Web Service，并通过管理员登录保护访问。

## 已加入的上线保护

- `render.yaml` 在仓库根目录，使用 `github/docker/Dockerfile` 构建。
- 云端启动命令固定为 Web 服务：`python main.py --serve-only --host 0.0.0.0 --port 8000`。
- `ADMIN_AUTH_ENABLED=true`：上线后必须先设置管理员密码，再进入系统。
- `/app/data` 挂载持久磁盘，保存数据库、登录密码哈希和会话密钥。
- API Key 均使用 `sync: false`，部署时在 Render 控制台填写，不写进 Git。

## 部署步骤

1. 把本仓库推送到 GitHub。
2. 打开 Render Dashboard，选择 **Blueprint**。
3. 连接 GitHub 仓库，Render 会读取仓库根目录的 `render.yaml`。
4. 部署前填写需要的密钥，例如 `DEEPSEEK_API_KEY`、`GEMINI_API_KEY`、`OPENAI_API_KEY`、`TUSHARE_TOKEN`。
5. 首次打开网站时设置管理员密码。

## 私有访问策略

第一版采用应用层密码保护：别人即使拿到网址，也看不到你的数据和 API。Render 的 IP 白名单属于更高套餐能力；如果后续要更强的“只允许你本人访问”，建议再加 Cloudflare Access 或 Render 入站 IP 规则。

## 注意

- 不要把本地 `.env` 上传到 GitHub。
- 不要把 `data/`、`logs/`、`reports/` 上传到 GitHub。
- 如果忘记管理员密码，在服务 Shell 中执行：`python -m src.auth reset_password`。
<!--
Private deployment note: Render is now a preview-only option.
The free-first deployment path is Cloudflare Tunnel. See docs/deploy-free-cloudflare.md.
The root render.yaml uses Render's free plan and has no persistent disk.
Do not use it as the main private trading journal unless persistence is moved to a durable database.
-->
