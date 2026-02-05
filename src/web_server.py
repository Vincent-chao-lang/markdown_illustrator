"""
Web 交互界面 - 多用户图片选择器
提供 Web 界面用于批量生成的图片预览和选择
支持多用户会话隔离和简单认证
"""

import os
import re
import json
import webbrowser
import secrets
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from flask import Flask, render_template, jsonify, request, send_from_directory, session, redirect, url_for
import threading
import time
import sys
import tempfile
from datetime import datetime, timedelta
from collections import defaultdict

app = Flask(__name__, template_folder='../templates', static_folder='../static')

# 配置
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB 限制

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.resolve()


# ============================================================================
# 用户认证管理（简单用户名密码）
# ============================================================================

class UserManager:
    """简单的用户管理器"""

    def __init__(self, users_file: Path = None):
        """
        初始化用户管理器

        Args:
            users_file: 用户配置文件路径
        """
        if users_file is None:
            users_file = PROJECT_ROOT / 'config' / 'users.yaml'

        self.users_file = users_file
        self.users = self._load_users()

    def _load_users(self) -> Dict[str, Dict]:
        """加载用户配置"""
        users = {}

        # 默认管理员账户
        users['admin'] = {
            'password': self._hash_password('admin123'),
            'name': '管理员',
            'role': 'admin',
            'quota_limit': 1000  # 每日配图次数限制
        }

        # 如果有配置文件，从配置文件加载
        if self.users_file.exists():
            import yaml
            with open(self.users_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                if config and 'users' in config:
                    for username, user_config in config['users'].items():
                        users[username] = {
                            'password': self._hash_password(user_config.get('password', '')),
                            'name': user_config.get('name', username),
                            'role': user_config.get('role', 'user'),
                            'quota_limit': user_config.get('quota_limit', 50)
                        }

        return users

    def _hash_password(self, password: str) -> str:
        """哈希密码"""
        return hashlib.sha256(password.encode()).hexdigest()

    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        """
        验证用户

        Args:
            username: 用户名
            password: 密码

        Returns:
            用户信息字典，验证失败返回 None
        """
        user = self.users.get(username)
        if user and user['password'] == self._hash_password(password):
            return {
                'username': username,
                'name': user['name'],
                'role': user['role'],
                'quota_limit': user['quota_limit']
            }
        return None

    def get_user(self, username: str) -> Optional[Dict]:
        """获取用户信息"""
        user = self.users.get(username)
        if user:
            return {
                'username': username,
                'name': user['name'],
                'role': user['role'],
                'quota_limit': user['quota_limit']
            }
        return None


# 全局用户管理器
user_manager = UserManager()


# ============================================================================
# 会话管理器
# ============================================================================

class SessionManager:
    """会话管理器，每个用户独立的服务器实例"""

    def __init__(self):
        # 存储每个会话的服务器实例
        # session_id -> ImageSelectorServer
        self.sessions: Dict[str, 'ImageSelectorServer'] = {}

        # 存储用户配额使用情况
        # username -> {date: count}
        self.user_quota: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        # 创建会话临时文件目录
        self.temp_dir = PROJECT_ROOT / 'temp' / 'sessions'
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def get_server(self, session_id: str) -> Optional['ImageSelectorServer']:
        """获取会话对应的服务器实例"""
        return self.sessions.get(session_id)

    def set_server(self, session_id: str, server: 'ImageSelectorServer'):
        """设置会话的服务器实例"""
        self.sessions[session_id] = server

    def remove_server(self, session_id: str):
        """移除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]

    def get_user_quota_today(self, username: str) -> int:
        """获取用户今日已使用的配图次数"""
        today = datetime.now().strftime('%Y-%m-%d')
        return self.user_quota[username][today]

    def increment_user_quota(self, username: str):
        """增加用户今日配图次数"""
        today = datetime.now().strftime('%Y-%m-%d')
        self.user_quota[username][today] += 1

    def check_user_quota(self, username: str, limit: int) -> bool:
        """检查用户配额是否用尽"""
        used = self.get_user_quota_today(username)
        return used < limit

    def get_session_temp_dir(self, session_id: str) -> Path:
        """获取会话的临时文件目录"""
        session_dir = self.temp_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir

    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """清理过期会话"""
        now = datetime.now()
        expired_sessions = []

        for session_id, server in self.sessions.items():
            session_dir = self.get_session_temp_dir(session_id)
            if not session_dir.exists():
                expired_sessions.append(session_id)
                continue

            # 检查目录最后修改时间
            mtime = datetime.fromtimestamp(session_dir.stat().st_mtime)
            age = now - mtime

            if age > timedelta(hours=max_age_hours):
                expired_sessions.append(session_id)

        # 清理过期会话
        for session_id in expired_sessions:
            self.remove_server(session_id)
            session_dir = self.get_session_temp_dir(session_id)
            if session_dir.exists():
                import shutil
                shutil.rmtree(session_dir)

        if expired_sessions:
            print(f"清理了 {len(expired_sessions)} 个过期会话")


# 全局会话管理器
session_manager = SessionManager()


# ============================================================================
# 速率限制器
# ============================================================================

class RateLimiter:
    """简单的速率限制器，防止误操作"""

    def __init__(self):
        # 存储请求记录
        # key = f"{session_id}:{endpoint}"
        # value = [timestamp1, timestamp2, ...]
        self.requests: Dict[str, List[float]] = defaultdict(list)

        # 限制配置
        self.limits = {
            'illustrate': {'max': 10, 'window': 3600},  # 每小时10次配图
            'save': {'max': 100, 'window': 3600},  # 每小时100次保存
            'default': {'max': 1000, 'window': 3600}  # 其他请求每小时1000次
        }

    def is_allowed(self, session_id: str, endpoint: str) -> bool:
        """
        检查是否允许请求

        Args:
            session_id: 会话ID
            endpoint: 端点名称

        Returns:
            是否允许请求
        """
        key = f"{session_id}:{endpoint}"
        now = time.time()

        # 获取限制配置
        limit_config = self.limits.get(endpoint, self.limits['default'])
        max_requests = limit_config['max']
        window = limit_config['window']

        # 清理过期记录
        self.requests[key] = [t for t in self.requests[key] if now - t < window]

        # 检查是否超过限制
        if len(self.requests[key]) >= max_requests:
            return False

        # 记录本次请求
        self.requests[key].append(now)
        return True

    def get_remaining(self, session_id: str, endpoint: str) -> int:
        """获取剩余请求次数"""
        key = f"{session_id}:{endpoint}"
        now = time.time()

        limit_config = self.limits.get(endpoint, self.limits['default'])
        max_requests = limit_config['max']
        window = limit_config['window']

        # 清理过期记录
        self.requests[key] = [t for t in self.requests[key] if now - t < window]

        return max_requests - len(self.requests[key])


# 全局速率限制器
rate_limiter = RateLimiter()


# ============================================================================
# 图片选择器服务器
# ============================================================================

class ImageSelectorServer:
    """图片选择器服务器（每个会话独立）"""

    def __init__(self, markdown_path: str, session_id: str):
        """
        初始化服务器

        Args:
            markdown_path: Markdown 文件路径
            session_id: 会话ID
        """
        self.markdown_path = Path(markdown_path)
        self.session_id = session_id
        self.candidates = []  # 候选图数据
        self.selections = {}  # 用户选择

        # 解析 Markdown 文件
        self._parse_markdown()

    def _parse_markdown(self):
        """解析 Markdown 文件，提取候选图"""
        if not self.markdown_path.exists():
            self.candidates = []
            return

        with open(self.markdown_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')

        # 正则模式匹配图片
        image_pattern = re.compile(r'!\[([^\]]+)\]\(([^)]+)\)')

        # 按位置组织候选图
        positions = {}
        position_counter = 0

        # 图片类型到中文的映射
        TYPE_NAMES = {
            'cover': '封面图',
            'section': '章节配图',
            'concept': '概念示意图',
            'atmospheric': '氛围插图',
            'diagram': '架构图',
            'code_concept': '代码结构图',
        }

        # 查找所有候选图注释块
        in_candidate_block = False
        current_position = None
        current_candidates = []
        current_image_type = 'cover'
        current_prompt = ''

        for line_num, line in enumerate(lines):
            # 检查候选图开始注释
            if '<!-- 候选图：从' in line:
                match = re.search(r'从(\d+)张中选择第(\d+)张', line)
                if match:
                    in_candidate_block = True
                    current_candidates = []
                    current_position = position_counter

                    # 尝试从前面提取提示词
                    for j in range(max(0, line_num - 10), line_num):
                        if '提示词:' in lines[j] or 'Prompt:' in lines[j]:
                            current_prompt = lines[j].split(':', 1)[1].strip()
                            break
                continue

            # 在候选图块内
            if in_candidate_block:
                # 检查是否是图片
                img_match = image_pattern.search(line)
                if img_match:
                    alt_text = img_match.group(1)
                    img_path = img_match.group(2)

                    # 判断是否选中
                    is_selected = '⭐' in line or 'selected' in line

                    current_candidates.append({
                        'index': len(current_candidates),
                        'path': img_path,
                        'line_number': line_num,
                        'is_selected': is_selected,
                        'alt_text': alt_text
                    })

                    # 从 alt text 提取图片类型
                    for img_type, cn_name in TYPE_NAMES.items():
                        if cn_name in alt_text:
                            current_image_type = img_type
                            break

                # 检查是否到了注释结束
                if '-->' in line and '<!--' not in line:
                    in_candidate_block = False

                    if current_candidates:
                        positions[current_position] = {
                            'index': current_position,
                            'image_type': current_image_type,
                            'candidates': current_candidates,
                            'prompt': current_prompt
                        }
                        position_counter += 1

                        # 重置
                        current_candidates = []
                        current_prompt = ''

        # 转换为列表并排序
        self.candidates = [positions[k] for k in sorted(positions.keys())]

        # 初始化选择（默认选中的候选图）
        for pos in self.candidates:
            for cand in pos['candidates']:
                if cand['is_selected']:
                    self.selections[pos['index']] = cand['index']
                    break
            # 如果没有选中的，默认选择第一个
            if pos['index'] not in self.selections and pos['candidates']:
                self.selections[pos['index']] = 0

    def _save_selections(self):
        """保存用户选择到 Markdown 文件"""
        if not self.markdown_path.exists():
            return

        # 读取原始文件
        with open(self.markdown_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 更新每个位置的选择
        for pos_index, selected_candidate in self.selections.items():
            pos_data = next((p for p in self.candidates if p['index'] == pos_index), None)
            if not pos_data:
                continue

            # 更新候选图显示状态
            for candidate in pos_data['candidates']:
                line_num = candidate['line_number']

                # 找到这一行
                lines = content.split('\n')
                if line_num < len(lines):
                    line = lines[line_num]

                    # 提取图片 markdown
                    img_match = re.search(r'!\[([^\]]+)\]\(([^)]+)\)', line)
                    if img_match:
                        alt_text = img_match.group(1)
                        img_path = img_match.group(2)

                        # 构建新的行
                        if candidate['index'] == selected_candidate:
                            # 选中的：添加 ⭐ 标记
                            new_line = f'![{alt_text}]({img_path}) ⭐'
                        else:
                            # 未选中的：注释掉
                            new_line = f'<!-- 候选{candidate["index"] + 1}: ![{alt_text}]({img_path}) -->'

                        # 替换这一行
                        lines[line_num] = new_line

                content = '\n'.join(lines)

        # 保存文件
        with open(self.markdown_path, 'w', encoding='utf-8') as f:
            f.write(content)


# ============================================================================
# 路由：认证相关
# ============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if request.method == 'POST':
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '')

        if not username or not password:
            return jsonify({'error': '用户名和密码不能为空'}), 400

        # 验证用户
        user = user_manager.authenticate(username, password)

        if user:
            session['username'] = user['username']
            session['name'] = user['name']
            session['role'] = user['role']
            session['quota_limit'] = user['quota_limit']
            session.permanent = True

            return jsonify({
                'success': True,
                'user': user,
                'message': f'欢迎回来，{user["name"]}！'
            })
        else:
            return jsonify({'error': '用户名或密码错误'}), 401

    # GET 请求返回登录页面
    return render_template('login.html')


@app.route('/logout')
def logout():
    """登出"""
    # 清理会话数据
    session_id = session.get('session_id')
    if session_id:
        session_manager.remove_server(session_id)

    session.clear()
    return redirect(url_for('login'))


@app.route('/api/me')
def get_current_user():
    """获取当前登录用户信息"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    username = session['username']
    user = user_manager.get_user(username)

    if user:
        # 添加今日使用量
        used = session_manager.get_user_quota_today(username)
        user['used_today'] = used
        user['remaining'] = user['quota_limit'] - used

        return jsonify({'user': user})

    return jsonify({'error': 'User not found'}), 404


# ============================================================================
# 路由：主应用
# ============================================================================

@app.route('/')
def index():
    """首页"""
    # 检查是否登录
    if 'username' not in session:
        return redirect(url_for('login'))

    # 生成会话ID（如果还没有）
    if 'session_id' not in session:
        session['session_id'] = secrets.token_urlsafe(16)

    return render_template('selector.html')


@app.route('/output/images/<path:filename>')
def serve_image(filename):
    """提供 output/images 目录下的图片文件"""
    images_dir = PROJECT_ROOT / 'output' / 'images'
    return send_from_directory(str(images_dir), filename)


@app.route('/api/session/images/<path:filename>')
def serve_session_image(filename):
    """提供会话临时目录下的图片文件"""
    session_id = session.get('session_id')
    if not session_id:
        return jsonify({'error': 'No session'}), 401

    session_dir = session_manager.get_session_temp_dir(session_id)
    images_dir = session_dir / 'images'
    return send_from_directory(str(images_dir), filename)


@app.route('/api/markdown')
def get_markdown():
    """获取 Markdown 内容"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    session_id = session.get('session_id')
    server = session_manager.get_server(session_id)

    if server is None:
        return jsonify({'error': 'No markdown file in current session'}), 404

    if not server.markdown_path.exists():
        return jsonify({'error': 'Markdown file not found'}), 404

    with open(server.markdown_path, 'r', encoding='utf-8') as f:
        content = f.read()

    return jsonify({
        'path': str(server.markdown_path),
        'content': content
    })


@app.route('/api/save-markdown', methods=['POST'])
def save_markdown():
    """保存 Markdown 内容"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    session_id = session.get('session_id')
    server = session_manager.get_server(session_id)

    if server is None:
        return jsonify({'error': 'No session'}), 404

    # 速率限制
    if not rate_limiter.is_allowed(session_id, 'save'):
        return jsonify({'error': '保存次数过多，请稍后再试'}), 429

    data = request.json
    content = data.get('content', '')

    if not content:
        return jsonify({'error': 'Content is empty'}), 400

    # 保存到文件
    with open(server.markdown_path, 'w', encoding='utf-8') as f:
        f.write(content)

    # 更新服务器实例中的内容
    server._parse_markdown()

    return jsonify({'success': True})


@app.route('/api/update-image', methods=['POST'])
def update_image():
    """更新单个图片选择"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    session_id = session.get('session_id')
    server = session_manager.get_server(session_id)

    if server is None:
        return jsonify({'error': 'No session'}), 404

    data = request.json
    position_index = data.get('position')
    candidate_index = data.get('candidate')

    if position_index is None or candidate_index is None:
        return jsonify({'error': 'Missing parameters'}), 400

    # 记录选择
    server.selections[position_index] = candidate_index

    # 保存到文件
    server._save_selections()

    # 记录偏好
    _record_preference(server, position_index, candidate_index)

    return jsonify({'success': True})


@app.route('/api/candidates')
def get_candidates():
    """获取所有候选图"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    session_id = session.get('session_id')
    server = session_manager.get_server(session_id)

    if server is None:
        return jsonify({'candidates': []})

    return jsonify({
        'markdown_path': str(server.markdown_path),
        'candidates': server.candidates
    })


@app.route('/api/select', methods=['POST'])
def select_candidate():
    """选择候选图"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    session_id = session.get('session_id')
    server = session_manager.get_server(session_id)

    if server is None:
        return jsonify({'error': 'No session'}), 404

    data = request.json
    position_index = data.get('position')
    candidate_index = data.get('candidate')

    if position_index is None or candidate_index is None:
        return jsonify({'error': 'Missing parameters'}), 400

    # 记录选择
    server.selections[position_index] = candidate_index

    # 保存到文件
    server._save_selections()

    # 记录偏好
    _record_preference(server, position_index, candidate_index)

    return jsonify({'success': True})


@app.route('/api/select-all', methods=['POST'])
def select_all_best():
    """自动选择所有最佳候选图"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    session_id = session.get('session_id')
    server = session_manager.get_server(session_id)

    if server is None:
        return jsonify({'error': 'No session'}), 404

    # 默认选择每个位置的第一张候选图
    for pos in server.candidates:
        if pos['candidates']:
            server.selections[pos['index']] = 0

    # 保存到文件
    server._save_selections()

    return jsonify({'success': True, 'selections': server.selections})


@app.route('/api/save')
def save_and_close():
    """保存选择并关闭"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    session_id = session.get('session_id')
    server = session_manager.get_server(session_id)

    if server is None:
        return jsonify({'error': 'No session'}), 404

    server._save_selections()

    return jsonify({
        'success': True,
        'message': '选择已保存',
        'selections': server.selections
    })


@app.route('/api/illustrate', methods=['POST'])
def illustrate_markdown():
    """为 Markdown 内容配图"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    session_id = session.get('session_id')
    username = session.get('username')
    quota_limit = session.get('quota_limit', 50)

    # 检查配额
    if not session_manager.check_user_quota(username, quota_limit):
        return jsonify({
            'error': '今日配图次数已达上限',
            'used': session_manager.get_user_quota_today(username),
            'limit': quota_limit
        }), 429

    # 速率限制
    if not rate_limiter.is_allowed(session_id, 'illustrate'):
        remaining = rate_limiter.get_remaining(session_id, 'illustrate')
        return jsonify({
            'error': f'配图请求过于频繁，请稍后再试',
            'remaining': remaining
        }), 429

    temp_file = None
    try:
        data = request.json
        content = data.get('content', '')
        batch = data.get('batch', 1)
        image_source = data.get('imageSource', 'auto')

        if not content:
            return jsonify({'error': '内容不能为空'}), 400

        # 使用会话临时目录
        session_temp_dir = session_manager.get_session_temp_dir(session_id)

        # 保存到临时文件
        with open(session_temp_dir / 'input.md', 'w', encoding='utf-8') as f:
            f.write(content)
        temp_file = str(session_temp_dir / 'input.md')

        # 动态导入 MarkdownIllustrator
        src_dir = Path(__file__).parent
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))
        from main import MarkdownIllustrator

        # 创建临时配置
        config_path = PROJECT_ROOT / 'config' / 'settings.yaml'

        # 创建配图器实例
        illustrator = MarkdownIllustrator(config_path=config_path)

        # 执行配图
        result = illustrator.illustrate(
            temp_file,
            output_path=temp_file,
            image_source=image_source,
            batch=batch,
            regenerate=None,
            regenerate_type=None,
            regenerate_failed=False
        )

        if not result.get('success'):
            return jsonify({'error': result.get('message', '配图失败')}), 500

        result_path = result.get('output_path')
        if not result_path:
            return jsonify({'error': '配图失败：未返回输出文件路径'}), 500

        # 读取生成的内容
        with open(result_path, 'r', encoding='utf-8') as f:
            result_content = f.read()

        # 更新会话的服务器实例
        server = ImageSelectorServer(result_path, session_id)
        session_manager.set_server(session_id, server)

        # 增加用户配额计数
        session_manager.increment_user_quota(username)

        return jsonify({
            'success': True,
            'content': result_content,
            'path': result_path,
            'images_generated': result.get('images_generated', 0),
            'message': f'配图成功，生成了 {result.get("images_generated", 0)} 张图片',
            'quota_remaining': quota_limit - session_manager.get_user_quota_today(username)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'配图失败: {str(e)}'}), 500


@app.route('/api/upload', methods=['POST'])
def upload_markdown():
    """上传 Markdown 文件"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    session_id = session.get('session_id')

    if 'file' not in request.files:
        return jsonify({'error': '没有上传文件'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': '文件名为空'}), 400

    if not file.filename.endswith('.md'):
        return jsonify({'error': '只支持 .md 文件'}), 400

    # 保存到会话临时目录
    session_temp_dir = session_manager.get_session_temp_dir(session_id)
    filepath = session_temp_dir / file.filename

    file.save(str(filepath))

    # 创建服务器实例
    server = ImageSelectorServer(str(filepath), session_id)
    session_manager.set_server(session_id, server)

    # 读取文件内容
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    return jsonify({
        'success': True,
        'filename': file.filename,
        'content': content,
        'candidates': server.candidates
    })


@app.route('/api/status')
def get_status():
    """获取系统状态"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    session_id = session.get('session_id')
    username = session.get('username')
    quota_limit = session.get('quota_limit', 50)

    server = session_manager.get_server(session_id)

    return jsonify({
        'session_id': session_id,
        'username': username,
        'has_markdown': server is not None,
        'quota_used': session_manager.get_user_quota_today(username),
        'quota_limit': quota_limit,
        'quota_remaining': quota_limit - session_manager.get_user_quota_today(username),
        'illustrate_remaining': rate_limiter.get_remaining(session_id, 'illustrate')
    })


# ============================================================================
# 辅助函数
# ============================================================================

def _record_preference(server: ImageSelectorServer, position_index: int, candidate_index: int):
    """记录用户偏好"""
    pos_data = next((p for p in server.candidates if p['index'] == position_index), None)
    if not pos_data:
        return

    candidate_data = next(
        (c for c in pos_data['candidates'] if c['index'] == candidate_index),
        None
    )
    if not candidate_data:
        return

    # 加载现有偏好
    prefs_path = PROJECT_ROOT / 'config' / 'preferences.json'
    prefs_path.parent.mkdir(parents=True, exist_ok=True)

    if prefs_path.exists():
        with open(prefs_path, 'r', encoding='utf-8') as f:
            preferences = json.load(f)
    else:
        preferences = {'selections': {}, 'stats': {}}

    # 记录选择
    image_type = pos_data['image_type']
    if image_type not in preferences['selections']:
        preferences['selections'][image_type] = []

    preferences['selections'][image_type].append({
        'position': position_index,
        'candidate': candidate_index,
        'path': candidate_data['path']
    })

    # 更新统计
    if image_type not in preferences['stats']:
        preferences['stats'][image_type] = {'total': 0, 'candidate_counts': {}}

    preferences['stats'][image_type]['total'] += 1
    preferences['stats'][image_type]['candidate_counts'][candidate_index] = \
        preferences['stats'][image_type]['candidate_counts'].get(candidate_index, 0) + 1

    # 保存偏好
    with open(prefs_path, 'w', encoding='utf-8') as f:
        json.dump(preferences, f, ensure_ascii=False, indent=2)


# ============================================================================
# 定期清理任务
# ============================================================================

def cleanup_task():
    """定期清理过期会话"""
    while True:
        time.sleep(3600)  # 每小时清理一次
        session_manager.cleanup_old_sessions()


# 启动清理线程
cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
cleanup_thread.start()


# ============================================================================
# 启动服务器
# ============================================================================

def start_server(port: int = 5000, debug: bool = False):
    """
    启动多用户图片选择器服务器

    Args:
        port: 服务器端口
        debug: 调试模式
    """
    temp_dir_str = str(PROJECT_ROOT / 'temp' / 'sessions')
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║            Markdown Illustrator - 多用户服务器                  ║
╠══════════════════════════════════════════════════════════════╣
║  版本: v1.8 (多用户版)                                       ║
║  端口: {port:<54} ║
║  访问: http://localhost:{port:<47} ║
║                                                              ║
║  默认账户:                                                   ║
║    用户名: admin                                             ║
║    密码:   admin123                                          ║
║                                                              ║
║  配置文件: config/users.yaml                                ║
║  临时目录: {temp_dir_str:<44} ║
╚══════════════════════════════════════════════════════════════╝
    """)

    print(f"已加载用户: {list(user_manager.users.keys())}")
    print(f"临时目录: {session_manager.temp_dir}")
    print(f"按 Ctrl+C 停止服务器\n")

    # 如果是开发模式，打开浏览器
    if debug:
        def open_browser():
            time.sleep(1)
            webbrowser.open(f'http://localhost:{port}/login')

        thread = threading.Thread(target=open_browser)
        thread.daemon = True
        thread.start()

    # 运行 Flask 应用
    app.run(host='0.0.0.0', port=port, debug=debug)


if __name__ == '__main__':
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    debug = '--debug' in sys.argv

    start_server(port, debug)
