#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
#  BridgeMate – macOS Local Deployment Script
# ──────────────────────────────────────────────────────────────
#  Sets up Nginx reverse proxy + Gunicorn on macOS via Homebrew.
#
#  Usage:
#    chmod +x deploy/setup-macos.sh
#    ./deploy/setup-macos.sh
# ──────────────────────────────────────────────────────────────

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
NGINX_CONF_SRC="$PROJECT_DIR/deploy/nginx-bridgemate.conf"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── 1. Check prerequisites ────────────────────────────────────
info "Checking prerequisites..."

command -v brew >/dev/null 2>&1 || error "Homebrew is required. Install it from https://brew.sh"

# ── 2. Install Nginx if needed ─────────────────────────────────
if ! command -v nginx >/dev/null 2>&1; then
    info "Installing Nginx via Homebrew..."
    brew install nginx
else
    info "Nginx is already installed: $(nginx -v 2>&1)"
fi

# ── 3. Determine Nginx config directory ────────────────────────
if [ -d "/opt/homebrew/etc/nginx/servers" ]; then
    NGINX_SERVERS_DIR="/opt/homebrew/etc/nginx/servers"
    NGINX_LOG_DIR="/opt/homebrew/var/log/nginx"
elif [ -d "/usr/local/etc/nginx/servers" ]; then
    NGINX_SERVERS_DIR="/usr/local/etc/nginx/servers"
    NGINX_LOG_DIR="/usr/local/var/log/nginx"
else
    error "Cannot find Nginx servers directory. Is Nginx installed via Homebrew?"
fi

# ── 4. Create log directory ────────────────────────────────────
mkdir -p "$NGINX_LOG_DIR"

# ── 5. Adjust Nginx config for local paths ────────────────────
info "Installing Nginx configuration..."

# Replace static files path and log paths for this machine
sed \
    -e "s|/Users/tim/Documents/bisv|$PROJECT_DIR|g" \
    -e "s|/var/log/nginx|$NGINX_LOG_DIR|g" \
    "$NGINX_CONF_SRC" > "$NGINX_SERVERS_DIR/bridgemate.conf"

info "Nginx config installed to $NGINX_SERVERS_DIR/bridgemate.conf"

# ── 6. Test Nginx configuration ───────────────────────────────
info "Testing Nginx configuration..."
nginx -t || error "Nginx configuration test failed!"

# ── 7. Set up Python virtual environment ──────────────────────
info "Setting up Python virtual environment..."

if [ ! -d "$PROJECT_DIR/venv" ]; then
    python3 -m venv "$PROJECT_DIR/venv"
    info "Created virtual environment at $PROJECT_DIR/venv"
else
    info "Virtual environment already exists"
fi

source "$PROJECT_DIR/venv/bin/activate"

info "Installing Python dependencies..."
pip install --quiet -r "$PROJECT_DIR/requirements.txt"

info "Installing Gunicorn with gevent worker..."
pip install --quiet gunicorn gevent

# ── 8. Start / Restart Nginx ──────────────────────────────────
info "Starting Nginx..."
brew services restart nginx

# ── 9. Print summary ──────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════════"
echo "  BridgeMate deployment is ready!"
echo "══════════════════════════════════════════════════════════"
echo ""
echo "  Nginx config:  $NGINX_SERVERS_DIR/bridgemate.conf"
echo "  Project dir:   $PROJECT_DIR"
echo ""
echo "  To start the application:"
echo ""
echo "    cd $PROJECT_DIR"
echo "    source venv/bin/activate"
echo "    gunicorn -c gunicorn.conf.py wsgi:app"
echo ""
echo "  Then open:  http://localhost"
echo ""
echo "  To stop Gunicorn:  Ctrl+C (or kill the process)"
echo "  To stop Nginx:     brew services stop nginx"
echo "══════════════════════════════════════════════════════════"
