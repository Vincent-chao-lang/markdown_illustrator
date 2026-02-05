"""
Gunicorn 配置文件
用于生产环境部署
"""

import multiprocessing
import os

# 服务器socket
bind = "0.0.0.0:5001"
backlog = 2048

# Worker进程数（建议CPU核心数 * 2 + 1）
workers = multiprocessing.cpu_count() * 2 + 1

# Worker类型（sync适合CPU密集型，gevent适合IO密集型）
worker_class = "sync"
worker_connections = 1000

# 每个worker的线程数
threads = 2

# Worker最大请求数，超过后自动重启（防止内存泄漏）
max_requests = 1000
max_requests_jitter = 100

# 超时设置
timeout = 120
keepalive = 5

# 日志配置
accesslog = "-"  # 输出到stdout
errorlog = "-"   # 输出到stderr
loglevel = "info"

# 进程名称
proc_name = "markdown_illustrator"

# 守护进程（生产环境设为True）
daemon = False

# PID文件
pidfile = "markdown_illustrator.pid"

# 工作目录
chdir = os.path.dirname(os.path.abspath(__file__))

# 环境变量
raw_env = [
    'FLASK_ENV=production',
    'FLASK_SECRET_KEY=' + os.environ.get('FLASK_SECRET_KEY', 'change-me-in-production'),
]

# 启动钩子
def on_starting(server):
    """服务器启动时执行"""
    print("\n" + "="*60)
    print("Markdown Illustrator 多用户服务器启动中...")
    print("="*60 + "\n")

def when_ready(server):
    """服务器准备就绪时执行"""
    print(f"\n服务器已启动，监听 {bind}")
    print(f"Worker进程数: {workers}")
    print(f"访问地址: http://localhost:{bind.split(':')[1]}/login\n")

def on_exit(server):
    """服务器关闭时执行"""
    print("\n服务器正在关闭...")

def worker_int(worker):
    """Worker收到SIGINT信号时执行"""
    print(f"Worker {worker.pid} 正在停止...")

def pre_fork(server, worker):
    """Worker fork之前执行"""
    pass

def post_fork(server, worker):
    """Worker fork之后执行"""
    print(f"Worker {worker.pid} 已启动")

def pre_exec(server):
    """主进程重新执行之前执行"""
    print("Forked child, re-executing.")

def pre_request(worker, req):
    """处理请求之前执行"""
    worker.log.debug(f"{req.method} {req.path}")

def post_request(worker, req, environ, resp):
    """处理请求之后执行"""
    pass

def child_exit(server, worker):
    """Worker退出时执行"""
    print(f"Worker {worker.pid} 已退出")

def worker_abort(worker):
    """Worker异常退出时执行"""
    print(f"Worker {worker.pid} 异常退出！")

def nworkers_changed(server, new_value, old_value):
    """Worker数量变化时执行"""
    print(f"Worker数量: {old_value} -> {new_value}")
