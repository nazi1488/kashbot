#!/bin/bash

# Deployment script for production VPS
# Usage: ./deploy.sh [install|update|restart|stop]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
APP_DIR="/opt/telegram-bot"
BACKUP_DIR="/opt/backups"
NGINX_CONF="/etc/nginx/sites-available/telegram-bot"
SSL_DIR="/etc/nginx/ssl"

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root or with sudo
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root or with sudo"
        exit 1
    fi
}

# Install dependencies and initial setup
install() {
    log_info "Starting installation..."
    
    # Update system
    apt-get update && apt-get upgrade -y
    
    # Install required packages
    apt-get install -y \
        docker.io \
        docker-compose \
        nginx \
        certbot \
        python3-certbot-nginx \
        git \
        htop \
        fail2ban \
        ufw
    
    # Enable and start Docker
    systemctl enable docker
    systemctl start docker
    
    # Setup firewall
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow ssh
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw --force enable
    
    # Create application directory
    mkdir -p $APP_DIR
    mkdir -p $BACKUP_DIR
    mkdir -p $SSL_DIR
    
    # Clone or update repository
    if [ ! -d "$APP_DIR/.git" ]; then
        git clone https://github.com/yourusername/telegram-bot.git $APP_DIR
    else
        cd $APP_DIR && git pull
    fi
    
    # Copy environment file
    if [ ! -f "$APP_DIR/.env" ]; then
        cp $APP_DIR/.env.production $APP_DIR/.env
        log_warn "Please edit $APP_DIR/.env with your actual credentials"
        exit 0
    fi
    
    # Setup SSL certificate
    read -p "Enter your domain name: " DOMAIN
    certbot certonly --nginx -d $DOMAIN
    
    # Link SSL certificates
    ln -sf /etc/letsencrypt/live/$DOMAIN/fullchain.pem $SSL_DIR/fullchain.pem
    ln -sf /etc/letsencrypt/live/$DOMAIN/privkey.pem $SSL_DIR/privkey.pem
    
    # Setup Nginx
    cp $APP_DIR/nginx.conf $NGINX_CONF
    sed -i "s/your-domain.com/$DOMAIN/g" $NGINX_CONF
    ln -sf $NGINX_CONF /etc/nginx/sites-enabled/telegram-bot
    rm -f /etc/nginx/sites-enabled/default
    nginx -t && systemctl reload nginx
    
    # Initialize database
    cd $APP_DIR
    docker-compose up -d postgres redis
    sleep 10
    docker-compose exec postgres psql -U bot_user -d bot_db -c "SELECT 1"
    
    # Run migrations
    docker-compose run --rm bot alembic upgrade head
    
    log_info "Installation completed!"
    log_info "Next steps:"
    log_info "1. Edit $APP_DIR/.env with your credentials"
    log_info "2. Run: ./deploy.sh update"
}

# Update application
update() {
    log_info "Updating application..."
    
    cd $APP_DIR
    
    # Backup database
    BACKUP_FILE="$BACKUP_DIR/db_backup_$(date +%Y%m%d_%H%M%S).sql"
    docker-compose exec -T postgres pg_dump -U bot_user bot_db > $BACKUP_FILE
    log_info "Database backed up to $BACKUP_FILE"
    
    # Pull latest code
    git pull
    
    # Rebuild containers
    docker-compose build --no-cache
    
    # Run migrations
    docker-compose run --rm bot alembic upgrade head
    
    # Restart services with zero downtime
    docker-compose up -d --no-deps --build bot
    sleep 5
    docker-compose up -d --no-deps --build worker_video worker_image worker_download
    docker-compose up -d --no-deps celery_beat flower
    
    # Cleanup old images
    docker image prune -f
    
    log_info "Update completed!"
}

# Restart services
restart() {
    log_info "Restarting services..."
    
    cd $APP_DIR
    docker-compose restart
    
    # Check health
    sleep 10
    curl -f http://localhost:8443/health || log_error "Health check failed!"
    
    log_info "Services restarted!"
}

# Stop services
stop() {
    log_info "Stopping services..."
    
    cd $APP_DIR
    docker-compose down
    
    log_info "Services stopped!"
}

# Monitor services
monitor() {
    log_info "Starting monitoring..."
    
    cd $APP_DIR
    
    # Show service status
    docker-compose ps
    
    echo ""
    log_info "Logs (last 50 lines):"
    docker-compose logs --tail=50
    
    echo ""
    log_info "Resource usage:"
    docker stats --no-stream
    
    echo ""
    log_info "Celery tasks:"
    docker-compose exec -T redis redis-cli -n 0 llen celery
}

# Backup data
backup() {
    log_info "Creating backup..."
    
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_PATH="$BACKUP_DIR/backup_$TIMESTAMP"
    mkdir -p $BACKUP_PATH
    
    # Backup database
    cd $APP_DIR
    docker-compose exec -T postgres pg_dump -U bot_user bot_db > "$BACKUP_PATH/database.sql"
    
    # Backup Redis
    docker-compose exec -T redis redis-cli --rdb "$BACKUP_PATH/redis.rdb"
    
    # Backup configs
    cp $APP_DIR/.env "$BACKUP_PATH/.env"
    cp -r $APP_DIR/locales "$BACKUP_PATH/locales"
    
    # Compress backup
    tar -czf "$BACKUP_PATH.tar.gz" -C $BACKUP_DIR "backup_$TIMESTAMP"
    rm -rf $BACKUP_PATH
    
    log_info "Backup created: $BACKUP_PATH.tar.gz"
}

# Main script
check_root

case "$1" in
    install)
        install
        ;;
    update)
        update
        ;;
    restart)
        restart
        ;;
    stop)
        stop
        ;;
    monitor)
        monitor
        ;;
    backup)
        backup
        ;;
    *)
        echo "Usage: $0 {install|update|restart|stop|monitor|backup}"
        exit 1
        ;;
esac
