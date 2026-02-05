# Markdown Illustrator 完整改造路线图

> 从中等改造（10-50人团队）到完整SaaS服务（公开服务）的演进路径
>
> 当前版本: v1.8 (中等改造)
> 目标版本: v2.0 (完整改造)

---

## 当前架构 vs 目标架构

### 当前中等改造 (v1.8)

```
┌─────────────────────────────────────────────────────────────┐
│                    当前架构限制                              │
├─────────────────────────────────────────────────────────────┤
│  ❌ 单进程阻塞: 图片生成30秒，阻塞整个请求                 │
│  ❌ 内存存储: 重启丢失所有会话                              │
│  ❌ 无任务队列: 无法处理大量并发                            │
│  ❌ 无数据库: 用户/任务数据不持久                           │
│  ❌ 无实时通知: 用户需轮询状态                              │
│  ❌ 单机部署: 无法水平扩展                                 │
│  ❌ 无监控告警: 无法了解系统状态                            │
│  ❌ 粗粒度限流: 无法精细成本控制                            │
└─────────────────────────────────────────────────────────────┘
```

### 目标完整改造 (v2.0)

```
┌─────────────────────────────────────────────────────────────┐
│                    目标架构能力                              │
├─────────────────────────────────────────────────────────────┤
│  ✅ 异步任务: 图片生成不阻塞，用户体验流畅                 │
│  ✅ 数据持久化: 用户/任务/配额永久保存                      │
│  ✅ 任务队列: 支持海量并发请求                              │
│  ✅ 实时推送: WebSocket 进度通知                            │
│  ✅ 水平扩展: 支持多服务器部署                              │
│  ✅ 监控告警: 实时了解系统健康                              │
│  ✅ 精细化计费: 按使用量付费                                │
│  ✅ 高可用: 避免单点故障                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 改造清单

### Phase 1: 任务队列系统 (2-3周)

**目标**: 解决图片生成阻塞问题

#### 需要实现

```
┌─────────────────────────────────────────────────────────────┐
│                    异步任务架构                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   Web 请求                                                │
│      │                                                     │
│      ▼                                                     │
│   ┌─────────────┐                                        │
│   │   Flask     │                                        │
│   │   接收请求   │                                        │
│   └──────┬──────┘                                        │
│          │                                                │
│          ▼                                                │
│   ┌─────────────┐    提交任务                              │
│   │    Redis    │────────────────────────────┐            │
│   │  (Broker)   │                            │            │
│   └─────────────┘                            │            │
│          │                                   ▼            │
│          │                            ┌─────────────┐   │
│          │                            │   Celery    │   │
│          │                            │   Worker     │   │
│          │                            └──────┬──────┘   │
│          │                                   │            │
│          │         ┌───────────────────────┘            │
│          │         │                                   │
│          ▼         ▼                                   │
│   ┌─────────────────────────┐                         │
│   │  图片生成 (异步)         │                         │
│   │  - 不阻塞Web进程         │                         │
│   │  - 可并行处理多个任务    │                         │
│   │  - 失败自动重试          │                         │
│   └─────────────────────────┘                         │
│          │                                              │
│          ▼                                              │
│   ┌─────────────┐    更新状态                           │
│   │    Redis    │<──────────────┐                      │
│   │ (Result)    │               │                      │
│   └─────────────┘               │                      │
│                                  │                      │
│                                  ▼                      │
│                           WebSocket 推送                │
│                                  │                      │
│                                  ▼                      │
│                           前端实时更新                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 技术选型

| 组件 | 技术选型 | 说明 |
|-----|---------|------|
| 消息队列 | Redis + Celery | 轻量级，易部署 |
| 结果存储 | Redis | 任务状态和结果 |
| 进度推送 | WebSocket | 实时通知前端 |

#### 需要创建的文件

```
src/
├── tasks/
│   ├── __init__.py
│   ├── celery_app.py       # Celery 配置
│   ├── image_tasks.py      # 图片生成任务
│   └── progress.py          # 进度管理
├── api/
│   ├── __init__.py
│   └── websocket.py         # WebSocket 处理
└── requirements-celery.txt  # Celery 依赖
```

#### 核心代码示例

**`src/tasks/celery_app.py`**:
```python
from celery import Celery
import redis

# Redis 配置
redis_url = f"redis://{os.environ.get('REDIS_HOST', 'localhost')}:{os.environ.get('REDIS_PORT', 6379)}/0"

# 创建 Celery 应用
celery_app = Celery(
    'markdown_illustrator',
    broker=redis_url,
    backend=redis_url,
    include=['tasks.image_tasks']
)

# 配置
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30分钟超时
    task_soft_time_limit=25 * 60,  # 25分钟软超时
    worker_prefetch_multiplier=4,  # 每个worker预取4个任务
    worker_max_tasks_per_child=1000,  # 防止内存泄漏
)
```

**`src/tasks/image_tasks.py`**:
```python
from celery import current_task
from .celery_app import celery_app
from .progress import update_progress

@celery_app.task(bind=True, name='tasks.generate_image')
def generate_image_task(self, prompt, index, image_type, image_source, config):
    """
    异步生成图片任务
    """
    task_id = self.request.id

    try:
        # 更新进度: 开始
        update_progress(task_id, 0, '初始化生成器...')

        # 获取生成器
        generator = get_image_generator(config, image_source=image_source)

        # 更新进度: 生成中
        update_progress(task_id, 30, '正在生成图片...')

        # 生成图片
        image_path = generator.generate(prompt, index, image_type)

        # 更新进度: 完成
        update_progress(task_id, 100, '生成完成')

        return {
            'status': 'success',
            'image_path': image_path,
            'task_id': task_id
        }

    except Exception as e:
        # 更新进度: 失败
        update_progress(task_id, -1, f'生成失败: {str(e)}')
        raise
```

**`src/api/websocket.py`**:
```python
from flask_socketio import SocketIO, emit, join_room
from ..tasks.progress import get_task_progress

socketio = SocketIO(cors_allowed_origins="*")

@socketio.on('connect')
def handle_connect():
    emit('connected', {'data': 'Connected'})

@socketio.on('subscribe_task')
def handle_subscribe_task(data):
    task_id = data.get('task_id')
    if task_id:
        join_room(f'task_{task_id}')
        # 发送当前进度
        progress = get_task_progress(task_id)
        emit('progress', progress)

def broadcast_task_progress(task_id, progress):
    """广播任务进度"""
    socketio.emit('progress', progress, room=f'task_{task_id}')
```

#### API 改造

```python
# 原来: 同步API
@app.route('/api/illustrate', methods=['POST'])
def illustrate_markdown():
    result = illustrator.illustrate(...)  # 阻塞30秒
    return jsonify(result)

# 改造后: 异步API
@app.route('/api/illustrate', methods=['POST'])
def illustrate_markdown():
    # 创建任务
    tasks = []
    for decision in decisions:
        task = generate_image_task.delay(
            decision.prompt,
            decision.element_index,
            decision.image_type,
            decision.image_source,
            config
        )
        tasks.append({
            'id': task.id,
            'position': decision.element_index
        })

    return jsonify({
        'success': True,
        'tasks': tasks,
        'message': '已创建配图任务'
    })

# 新增: 查询任务状态
@app.route('/api/tasks/<task_id>', methods=['GET'])
def get_task_status(task_id):
    result = celery_app.AsyncResult(task_id)
    return jsonify({
        'id': task_id,
        'status': result.state,
        'result': result.result if result.ready() else None
    })
```

#### 前端改造

```javascript
// 原来: 同步等待
const response = await fetch('/api/illustrate', {...});
const result = await response.json();

// 改造后: 订阅任务进度
const response = await fetch('/api/illustrate', {...});
const { tasks } = await response.json();

// 连接 WebSocket
const socket = io();
tasks.forEach(task => {
    socket.emit('subscribe_task', { task_id: task.id });
});

// 监听进度更新
socket.on('progress', (progress) => {
    console.log(`Task ${progress.task_id}: ${progress.current}%`);
    updateUI(progress);
});
```

#### 启动方式

```bash
# 1. 启动 Redis
docker run -d -p 6379:6379 redis:alpine

# 2. 启动 Celery Worker
celery -A src.tasks.celery_app worker --loglevel=info --concurrency=4

# 3. 启动 Celery Beat (定时任务)
celery -A src.tasks.celery_app beat --loglevel=info

# 4. 启动 Flask (集成 SocketIO)
python src/web_server.py
```

---

### Phase 2: 数据持久化 (1-2周)

**目标**: 用户、任务、配额数据持久化

#### 数据库设计

```
PostgreSQL 数据库
├─ users (用户表)
├─ tasks (任务表)
├─ task_images (任务图片表)
├─ quotas (配额表)
├─ usage_records (使用记录表)
└─ billing (账单表)
```

#### 表结构

**`users` 表**:
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100) UNIQUE,
    name VARCHAR(100),
    role VARCHAR(20) DEFAULT 'user',  -- admin, user
    quota_limit INTEGER DEFAULT 50,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**`tasks` 表**:
```sql
CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(100) UNIQUE NOT NULL,  -- Celery task ID
    user_id INTEGER REFERENCES users(id),
    markdown_content TEXT,
    status VARCHAR(20),  -- pending, processing, completed, failed
    image_source VARCHAR(20),
    total_images INTEGER,
    completed_images INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    error_message TEXT
);
```

**`task_images` 表**:
```sql
CREATE TABLE task_images (
    id SERIAL PRIMARY KEY,
    task_id INTEGER REFERENCES tasks(id),
    position_index INTEGER,
    image_type VARCHAR(20),
    prompt TEXT,
    image_path TEXT,
    status VARCHAR(20),  -- pending, processing, completed, failed
    created_at TIMESTAMP DEFAULT NOW()
);
```

**`usage_records` 表**:
```sql
CREATE TABLE usage_records (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    date DATE DEFAULT CURRENT_DATE,
    image_count INTEGER DEFAULT 0,
    api_calls_count INTEGER DEFAULT 0,
    cost_cents INTEGER DEFAULT 0,  -- 成本（分）
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, date)
);
```

#### ORM 集成

**`src/models.py`**:
```python
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(100), unique=True)
    name = db.Column(db.String(100))
    role = db.Column(db.String(20), default='user')
    quota_limit = db.Column(db.Integer, default=50)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    tasks = db.relationship('Task', backref='user', lazy='dynamic')
    usage_records = db.relationship('UsageRecord', backref='user', lazy='dynamic')

class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(100), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    markdown_content = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')
    image_source = db.Column(db.String(20))
    total_images = db.Column(db.Integer)
    completed_images = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)

    # 关系
    images = db.relationship('TaskImage', backref='task', lazy='dynamic')

class TaskImage(db.Model):
    __tablename__ = 'task_images'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'))
    position_index = db.Column(db.Integer)
    image_type = db.Column(db.String(20))
    prompt = db.Column(db.Text)
    image_path = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

#### 配置文件

**`config/database.py`**:
```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 数据库配置
DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    'postgresql://user:password@localhost/markdown_illustrator'
)

# 创建引擎
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 基类
class Base:
    pass
```

---

### Phase 3: 用户系统增强 (1周)

**目标**: 完善的用户管理和认证

#### 需要实现

```
┌─────────────────────────────────────────────────────────────┐
│                    用户系统功能                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  注册/登录                                                  │
│  ├─ 邮箱验证                                               │
│  ├─ 密码重置                                               │
│  └─ OAuth (GitHub/Google)                                  │
│                                                             │
│  权限管理                                                  │
│  ├─ RBAC (角色访问控制)                                    │
│  ├─ 用户/管理员/超级管理员                                 │
│  └─ API Key 管理                                           │
│                                                             │
│  配额管理                                                  │
│  ├─ 免费版配额                                             │
│  ├─ 付费版配额                                             │
│  └─ 企业版配额                                             │
│                                                             │
│  订阅管理                                                  │
│  ├─ 订阅计划                                               │
│  ├─ 续费提醒                                               │
│  └─ 使用统计                                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 新增模块

```
src/auth/
├── __init__.py
├── models.py              # 用户模型
├── routes.py              # 认证路由
├── utils.py               # 认证工具
└── oauth/                 # OAuth 集成
    ├── github.py
    └── google.py
```

---

### Phase 4: 监控与告警 (1周)

**目标**: 实时了解系统运行状态

#### 监控指标

```
┌─────────────────────────────────────────────────────────────┐
│                    监控指标体系                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  系统指标 (System)                                          │
│  ├─ CPU 使用率                                             │
│  ├─ 内存使用率                                             │
│  ├─ 磁盘使用率                                             │
│  └─ 网络流量                                               │
│                                                             │
│  应用指标 (Application)                                     │
│  ├─ 请求数 (QPS)                                           │
│  ├─ 响应时间 (RT)                                           │
│  ├─ 错误率 (Error Rate)                                     │
│  └─ 队列长度 (Queue Length)                                │
│                                                             │
│  业务指标 (Business)                                        │
│  ├─ 活跃用户数                                             │
│  ├─ 任务成功率                                             │
│  ├─ API 调用次数                                           │
│  └─ 成本统计                                               │
│                                                             │
│  Celery 指标                                                │
│  ├─ Worker 数量                                             │
│  ├─ 任务队列长度                                           │
│  ├─ 任务执行时间                                           │
│  └─ 任务失败率                                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 技术选型

| 组件 | 技术选型 | 说明 |
|-----|---------|------|
| 指标采集 | Prometheus | 时序数据库 |
| 可视化 | Grafana | 仪表板 |
| 告警 | Alertmanager | 告警管理 |
| 日志 | ELK Stack | 日志分析 |

#### 配置示例

**`monitoring/prometheus.yml`**:
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'flask'
    static_configs:
      - targets: ['localhost:5000']
    metrics_path: '/metrics'

  - job_name: 'celery'
    static_configs:
      - targets: ['localhost:9540']
```

**Flask Prometheus 集成**:
```python
from prometheus_flask_exporter import PrometheusMetrics

prometheus_metrics = PrometheusMetrics(app)

# 自定义指标
from prometheus_client import Counter, Histogram

image_generation_counter = Counter(
    'image_generation_total',
    'Total number of images generated',
    ['source', 'status']
)

image_generation_duration = Histogram(
    'image_generation_duration_seconds',
    'Image generation duration',
    ['source']
)

# 在代码中使用
image_generation_counter.labels(source='zhipu', status='success').inc()
```

---

### Phase 5: 高可用部署 (1周)

**目标**: 水平扩展和高可用

#### 部署架构

```
┌─────────────────────────────────────────────────────────────┐
│                    高可用部署架构                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   Internet                                                  │
│      │                                                      │
│      ▼                                                      │
│   ┌──────────────┐                                        │
│   │   DNS +      │                                        │
│   │   CDN        │                                        │
│   └──────┬───────┘                                        │
│          │                                                 │
│          ▼                                                 │
│   ┌─────────────────────────────────────────────────────┐  │
│   │              Nginx (负载均衡)                        │  │
│   │              + SSL 终止                               │  │
│   └─────────────────────────────────────────────────────┘  │
│          │                                                 │
│          ├──┬────────┬────────┬────────┐                 │
│          │  │        │        │        │                 │
│          ▼  ▼        ▼        ▼        ▼                 │
│   ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐            │
│   │Flask 1 │ │Flask 2 │ │Flask 3 │ │Flask N │            │
│   └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘            │
│       │          │          │          │                  │
│       └──────────┴──────────┴──────────┘                  │
│                          │                                  │
│          ┌───────────────┴───────────────┐                │
│          │                                │                │
│          ▼                                ▼                │
│   ┌─────────────┐              ┌─────────────┐              │
│   │ PostgreSQL  │              │ Redis       │              │
│   │ (主从复制)   │              │ 哨群模式     │              │
│   └─────────────┘              └─────────────┘              │
│          │                                │                  │
│          ▼                                ▼                  │
│   ┌─────────────────────────────────────────────────────┐    │
│   │              OSS (对象存储)                           │    │
│   │              存储生成的图片                             │    │
│   └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### Kubernetes 部署

**`k8s/deployment.yaml`**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: markdown-illustrator
spec:
  replicas: 3
  selector:
    matchLabels:
      app: markdown-illustrator
  template:
    metadata:
      labels:
        app: markdown-illustrator
    spec:
      containers:
      - name: flask
        image: markdown-illustrator:latest
        ports:
        - containerPort: 5000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: url
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 5000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 5000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: markdown-illustrator-service
spec:
  selector:
    app: markdown-illustrator
  ports:
  - protocol: TCP
    port: 80
    targetPort: 5000
  type: LoadBalancer
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: markdown-illustrator-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: markdown-illustrator
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

---

### Phase 6: 计费系统 (1-2周)

**目标**: 按使用量付费

#### 订阅计划

```
┌─────────────────────────────────────────────────────────────┐
│                    订阅计划                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  免费版 (Free)                                              │
│  ├─ 价格: ¥0/月                                            │
│  ├─ 配图: 20次/天                                          │
│  ├─ 来源: Mermaid + Unsplash                                │
│  └─ 支持: 社区                                             │
│                                                             │
│  基础版 (Basic)                                             │
│  ├─ 价格: ¥29/月                                           │
│  ├─ 配图: 100次/天                                         │
│  ├─ 来源: 所有图库 + 豆包AI                                │
│  └─ 支持: 邮件                                             │
│                                                             │
│  专业版 (Pro)                                               │
│  ├─ 价格: ¥99/月                                           │
│  ├─ 配图: 500次/天                                         │
│  ├─ 来源: 所有来源                                         │
│  └─ 支持: 优先 + API                                        │
│                                                             │
│  企业版 (Enterprise)                                        │
│  ├─ 价格: ¥499/月                                          │
│  ├─ 配图: 无限                                             │
│  ├─ 来源: 所有来源 + 自定义                                 │
│  └─ 支持: 专属 + 部署                                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 计费逻辑

```python
class BillingService:
    """计费服务"""

    PRICING = {
        'mermaid': 0,
        'unsplash': 0,
        'pexels': 0,
        'doubao': 0.5,    # 0.5分/张
        'flux': 1,        # 1分/张
        'zhipu': 6,       # 6分/张
        'dalle': 40       # 40分/张
    }

    @staticmethod
    def calculate_cost(image_source, count):
        """计算成本（分）"""
        unit_price = BillingService.PRICING.get(image_source, 0)
        return unit_price * count

    @staticmethod
    def check_quota(user, image_source, count):
        """检查配额"""
        cost = BillingService.calculate_cost(image_source, count)

        # 今日已用配额
        used_today = get_user_quota_today(user.id)

        # 配额限制
        if used_today + count > user.quota_limit:
            raise QuotaExceededException(
                f"今日配额已用完 ({used_today}/{user.quota_limit})"
            )

        # 成本限制（如果是付费用户）
        if user.plan != 'free':
            monthly_budget = user.monthly_budget_cents
            used_this_month = get_user_cost_this_month(user.id)
            if used_this_month + cost > monthly_budget:
                raise BudgetExceededException(
                    f"本月预算超限 ({used_this_month + cost}/{monthly_budget}分)"
                )

        return True
```

---

## 总结对比

### 改造前后对比

| 维度 | 中等改造 (v1.8) | 完整改造 (v2.0) |
|-----|-----------------|-----------------|
| **并发处理** | 单进程阻塞 | 异步任务队列 |
| **数据存储** | 内存/文件 | PostgreSQL + Redis |
| **实时通信** | 轮询 | WebSocket 推送 |
| **扩展性** | 单机 | 水平扩展 (K8s) |
| **监控** | 无 | Prometheus + Grafana |
| **计费** | 粗粒度配额 | 精细化按量计费 |
| **高可用** | 无 | 主从 + 集群 |
| **支持用户** | 10-50人 | 无限制 |

### 工作量估算

| Phase | 内容 | 工作量 |
|-------|------|-------|
| Phase 1 | 任务队列系统 | 2-3周 |
| Phase 2 | 数据持久化 | 1-2周 |
| Phase 3 | 用户系统增强 | 1周 |
| Phase 4 | 监控与告警 | 1周 |
| Phase 5 | 高可用部署 | 1周 |
| Phase 6 | 计费系统 | 1-2周 |
| **总计** | | **7-10周** |

### 优先级建议

如果资源有限，建议按以下优先级实施：

1. **必须**: Phase 1 (任务队列) - 解决核心阻塞问题
2. **重要**: Phase 2 (数据库) - 数据持久化
3. **重要**: Phase 4 (监控) - 系统可观测性
4. **可选**: Phase 3 (用户系统) - 可后续迭代
5. **可选**: Phase 5 (高可用) - 用户量增长后再做
6. **可选**: Phase 6 (计费) - 商业化需要时再做

---

**文档版本**: v1.0
**最后更新**: 2025-01-20
