# Markdown Illustrator 多用户部署指南

## 概述

Markdown Illustrator v1.8 引入了多用户支持，适合企业内部团队使用（10-50人）。

**主要特性：**
- 用户登录认证（用户名/密码）
- 会话隔离（每个用户独立的工作空间）
- 文件隔离（会话级临时目录）
- 速率限制（防误操作）
- 配额管理（每日配图次数限制）

---

## 快速开始

### 1. 开发模式（单机测试）

```bash
# 使用启动脚本（推荐）
./start_server.sh dev

# 或直接使用 Python
python3 src/web_server.py
```

访问 http://localhost:5000/login

**默认账户：**
- 用户名: `admin`
- 密码: `admin123`

### 2. 生产模式（Gunicorn 多进程）

```bash
# 使用启动脚本
./start_server.sh prod

# 或直接使用 Gunicorn
gunicorn -c gunicorn_conf.py src.web_server:app
```

---

## 配置文件

### 用户配置 (`config/users.yaml`)

```yaml
users:
  # 管理员
  admin:
    password: admin123
    name: 管理员
    role: admin
    quota_limit: 1000

  # 普通用户
  user1:
    password: user123
    name: 张三
    role: user
    quota_limit: 50
```

**配置说明：**
- `password`: 明文密码（启动时自动哈希）
- `name`: 显示名称
- `role`: 用户角色（admin/user）
- `quota_limit`: 每日配图次数限制

### Gunicorn 配置 (`gunicorn_conf.py`)

主要配置项：

```python
# 绑定地址
bind = "0.0.0.0:5001"

# Worker进程数（CPU核心数 * 2 + 1）
workers = multiprocessing.cpu_count() * 2 + 1

# 超时时间（秒）
timeout = 120
```

---

## 部署方式

### 方式 1: 直接运行

```bash
# 开发模式
python3 src/web_server.py 5000 --debug

# 生产模式
gunicorn -c gunicorn_conf.py src.web_server:app
```

### 方式 2: 使用启动脚本

```bash
# 开发模式（端口5001）
./start_server.sh dev

# 开发模式（自定义端口）
./start_server.sh dev 8000

# 生产模式
./start_server.sh prod
```

### 方式 3: systemd 服务（Linux）

```bash
# 1. 复制服务文件
sudo cp markdown-illustrator.service /etc/systemd/system/

# 2. 修改服务文件中的路径
sudo vim /etc/systemd/system/markdown-illustrator.service

# 3. 生成随机密钥
export FLASK_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# 4. 更新服务文件中的密钥
sudo vim /etc/systemd/system/markdown-illustrator.service
# 将 CHANGE_ME_TO_RANDOM_STRING 替换为生成的密钥

# 5. 启用并启动服务
sudo systemctl daemon-reload
sudo systemctl enable markdown-illustrator
sudo systemctl start markdown-illustrator

# 6. 查看状态
sudo systemctl status markdown-illustrator

# 7. 查看日志
sudo journalctl -u markdown-illustrator -f
```

### 方式 4: Docker 容器

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY . /app

RUN pip install gunicorn flask pyyaml requests zhipuai

EXPOSE 5001

CMD ["gunicorn", "-c", "gunicorn_conf.py", "src.web_server:app"]
```

```bash
# 构建镜像
docker build -t markdown-illustrator .

# 运行容器
docker run -d -p 5001:5001 \
  -e FLASK_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))") \
  markdown-illustrator
```

---

## Nginx 反向代理配置

```nginx
upstream markdown_illustrator {
    server 127.0.0.1:5001;
}

server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 10M;

    location / {
        proxy_pass http://markdown_illustrator;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 支持（如果需要）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # 超时设置
        proxy_connect_timeout 120s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }
}
```

---

## 速率限制配置

默认限制在 `src/web_server.py` 的 `RateLimiter` 类中：

```python
self.limits = {
    'illustrate': {'max': 10, 'window': 3600},  # 每小时10次配图
    'save': {'max': 100, 'window': 3600},       # 每小时100次保存
    'default': {'max': 1000, 'window': 3600}    # 其他请求每小时1000次
}
```

可根据需要调整。

---

## 临时文件清理

系统会自动清理 24 小时未访问的会话数据。

手动清理：

```bash
# 清理会话临时文件
rm -rf temp/sessions/*

# 查看会话目录大小
du -sh temp/sessions
```

---

## 监控与日志

### 查看日志

```bash
# Gunicorn 输出到 stdout/stderr
gunicorn -c gunicorn_conf.py src.web_server:app 2>&1 | tee server.log

# systemd 日志
sudo journalctl -u markdown-illustrator -f
```

### 监控指标

- **活跃会话数**: `len(session_manager.sessions)`
- **用户配额使用**: `session_manager.get_user_quota_today(username)`
- **请求速率**: `rate_limiter.get_remaining(session_id, endpoint)`

---

## 安全建议

1. **修改默认密码**
   - 首次部署后立即修改 `admin` 账户密码

2. **使用 HTTPS**
   - 生产环境务必配置 SSL 证书

3. **设置防火墙**
   ```bash
   # 只允许特定IP访问
   sudo ufw allow from 192.168.1.0/24 to any port 5001
   ```

4. **定期备份**
   ```bash
   # 备份用户配置
   cp config/users.yaml config/users.yaml.backup

   # 备份用户偏好
   cp config/preferences.json config/preferences.json.backup
   ```

5. **更新密钥**
   ```bash
   # 生成新的 SECRET_KEY
   export FLASK_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
   echo $FLASK_SECRET_KEY
   ```

---

## 故障排查

### 问题 1: 无法登录

**原因**: 用户配置文件未加载

**解决**:
```bash
# 检查配置文件是否存在
ls -la config/users.yaml

# 查看启动日志中是否加载了用户
# 已加载用户: ['admin', 'user1', ...]
```

### 问题 2: 配图失败

**原因**: API Key 未配置或配额用尽

**解决**:
```bash
# 检查 API Key
cat config/settings.yaml | grep api_key

# 查看用户配额
# 访问 /api/status 接口查看剩余配额
```

### 问题 3: 会话丢失

**原因**: 临时文件被清理

**解决**:
```bash
# 检查会话目录
ls -la temp/sessions/

# 调整清理时间（web_server.py）
session_manager.cleanup_old_sessions(max_age_hours=48)
```

---

## 性能优化

### Worker 进程数调整

```python
# gunicorn_conf.py
# CPU 密集型：workers = CPU核心数 * 2 + 1
# IO 密集型：workers = CPU核心数 * 4

workers = multiprocessing.cpu_count() * 2 + 1
```

### 使用 gevent Worker（高并发）

```bash
# 安装 gevent
pip install gevent

# 修改 gunicorn_conf.py
worker_class = "gevent"
worker_connections = 1000
```

---

## 版本信息

- 当前版本: v1.8 (多用户版)
- 支持: Python 3.7+
- 依赖: Flask, Gunicorn, PyYAML

---

## 支持

- 问题反馈: https://github.com/your-repo/issues
- 文档: docs/USER_GUIDE.md
