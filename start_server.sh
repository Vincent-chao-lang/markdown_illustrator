#!/bin/bash
# Markdown Illustrator 多用户服务器启动脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查依赖
check_dependencies() {
    print_info "检查依赖..."

    # 检查 Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python3 未安装"
        exit 1
    fi

    # 检查 pip
    if ! command -v pip3 &> /dev/null; then
        print_error "pip3 未安装"
        exit 1
    fi

    # 检查 Gunicorn
    if ! command -v gunicorn &> /dev/null; then
        print_warning "Gunicorn 未安装，正在安装..."
        pip3 install gunicorn
        if [ $? -eq 0 ]; then
            print_success "Gunicorn 安装成功"
        else
            print_error "Gunicorn 安装失败"
            exit 1
        fi
    fi

    print_success "依赖检查完成"
}

# 安装 Python 依赖
install_python_packages() {
    print_info "安装 Python 依赖包..."

    pip3 install -q flask pyyaml requests zhipuai

    print_success "Python 依赖安装完成"
}

# 设置环境变量
setup_environment() {
    print_info "设置环境变量..."

    # 生成随机的 SECRET_KEY（如果未设置）
    if [ -z "$FLASK_SECRET_KEY" ]; then
        export FLASK_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
        print_info "已生成 FLASK_SECRET_KEY"
    fi

    print_success "环境变量设置完成"
}

# 启动服务器
start_server() {
    local mode=$1
    local port=${2:-5001}

    print_info "启动 Markdown Illustrator 多用户服务器..."
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Markdown Illustrator - 多用户服务器"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  模式: $mode"
    echo "  端口: $port"
    echo "  访问: http://localhost:$port/login"
    echo ""
    echo "  默认账户:"
    echo "    用户名: admin"
    echo "    密码:   admin123"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    case $mode in
        dev)
            print_info "使用开发模式启动 (Flask 开发服务器)..."
            python3 src/web_server.py $port --debug
            ;;
        prod)
            print_info "使用生产模式启动 (Gunicorn)..."
            gunicorn -c gunicorn_conf.py src.web_server:app
            ;;
        *)
            print_error "未知模式: $mode"
            echo "用法: $0 {dev|prod} [port]"
            exit 1
            ;;
    esac
}

# 主函数
main() {
    # 检查参数
    if [ $# -lt 1 ]; then
        echo "用法: $0 {dev|prod} [port]"
        echo ""
        echo "示例:"
        echo "  $0 dev      # 开发模式启动（端口5001）"
        echo "  $0 dev 8000 # 开发模式启动（端口8000）"
        echo "  $0 prod     # 生产模式启动（端口5001）"
        echo "  $0 prod 8000 # 生产模式启动（端口8000）"
        exit 1
    fi

    local mode=$1
    local port=${2:-5001}

    # 检查依赖
    check_dependencies

    # 安装 Python 包
    install_python_packages

    # 设置环境变量
    setup_environment

    # 启动服务器
    start_server "$mode" "$port"
}

# 运行主函数
main "$@"
